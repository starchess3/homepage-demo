from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


def _load_latest_external(data_dir: Path) -> dict | None:
    external_dir = data_dir / "external"
    files = sorted(external_dir.glob("*.json"))
    if not files:
        return None
    return json.loads(files[-1].read_text(encoding="utf-8"))


_LATIN_STOPWORDS = {
    "the", "and", "for", "with", "from", "your", "this", "that", "http",
    "https", "com", "www", "app", "how", "what", "you", "are", "was",
    "not", "can", "will", "new", "post", "prime", "story", "frame",
}

_CHINESE_STOPWORDS = {
    "一个", "如何", "自己", "以及", "可以", "没有", "什么", "怎么", "这个",
    "那个", "我们", "你们", "他们", "还是", "但是", "因为", "所以", "如果",
    "就是", "已经", "时候", "现在", "这些", "那些", "可能", "应该", "需要",
    "不会", "不能", "不是", "或者", "而且", "并且", "不过", "只是", "还有",
    "一样", "一些", "值得", "关注", "近期", "开始", "进行", "相关", "内容",
}

_NOISE_DIRS = {
    "Contents", "Frameworks", "Resources", "Libraries", "Helpers", "Versions",
    "Headers", "bin", "node_modules", ".git", "__pycache__", "Sparkle.framework",
}

_CATEGORY_PRIORITY = {
    "docs": 1, "data": 2, "skill": 3, "code": 4, "config": 5, "media": 6, "other": 7,
}


def _terms(titles: list[str]) -> Counter:
    counter = Counter()
    for title in titles:
        latin_words = re.findall(r"[A-Za-z][A-Za-z0-9+#-]{2,}", title.lower())
        for word in latin_words:
            if word not in _LATIN_STOPWORDS:
                counter[word] += 1

        chinese = re.sub(r"[^\u4e00-\u9fff]", "", title)
        for i in range(len(chinese) - 1):
            bigram = chinese[i:i + 2]
            if bigram not in _CHINESE_STOPWORDS:
                counter[bigram] += 1
    return counter


def _entry_text(entry: dict) -> str | None:
    parts = [part for part in entry["path"].split("/") if part]
    if not parts:
        return None
    if any(part.endswith(".app") for part in parts):
        return None
    if any(part in _NOISE_DIRS for part in parts):
        return None
    if parts[-1].startswith("."):
        return None
    return " ".join(parts)


def _related_entries(entries: list[dict], terms: Counter, limit: int = 20) -> list[tuple[dict, list[str]]]:
    top_terms = [term for term, _ in terms.most_common(60)]
    scored = []
    for entry in entries:
        text = _entry_text(entry)
        if not text:
            continue
        haystack = text.lower()
        matched = []
        for term in top_terms:
            if term.isascii():
                if re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", haystack):
                    matched.append(term)
            elif term in haystack:
                matched.append(term)
        if matched:
            priority = _CATEGORY_PRIORITY.get(entry["category"], 7)
            scored.append((len(matched), -priority, matched, entry))

    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [(item[3], item[2]) for item in scored[:limit]]


def _money(value: float) -> str:
    if abs(value) >= 1e8:
        return f"{value / 1e8:.2f} 亿元"
    if abs(value) >= 1e4:
        return f"{value / 1e4:.0f} 万元"
    return f"{value:.0f} 元"


def _analyze_external(items: list[dict]) -> list[str]:
    lines: list[str] = []
    structured = [item for item in items if isinstance(item.get("data"), dict) and "close" in item["data"]]
    if not structured:
        return lines

    ordered = sorted(structured, key=lambda item: str(item.get("published", "")))
    closes = [item["data"]["close"] for item in ordered if item["data"].get("close")]
    latest = ordered[-1]["data"]

    lines.append("## 数据源分析")
    lines.append("")
    if len(closes) >= 2:
        first, last = closes[0], closes[-1]
        total_change = (last - first) / first * 100 if first else 0.0
        up_days = sum(1 for a, b in zip(closes, closes[1:]) if b > a)
        down_days = sum(1 for a, b in zip(closes, closes[1:]) if b < a)
        trend = "上涨" if total_change > 0 else ("下跌" if total_change < 0 else "震荡")
        lines.append(f"- 观察期内收盘价：{first:.2f} → {last:.2f}，累计涨跌 {total_change:+.2f}%")
        lines.append(f"- 上涨 {up_days} 天，下跌 {down_days} 天，整体呈{trend}走势")
    else:
        lines.append(f"- 最新收盘价：{latest.get('close', 0):.2f}")

    if "main_net" in latest:
        main_net = latest["main_net"]
        super_big = latest.get("super_net", 0) + latest.get("big_net", 0)
        mid_small = latest.get("mid_net", 0) + latest.get("small_net", 0)
        direction = "净流入" if main_net >= 0 else "净流出"
        lines.append(f"- 最新交易日主力资金{direction} {_money(main_net)}")
        lines.append(f"- 超大单+大单净额 {_money(super_big)}，中单+小单净额 {_money(mid_small)}")

        if main_net >= 0 and mid_small >= 0:
            conclusion = "主力与中小单同时净流入，资金面偏积极。"
        elif main_net >= 0 and mid_small < 0:
            conclusion = "主力净流入、中小单净流出，资金向大单集中。"
        elif main_net < 0 and mid_small >= 0:
            conclusion = "主力净流出、中小单净流入，需警惕大资金逢高减持。"
        else:
            conclusion = "主力与中小单同时净流出，资金面偏弱。"
    else:
        conclusion = "当前数据源暂无资金流字段，仅有价格数据。"

    lines.append("")
    lines.append("### 一句话结论")
    lines.append("")
    lines.append(f"- {conclusion}")
    return lines


def analyze(config: dict) -> Path:
    data_dir = Path(config["_data_dir"])
    output_dir = Path(config["_output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)

    external = _load_latest_external(data_dir)
    inventory_path = data_dir / "inventory.json"
    inventory_data = None
    if inventory_path.exists():
        inventory_data = json.loads(inventory_path.read_text(encoding="utf-8"))

    lines = []
    lines.append("# 个人自动化 agent 分析报告")
    lines.append("")
    lines.append(f"- 生成时间：{datetime.now(timezone.utc).isoformat()}")

    if external:
        items = external.get("new_items") or external.get("items") or []
        all_items = external.get("items") or items
        lines.append(f"- 外部数据：本次新增 {len(external.get('new_items') or [])} 条 / 抓取 {len(external.get('items') or [])} 条")
        lines.append("")
        lines.append("## 外部输入摘要")
        lines.append("")
        for item in items[:10]:
            title = (item.get("title") or "").strip()
            link = (item.get("link") or "").strip()
            lines.append(f"- {title}（{link}）")
        lines.append("")
        lines.extend(_analyze_external(all_items))
    else:
        lines.append("- 外部数据：暂无（请先运行 ingest）")

    if inventory_data:
        lines.append("")
        lines.append("## 本地资产地图")
        lines.append("")
        lines.append(f"- 文件总数：{inventory_data['total_files']}")
        lines.append("- 分类统计：" + "，".join(f"{k} {v}" for k, v in inventory_data["by_category"].items()))
        lines.append("")
        lines.append("### 高频目录")
        lines.append("")
        for directory, count in inventory_data["top_directories"][:10]:
            lines.append(f"- {count} 个文件：{directory}")

        if external:
            items = external.get("new_items") or external.get("items") or []
            terms = _terms([item.get("title", "") for item in items])
            matched = _related_entries(inventory_data["entries"], terms)
            lines.append("")
            lines.append("## 与外部输入相关的本地文件")
            lines.append("")
            if matched:
                for entry, matched_terms in matched:
                    terms_label = "、".join(matched_terms[:6])
                    lines.append(f"- [{entry['category']}] {entry['path']}（匹配：{terms_label}）")
            else:
                lines.append("- 未发现明显相关文件。")

    lines.append("")
    lines.append("## 下一步建议")
    lines.append("")
    lines.append("- 若外部数据为空，检查 config.json 中的数据源地址。")
    lines.append("- 若要开启邮件投递，配置 config.json 的 email 字段并设置密码环境变量。")
    lines.append("- 运行 `python3 run.py schedule` 生成定时任务配置。")

    output_file = output_dir / "report.md"
    output_file.write_text("\n".join(lines), encoding="utf-8")
    print(f"分析报告已生成：{output_file}")
    return output_file
