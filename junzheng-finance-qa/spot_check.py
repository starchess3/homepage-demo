#!/usr/bin/env python3
"""Step 3: 抽检问答数据。逐条把 key_facts 里的“数字/关键术语”回原文出处页码比对：
- 数字级回源：事实串中的每个数字都要能在出处页找到（去掉千分位逗号后子串匹配）。
- 空洞避答检测：答案若只有“以公告为准/未披露”等套话且没有实质数字，判为无效。
任一事实回源失败或答案空洞，即标记 DELETE。

输出:
  data/spot_check.csv         # 逐条抽检记录(含失败原因)
  data/qa_dataset_clean.jsonl # 抽检通过后的干净数据集
"""
import csv
import json
import re
from collections import defaultdict
from pathlib import Path


BASE = Path(__file__).parent
RAW = BASE / "data" / "qa_dataset_raw.jsonl"
CLEAN = BASE / "data" / "qa_dataset_clean.jsonl"
REPORT_CSV = BASE / "data" / "spot_check.csv"
PAGES = BASE / "corpus" / "pages.jsonl"

NUM_RE = re.compile(r"\d[\d,]*\.?\d*%?")
HEDGE_RE = re.compile(r"以(公司)?公告为准|具体.*请|未披露|不便|请查阅|详见(公司)?公告")


def load_pages() -> dict[tuple[str, int], str]:
    m = defaultdict(str)
    with open(PAGES, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                o = json.loads(line)
                m[(o["doc_id"], o["page"])] = o["text"]
    return m


def norm(s: str) -> str:
    return re.sub(r"[\s,，]", "", s)


def fact_grounded(fact: str, page_norm: str) -> bool:
    nums = [norm(n) for n in NUM_RE.findall(fact)]
    if nums:
        return all(n in page_norm for n in nums)
    # 无数字的定性事实：用双字词重叠度判断（能容忍改写，能识别“凭空编造”）
    chars = re.sub(r"[^\u4e00-\u9fa5]", "", fact)
    if len(chars) < 4:
        return True  # 过短，无法判定，放行给人工
    bigrams = [chars[i:i+2] for i in range(len(chars)-1)]
    hit = sum(1 for b in bigrams if b in page_norm)
    return hit / len(bigrams) >= 0.5


def answer_is_hedged(answer: str) -> bool:
    nums = NUM_RE.findall(answer)
    return (len(nums) == 0) and bool(HEDGE_RE.search(answer))


def main() -> None:
    pages = load_pages()
    raw = [json.loads(l) for l in open(RAW, encoding="utf-8") if l.strip()]
    rows, clean = [], []
    for rec in raw:
        cited = ""
        for c in rec.get("citations", []):
            cited += pages.get((rec["report"], c["page"]), "")
        cited_norm = norm(cited)
        reasons = []
        for k in rec.get("key_facts", []):
            if not fact_grounded(k, cited_norm):
                reasons.append("事实未回源: " + k)
        if answer_is_hedged(rec.get("answer", "")):
            reasons.append("空洞避答(无数据/以公告为准)")
        if not rec.get("citations"):
            reasons.append("无出处页码")
        ok = not reasons
        rows.append({
            "id": rec["id"],
            "report_title": rec["report_title"],
            "page": ",".join(str(c["page"]) for c in rec.get("citations", [])),
            "question": rec["question"],
            "result": "PASS" if ok else "DELETE",
            "missing_facts": " | ".join(reasons),
            "note": "" if ok else "疑似编造/未回源/空洞，删除",
        })
        if ok:
            rec["status"] = "verified"
            clean.append(rec)

    with open(REPORT_CSV, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    with open(CLEAN, "w", encoding="utf-8") as f:
        for rec in clean:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    n_pass = sum(1 for r in rows if r["result"] == "PASS")
    n_del = len(rows) - n_pass
    print(f"抽检完成: 共 {len(rows)} 条, 通过 {n_pass} 条, 删除 {n_del} 条")
    for r in rows:
        if r["result"] == "DELETE":
            print(f"  [删除] {r['id']} {r['report_title']} 第{r['page']}页: {r['missing_facts'][:100]}")
    print(f"记录见 {REPORT_CSV}, 干净数据见 {CLEAN}")


if __name__ == "__main__":
    main()
