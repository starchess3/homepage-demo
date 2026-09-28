#!/usr/bin/env python3
"""Step 2: 用大模型从财报原文生成「投资者提问 -> 董秘作答」问答，答案标注出处(报告+页码)。

用法:
  OPENAI_API_KEY=sk-xxx OPENAI_BASE_URL=https://api.openai.com/v1 \
  MODEL=gpt-4o-mini python3 generate_qa.py

默认使用 OpenAI 兼容接口；任何支持 /chat/completions 的网关(含 Colab 环境里的各家模型)均可。
输出:
  data/qa_dataset_raw.jsonl    # 原始生成结果(未抽检)

说明:
  1) 按“页”喂给模型，要求答案只能来自给定页面文字，并逐条给出 page 引用;
  2) 保留 source_snippet 便于后续人工抽检比对原文;
  3) 若环境变量缺失，脚本会退出并提示(不会联网空跑)。
"""
import json
import os
import re
import sys
import urllib.request
from pathlib import Path


BASE = Path(__file__).parent
CORPUS = BASE / "corpus" / "pages.jsonl"
OUT = BASE / "data" / "qa_dataset_raw.jsonl"

SYSTEM = (
    "你是A股上市公司北京君正(君正股份,300223)的董事会秘书。你的任务是基于给定的财报原文，"
    "生成“投资者提问 -> 董秘作答”的问答对，用于训练一个熟悉公司披露口径的小模型。\n"
    "硬性要求:\n"
    "1. 每个回答必须严格、准确地来自下面给出的原文片段，不得编造任何数字、日期或结论;\n"
    "2. 回答采用董秘口吻(客观、合规、克制，常用“感谢您的关注”“以公司公告为准”等)，"
    "但关键数据必须与原文一致;\n"
    "3. 每条问答都要附 citations: 列出所用到的页码(报告内部页码);\n"
    "4. 数字尽量保留原文口径(元或万元)，并保留同比增减百分比;\n"
    "5. 只输出 JSON 数组，不要输出任何解释性文字。"
)

USER_TMPL = (
    "以下是《{title}》的部分原文(每段前缀为 [第N页]):\n\n{chunks}\n\n"
    "请生成 4~6 条问答对，覆盖: 营收与利润、同比变动原因、研发投入、分红、现金流、资产情况、"
    "业务/产品线、经营展望等。输出 JSON 数组，每项结构为:\n"
    '{{"question":"投资者提问","answer":"董秘作答",'
    '"citations":[{{"page":7}}],"source_snippet":"原文关键句","key_facts":["事实点1"]}}'
)


def load_pages() -> list[dict]:
    with open(CORPUS, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def chunk_report(pages: list[dict], max_chars: int = 14000) -> list[str]:
    """把一份报告按页拼接成长文本块，供模型单次请求使用。"""
    blocks, cur, cur_len = [], [], 0
    for p in pages:
        seg = f"[第{p['page']}页] {p['text']}\n"
        if cur_len + len(seg) > max_chars and cur:
            blocks.append("\n".join(cur))
            cur, cur_len = [], 0
        cur.append(seg)
        cur_len += len(seg)
    if cur:
        blocks.append("\n".join(cur))
    return blocks


def call_llm(api_key: str, base_url: str, model: str, system: str, user: str) -> list[dict]:
    url = base_url.rstrip("/") + "/chat/completions"
    body = {
        "model": model,
        "temperature": 0.3,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        data = json.loads(resp.read().decode())
    content = data["choices"][0]["message"]["content"]
    # 容错: 去掉 ```json ... ``` 包裹
    content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content.strip(), flags=re.M)
    return json.loads(content)


def main() -> None:
    api_key = os.environ.get("OPENAI_API_KEY")
    base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
    model = os.environ.get("MODEL", "gpt-4o-mini")
    if not api_key:
        print("缺少 OPENAI_API_KEY。示例: OPENAI_API_KEY=sk-xxx python3 generate_qa.py", file=sys.stderr)
        sys.exit(1)

    pages = load_pages()
    by_doc: dict[str, list[dict]] = {}
    for p in pages:
        by_doc.setdefault(p["doc_id"], []).append(p)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    n_total = 0
    with open(OUT, "w", encoding="utf-8") as f:
        for doc_id, ps in by_doc.items():
            title = f"{ps[0]['year']}{'年年度报告' if ps[0]['rtype']=='annual' else '年半年度报告'}"
            blocks = chunk_report(ps)
            print(f"[{doc_id}] {len(ps)} 页 -> {len(blocks)} 块")
            for bi, block in enumerate(blocks):
                try:
                    items = call_llm(api_key, base_url, model, SYSTEM,
                                     USER_TMPL.format(title=title, chunks=block))
                except Exception as e:  # noqa: BLE001
                    print(f"  ! {doc_id} 块{bi} 调用失败: {e}", file=sys.stderr)
                    continue
                for it in items:
                    rec = {
                        "id": f"qa_{n_total:04d}",
                        "report": doc_id,
                        "year": ps[0]["year"],
                        "rtype": ps[0]["rtype"],
                        "report_title": title,
                        "question": it.get("question", ""),
                        "answer": it.get("answer", ""),
                        "citations": it.get("citations", []),
                        "key_facts": it.get("key_facts", []),
                        "source_snippet": it.get("source_snippet", ""),
                        "status": "raw",
                    }
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    n_total += 1
    print(f"完成: 共生成 {n_total} 条, 见 {OUT}")


if __name__ == "__main__":
    main()
