#!/usr/bin/env python3
"""Step 1/2: 抽取君正股份财报全文（按页，带页码），输出结构化语料。

输出:
  corpus/reports.json   # 每份报告: doc_id, year, rtype, title, path, page_count, pages[{page,text}]
  corpus/pages.jsonl    # 每页一行: {doc_id, year, rtype, page, text}
"""
import json
import os
import sys
from pathlib import Path

from pypdf import PdfReader


def find_reports(base: Path) -> list[dict]:
    """按目录约定返回报告列表，识别年报/半年报与年份。"""
    items = []
    for rtype, folder in (("annual", "年报"), ("half", "半年报")):
        d = base / folder
        if not d.exists():
            continue
        for p in sorted(d.glob("*.pdf")):
            name = p.stem  # 如: 君正股份2023年年度报告
            year = None
            for ch in name:
                if ch.isdigit():
                    year = int("".join(c for c in name if c.isdigit())[:4])
                    break
            items.append({
                "doc_id": f"{rtype}_{year}",
                "year": year,
                "rtype": rtype,
                "title": name,
                "path": str(p),
            })
    return items


def extract(report: dict) -> dict:
    reader = PdfReader(report["path"])
    pages = []
    for i, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""
        text = " ".join(text.split())
        pages.append({"page": i, "text": text})
    report["page_count"] = len(pages)
    report["pages"] = pages
    return report


def main() -> None:
    base = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(
        os.path.expanduser("~/Desktop/人工智能与数据分析课程"))
    out_dir = Path(__file__).parent / "corpus"
    out_dir.mkdir(parents=True, exist_ok=True)

    reports = [extract(r) for r in find_reports(base)]
    reports.sort(key=lambda r: (r["year"], r["rtype"]))

    # reports.json 保存页文本，便于脚本生成问答时引用
    with open(out_dir / "reports.json", "w", encoding="utf-8") as f:
        json.dump(reports, f, ensure_ascii=False, indent=2)

    # pages.jsonl 每页一行，便于按页检索/抽检
    with open(out_dir / "pages.jsonl", "w", encoding="utf-8") as f:
        for r in reports:
            for p in r["pages"]:
                f.write(json.dumps({
                    "doc_id": r["doc_id"],
                    "year": r["year"],
                    "rtype": r["rtype"],
                    "page": p["page"],
                    "text": p["text"],
                }, ensure_ascii=False) + "\n")

    total_chars = sum(len(p["text"]) for r in reports for p in r["pages"])
    print(f"抽取完成: {len(reports)} 份报告, 共 {sum(r['page_count'] for r in reports)} 页, {total_chars} 字符")
    for r in reports:
        print(f"  {r['doc_id']:<12} {r['page_count']:>4} 页  {r['title']}")


if __name__ == "__main__":
    main()
