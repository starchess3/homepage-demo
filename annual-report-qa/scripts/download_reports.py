#!/usr/bin/env python3
"""从巨潮资讯下载 A 股公司年度报告全文 PDF。

用法:
  python3 scripts/download_reports.py --year 2024 --out data/pdfs
"""
from __future__ import annotations

import argparse
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path


COMPANIES = [
    # (代码, 简称)
    ("300223", "君正股份"),
    ("603986", "兆易创新"),
    ("603501", "韦尔股份"),
    ("688008", "澜起科技"),
    ("688981", "中芯国际"),
    ("002371", "北方华创"),
    ("002049", "紫光国微"),
    ("300782", "卓胜微"),
    ("300661", "圣邦股份"),
    ("600584", "长电科技"),
    ("600460", "士兰微"),
    ("603160", "汇顶科技"),
    ("688396", "华润微"),
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Referer": "http://www.cninfo.com.cn/new/index",
    "X-Requested-With": "XMLHttpRequest",
}


def _get(url: str, data: bytes | None = None, timeout: int = 30):
    req = urllib.request.Request(url, data=data, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def get_org_id(code: str) -> str:
    payload = urllib.parse.urlencode({"keyWord": code, "maxNum": 5}).encode()
    raw = _get("http://www.cninfo.com.cn/new/information/topSearch/query", payload)
    for item in json.loads(raw.decode()):
        if item.get("code") == code:
            return item["orgId"]
    raise RuntimeError(f"未找到 {code} 的 orgId")


def find_annual_report(code: str, org_id: str, year: int) -> tuple[str, str]:
    column = "sse" if code.startswith("6") else "szse"
    form = {
        "pageNum": "1", "pageSize": "30", "column": column,
        "tabName": "fulltext", "plate": "", "stock": f"{code},{org_id}",
        "searchkey": "", "secid": "", "category": "category_ndbg_szsh",
        "trade": "", "seDate": f"{year+1}-01-01~{year+1}-06-30",
        "sortName": "", "sortType": "", "isHLtitle": "true",
    }
    raw = _get(
        "http://www.cninfo.com.cn/new/hisAnnouncement/query",
        urllib.parse.urlencode(form).encode(),
    )
    anns = json.loads(raw.decode()).get("announcements") or []
    key = f"{year}年年度报告"
    for a in anns:
        title = a.get("announcementTitle", "")
        url = a.get("adjunctUrl", "")
        if not url:
            continue
        if key not in title:
            continue
        if any(x in title for x in ("摘要", "英文", "已取消", "问询", "更正", "补充", "审计报告")):
            continue
        return title, "http://static.cninfo.com.cn/" + url
    raise RuntimeError(f"未找到 {code} {year}年年度报告全文")


def download(url: str, dest: Path) -> None:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = resp.read()
    dest.write_bytes(data)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, default=2024)
    ap.add_argument("--out", default=str(Path(__file__).parent.parent / "data" / "pdfs"))
    ap.add_argument("--only", nargs="*", default=None, help="只下载这些代码")
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    companies = [c for c in COMPANIES if not args.only or c[0] in args.only]

    manifest = []
    for i, (code, name) in enumerate(companies, 1):
        dest = out / f"{code}_{name}_{args.year}年报.pdf"
        if dest.exists() and dest.stat().st_size > 0:
            print(f"[{i}/{len(companies)}] {code} {name}: 已存在，跳过")
            manifest.append({"code": code, "name": name, "file": dest.name})
            continue
        try:
            org = get_org_id(code)
            title, url = find_annual_report(code, org, args.year)
            print(f"[{i}/{len(companies)}] {code} {name}: {title} -> 下载中")
            download(url, dest)
            print(f"    已保存 {dest.name} ({dest.stat().st_size/1e6:.1f} MB)")
            manifest.append({"code": code, "name": name, "title": title, "file": dest.name})
        except Exception as e:  # noqa: BLE001
            print(f"[{i}/{len(companies)}] {code} {name}: 失败 - {e}")
        time.sleep(0.6)

    (out / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"完成，清单见 {out / 'manifest.json'}（共 {len(manifest)} 份）")


if __name__ == "__main__":
    main()
