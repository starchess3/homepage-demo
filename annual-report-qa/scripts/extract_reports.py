#!/usr/bin/env python3
"""从年报 PDF 抽取文字 + 表格，按“公司/章节/页码”切块。

表格用 PyMuPDF 的 find_tables 还原成“行 | 列”文本，随正文一起写入块；
每个块带 company / code / year / page / section 元数据。
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import fitz  # PyMuPDF


SECTION_RE = re.compile(
    r"^\s*(第[一二三四五六七八九十百]+节|"
    r"[一二三四五六七八九十]+、|\d+、|（[一二三四五六七八九十]+）|[一二三四五六七八九十]+\.)"
)


def detect_section(line: str) -> str | None:
    line = line.strip()
    if not line or len(line) > 60:
        return None
    if SECTION_RE.match(line):
        return line[:40]
    return None


def render_table(table) -> str:
    try:
        rows = table.extract()
    except Exception:  # noqa: BLE001
        return ""
    out = []
    for r in rows:
        if not r:
            continue
        cells = [("" if c is None else str(c).replace("\n", " ").strip()) for c in r]
        if not any(cells):
            continue
        out.append(" | ".join(cells))
    if not out:
        return ""
    return "[表格]\n" + "\n".join(out) + "\n[/表格]"


def chunk_text(text: str, size: int = 600) -> list[str]:
    paras = [p.strip() for p in re.split(r"\n\s*\n|\n", text) if p.strip()]
    chunks, cur = [], ""
    for p in paras:
        if len(cur) + len(p) + 1 <= size:
            cur = (cur + "\n" + p).strip()
        else:
            if cur:
                chunks.append(cur)
            cur = p
    if cur:
        chunks.append(cur)
    return chunks


def extract_pdf(pdf_path: Path, company: str, code: str, year: str, report: str) -> list[dict]:
    doc = fitz.open(pdf_path)
    records, current_section = [], "首页"
    for page_no, page in enumerate(doc, 1):
        text = page.get_text("text") or ""
        tables = ""
        try:
            for t in page.find_tables():
                tables += render_table(t) + "\n"
        except Exception:  # noqa: BLE001
            pass
        for line in text.splitlines():
            sec = detect_section(line)
            if sec:
                current_section = sec
                break
        full = (text + "\n" + tables).strip()
        if not full:
            continue
        for chunk in chunk_text(full):
            records.append({
                "company": company, "code": code, "year": year, "report": report,
                "page": page_no, "section": current_section, "text": chunk,
            })
    doc.close()
    return records


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf-dir", default=str(Path(__file__).parent.parent / "data" / "pdfs"))
    ap.add_argument("--out", default=str(Path(__file__).parent.parent / "data" / "chunks.jsonl"))
    ap.add_argument("--year", default="2024")
    args = ap.parse_args()

    pdf_dir = Path(args.pdf_dir)
    manifest = json.loads((pdf_dir / "manifest.json").read_text(encoding="utf-8"))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    total = 0
    with open(out, "w", encoding="utf-8") as f:
        for m in manifest:
            pdf = pdf_dir / m["file"]
            if not pdf.exists():
                print(f"跳过缺失: {pdf.name}")
                continue
            print(f"抽取 {m['name']} ({m['code']}) ...")
            recs = extract_pdf(pdf, m["name"], m["code"], args.year, f"{args.year}年年度报告")
            for r in recs:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
            total += len(recs)
            print(f"    -> {len(recs)} 块")
    print(f"完成，共 {total} 块，输出 {out}")


if __name__ == "__main__":
    main()
