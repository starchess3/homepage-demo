#!/usr/bin/env python3
"""生成两张页面截图（需要 playwright + chromium，且能在本机启动浏览器）。

在本机运行（不受沙箱限制时）:
  pip install playwright && python3 -m playwright install chromium
  python3 scripts/screenshot.py          # 会先确认 app/server.py 已启动在 8765

输出:
  output/screenshots/qa_page.png        # 问答页（带一次真实查询）
  output/screenshots/eval_results.png   # 10 题评测结果页
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent


def main() -> None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        sys.exit("缺少 playwright，请先 pip install playwright && python3 -m playwright install chromium")

    out = ROOT / "output" / "screenshots"
    out.mkdir(parents=True, exist_ok=True)
    q = "%E4%B8%AD%E8%8A%AF%E5%9B%BD%E9%99%852024%E5%B9%B4%E8%90%A5%E4%B8%9A%E6%94%B6%E5%85%A5%E5%92%8C%E5%BD%92%E6%AF%8D%E5%87%80%E5%88%A9%E6%B6%A6"
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1400, "height": 900})
        pg.goto((ROOT / "output" / "eval_results.html").as_uri())
        pg.wait_for_timeout(500)
        pg.screenshot(path=str(out / "eval_results.png"), full_page=True)
        pg.close()

        pg = b.new_page(viewport={"width": 1100, "height": 1300})
        pg.goto("http://localhost:8765/?q=" + q)
        pg.wait_for_selector("#out .qa", timeout=15000)
        pg.wait_for_timeout(800)
        pg.screenshot(path=str(out / "qa_page.png"), full_page=True)
        pg.close()
        b.close()
    print("已生成：", out / "qa_page.png", "与", out / "eval_results.png")


if __name__ == "__main__":
    main()
