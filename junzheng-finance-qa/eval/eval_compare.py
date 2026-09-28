#!/usr/bin/env python3
"""Step 5/6: 四格对照 + RAG 对照评测。

在 Colab 里跑（GPU 环境，与 train_lora.ipynb 同一套依赖）。三种回答方式:
  A) 微调模型 (LoRA adapter 加载到基座)
  B) 基座模型 (没训练过)
  C) 知识库 RAG + 同一个基座模型 (检索财报原文页作为上下文)

打分: 答案对每条“关键事实组”(gold 里的一个列表) 只要命中任一写法就算对，
      单题得分 = 命中事实组数 / 总事实组数。

用法(Colab 单元格):
  %run eval_compare.py --base Qwen/Qwen2.5-1.5B-Instruct \
      --adapter /content/junzheng_lora/adapter
"""
import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from peft import PeftModel


SYSTEM = (
    "你是A股上市公司北京君正(君正股份,300223)的董事会秘书。"
    "请用合规、客观、克制的董秘口吻回答投资者问题，只依据公司财报信息作答。"
)


def load_model_tokenizer(model_id: str, adapter: str | None = None):
    bnb = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True,
        bnb_4bit_compute_dtype=torch.float16,
    )
    tok = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    model = AutoModelForCausalLM.from_pretrained(
        model_id, quantization_config=bnb, device_map="auto",
        torch_dtype=torch.float16, trust_remote_code=True,
    )
    if adapter:
        model = PeftModel.from_pretrained(model, adapter)
    model.eval()
    return model, tok


def build_index(corpus_path: str) -> list[dict]:
    with open(corpus_path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def retrieve(index: list[dict], query: str, top_k: int = 3) -> list[dict]:
    q_chars = [c for c in query if not c.isspace()]
    scored = []
    for p in index:
        s = sum(p["text"].count(c) for c in q_chars)
        scored.append((s, p))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [p for _, p in scored[:top_k]]


def ask(model, tok, question: str, context: str | None = None) -> str:
    sys_msg = SYSTEM
    if context:
        sys_msg += "\n\n可参考的公司财报原文（节选）:\n" + context
    prompt = tok.apply_chat_template(
        [{"role": "system", "content": sys_msg},
         {"role": "user", "content": "投资者提问：" + question}],
        tokenize=False, add_generation_prompt=True,
    )
    inputs = tok(prompt, return_tensors="pt").to(model.device)
    out = model.generate(**inputs, max_new_tokens=256, do_sample=False)
    return tok.decode(out[0], skip_special_tokens=True)


def norm(s: str) -> str:
    return re.sub(r"[\s,，]", "", s)


def score_answer(answer: str, gold: list[list[str]]) -> float:
    a = norm(answer)
    hit = 0
    for group in gold:
        if any(norm(v) in a for v in group):
            hit += 1
    return hit / len(gold) if gold else 0.0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="Qwen/Qwen2.5-1.5B-Instruct")
    ap.add_argument("--adapter", default=None, help="LoRA adapter 目录")
    ap.add_argument("--eval", default=str(Path(__file__).parent / "eval_questions.jsonl"))
    ap.add_argument("--corpus", default=str(Path(__file__).parent.parent / "corpus" / "pages.jsonl"))
    ap.add_argument("--out", default=str(Path(__file__).parent / "results.json"))
    args = ap.parse_args()

    questions = [json.loads(l) for l in open(args.eval, encoding="utf-8") if l.strip()]
    index = build_index(args.corpus)

    # 基座模型（未微调）必须单独加载，否则 base/rag 会误用微调后的权重
    base_model, tok = load_model_tokenizer(args.base, None)
    ft_model = None
    if args.adapter:
        ft_model, _ = load_model_tokenizer(args.base, args.adapter)

    results = []
    for q in questions:
        ctx_chunks = "\n".join(
            f"[{p['doc_id']} 第{p['page']}页] {p['text'][:1500]}" for p in retrieve(index, q["question"])
        )
        setups = [("base", base_model, None), ("rag", base_model, ctx_chunks)]
        if ft_model is not None:
            setups.insert(0, ("ft", ft_model, None))
        for name, mdl, ctx in setups:
            ans = ask(mdl, tok, q["question"], context=ctx)
            results.append({
                "id": q["id"], "group": q["group"], "phrasing": q["phrasing"],
                "setup": name, "score": score_answer(ans, q["gold"]),
                "answer": ans,
            })
            print(f"[{name}] {q['id']}: {results[-1]['score']:.2f}")

    # 四格对照: 训练过/没训练过 x 原问法/换问法，分别对 ft / base / rag
    grid = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    for r in results:
        grid[r["setup"]][r["group"]][r["phrasing"]].append(r["score"])

    setups = ["ft", "base", "rag"]
    print("\n===== 四格对照（关键事实命中率，0~1） =====")
    for st in setups:
        print(f"\n{st}  (ft=微调, base=基座, rag=知识库+基座)")
        print("              原问法   换问法")
        for g in ["trained", "unseen"]:
            o = sum(grid[st][g]["original"]) / max(1, len(grid[st][g]["original"]))
            p = sum(grid[st][g]["paraphrase"]) / max(1, len(grid[st][g]["paraphrase"]))
            print(f"{g:<12}  {o:.2f}     {p:.2f}")

    # 总览
    print("\n===== 三种方式总览（平均命中率） =====")
    for st in setups:
        vals = [r["score"] for r in results if r["setup"] == st]
        print(f"{st}: {sum(vals)/len(vals):.3f}")

    Path(args.out).write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n明细见 {args.out}")


if __name__ == "__main__":
    main()
