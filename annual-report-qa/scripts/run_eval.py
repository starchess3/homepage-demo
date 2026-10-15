#!/usr/bin/env python3
"""跑 10 道评测题：逐题记录召回了哪些块、答对没有、错在哪，输出 md + html。"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from indexer import HybridIndex, load_chunks


def norm(s: str) -> str:
    return re.sub(r"[\s,，%]", "", s)


def fact_hits(facts: list[str], text: str) -> dict[str, bool]:
    t = norm(text)
    return {f: norm(f) in t for f in facts}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--chunks", default=str(Path(__file__).parent.parent / "data" / "chunks.jsonl"))
    ap.add_argument("--questions", default=str(Path(__file__).parent.parent / "eval" / "questions.jsonl"))
    ap.add_argument("--out-md", default=str(Path(__file__).parent.parent / "output" / "eval_results.md"))
    ap.add_argument("--out-html", default=str(Path(__file__).parent.parent / "output" / "eval_results.html"))
    ap.add_argument("--top-k", type=int, default=5)
    args = ap.parse_args()

    idx = HybridIndex(load_chunks(args.chunks))
    questions = [json.loads(l) for l in open(args.questions, encoding="utf-8") if l.strip()]

    results = []
    for q in questions:
        hits = idx.query(q["question"], top_k=args.top_k)
        joined = "\n".join(h["text"] for h in hits)
        hit_map = fact_hits(q["gold"], joined)
        n_hit = sum(hit_map.values())
        cross = q.get("needs_aggregation", False)

        if cross:
            verdict = "翻车（召回可，但缺跨公司聚合/比较）"
        elif n_hit == len(q["gold"]):
            verdict = "答对"
        elif n_hit > 0:
            verdict = "部分答对"
        else:
            verdict = "翻车（未召回相关块）"

        results.append({
            "id": q["id"], "question": q["question"], "type": q["type"],
            "cross": cross, "gold": q["gold"], "hint": q.get("hint", ""),
            "hits": hits, "hit_map": hit_map, "n_hit": n_hit,
            "n_gold": len(q["gold"]), "verdict": verdict,
        })

    # markdown
    md = ["# 年报问答 10 题评测记录\n",
          "> 检索系统：向量(字符 bigram 特征哈希) + BM25 混合；回答为检索块原文 + 出处。",
          "> 判定：事实命中 = 标准答案中的关键数字/事实出现在 top-5 召回文本中。\n"]
    for r in results:
        md.append(f"\n## {r['id']}（{'跨公司全景' if r['cross'] else '单公司事实'}） {r['verdict']}")
        md.append(f"\n**问题**：{r['question']}")
        md.append(f"\n**标准答案要点**：{r['hint']}")
        md.append(f"\n**事实命中**：{r['n_hit']}/{r['n_gold']}")
        for f, ok in r["hit_map"].items():
            md.append(f"\n- {'✔' if ok else '✘'} `{f}`")
        md.append("\n**召回块**：")
        for h in r["hits"][:5]:
            snippet = h["text"].replace("\n", " ")[:140]
            md.append(
                f"\n- `{h['company']} {h['code']}` {h['year']}年报 第{h['page']}页 "
                f"《{h['section']}》 → {snippet}"
            )
        md.append("")

    Path(args.out_md).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out_md).write_text("\n".join(md), encoding="utf-8")

    # html
    rows = []
    for r in results:
        cls = {"答对": "ok", "部分答对": "part", "翻车": "fail"}.get(r["verdict"].split("（")[0], "part")
        facts = " ".join(
            f"<span class='{'hit' if ok else 'miss'}'>{html.escape(f)}</span>" for f, ok in r["hit_map"].items()
        )
        blocks = "".join(
            f"<li><b>{html.escape(h['company'])} {h['code']}</b> 第{h['page']}页 "
            f"{html.escape(h['section'][:16])}<br><span class='src'>{html.escape(h['text'][:120])}</span></li>"
            for h in r["hits"][:5]
        )
        rows.append(
            f"<tr><td>{r['id']}</td><td>{'跨公司' if r['cross'] else '单公司'}</td>"
            f"<td class='q'>{html.escape(r['question'])}</td>"
            f"<td class='{cls}'>{html.escape(r['verdict'])}</td>"
            f"<td>{r['n_hit']}/{r['n_gold']}<br>{facts}</td>"
            f"<td><ul class='blk'>{blocks}</ul></td></tr>"
        )
    doc = f"""<!doctype html><meta charset="utf-8"><title>年报问答 10 题评测</title>
<style>
body{{font-family:-apple-system,'PingFang SC','Microsoft YaHei',sans-serif;margin:28px;color:#1b2733}}
h1{{font-size:22px}}table{{border-collapse:collapse;width:100%;font-size:13px}}
td,th{{border:1px solid #dfe5ec;padding:8px 10px;vertical-align:top}}
th{{background:#f2f5f9}}td.q{{max-width:260px}}
.ok{{color:#157f3d;font-weight:600}}.part{{color:#b27a00;font-weight:600}}.fail{{color:#c0392b;font-weight:600}}
.hit{{background:#e5f6eb;padding:0 4px;border-radius:4px}}.miss{{background:#fdecec;color:#c0392b;padding:0 4px;border-radius:4px}}
.src{{color:#66788c}}ul.blk{{margin:0;padding-left:16px}}li{{margin:4px 0}}
</style>
<h1>年报问答 10 题评测记录</h1>
<p>检索：向量 + BM25 混合；回答为检索块原文 + 出处。标准答案要点见每行“事实命中”。</p>
<table><thead><tr><th>题</th><th>类型</th><th>问题</th><th>判定</th><th>事实命中</th><th>召回块（公司/页码/章节）</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table>
"""
    Path(args.out_html).write_text(doc, encoding="utf-8")

    ok = sum(1 for r in results if r["verdict"].startswith("答对"))
    part = sum(1 for r in results if r["verdict"].startswith("部分"))
    fail = len(results) - ok - part
    print(f"完成：{len(results)} 题，答对 {ok}，部分 {part}，翻车 {fail}")
    print(f"记录见 {args.out_md} 与 {args.out_html}")


if __name__ == "__main__":
    main()
