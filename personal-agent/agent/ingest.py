from __future__ import annotations

import hashlib
import json
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path


USER_AGENT = "personal-agent/1.0 (homework demo)"


def _jsonp_payload(text: str) -> dict:
    start = text.find("(")
    end = text.rfind(")")
    if start == -1 or end <= start:
        raise ValueError("not a JSONP response")
    return json.loads(text[start + 1:end])


def _text_of(element: ET.Element, tag: str) -> str:
    for child in element.iter():
        if child.tag.rsplit("}", 1)[-1] == tag and child.text:
            return child.text.strip()
    return ""


def fetch_rss(url: str, limit: int) -> list[dict]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=20) as response:
        payload = response.read()
    root = ET.fromstring(payload)
    items = []
    for node in root.iter("item"):
        items.append(
            {
                "title": _text_of(node, "title"),
                "link": _text_of(node, "link"),
                "description": _text_of(node, "description"),
                "published": _text_of(node, "pubDate"),
            }
        )
        if len(items) >= limit:
            break
    return items


def _normalize_api_record(record: dict) -> dict:
    return {
        "title": record.get("title") or record.get("name") or "",
        "link": record.get("link") or record.get("url") or "",
        "description": record.get("description") or record.get("summary") or "",
        "published": record.get("published") or record.get("created_at") or "",
    }


def fetch_api(url: str, limit: int) -> list[dict]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=20) as response:
        payload = response.read()
    data = json.loads(payload.decode("utf-8"))
    if isinstance(data, list):
        records = data
    elif isinstance(data, dict):
        records = data.get("items") or data.get("data") or data.get("results") or []
    else:
        records = []
    return [_normalize_api_record(item) for item in records[:limit]]


def fetch_ths_line(code: str, limit: int) -> list[dict]:
    url = f"http://d.10jqka.com.cn/v6/line/hs_{code}/01/last.js"
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=20) as response:
        payload = response.read().decode("utf-8", "replace")
    obj = _jsonp_payload(payload)
    records = []
    for row in obj.get("data", "").split(";"):
        parts = row.split(",")
        if len(parts) < 7 or not all(parts[:5]):
            continue
        records.append(
            {
                "date": parts[0],
                "open": float(parts[1]),
                "high": float(parts[2]),
                "low": float(parts[3]),
                "close": float(parts[4]),
                "volume": float(parts[5] or 0),
                "amount": float(parts[6] or 0),
            }
        )
    return records[-limit:]


def fetch_ths_fundflow(code: str) -> dict:
    url = f"http://d.10jqka.com.cn/v2/realhead/hs_{code}/last.js"
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=20) as response:
        payload = response.read().decode("utf-8", "replace")
    obj = _jsonp_payload(payload)
    items = obj.get("items", {})

    def num(key: str) -> float:
        try:
            return float(items.get(key, "0"))
        except (TypeError, ValueError):
            return 0.0

    super_in, super_out = num("223"), num("224")
    big_in, big_out = num("225"), num("226")
    mid_in, mid_out = num("237"), num("238")
    small_in, small_out = num("259"), num("260")
    return {
        "name": items.get("name", code),
        "price": num("10"),
        "prev_close": num("7"),
        "high": num("8"),
        "low": num("9"),
        "volume": num("13"),
        "amount": num("19"),
        "super_net": super_in - super_out,
        "big_net": big_in - big_out,
        "mid_net": mid_in - mid_out,
        "small_net": small_in - small_out,
        "main_net": (super_in - super_out) + (big_in - big_out),
        "total_net": (super_in - super_out) + (big_in - big_out) + (mid_in - mid_out) + (small_in - small_out),
        "time": (items.get("time") or "").strip(),
    }


def fetch_ths(source: dict) -> list[dict]:
    code = str(source.get("code", "")).zfill(6)
    name = source.get("name") or code
    limit = int(source.get("limit", 5))
    line_records = fetch_ths_line(code, max(limit, 1))
    fund = fetch_ths_fundflow(code)
    latest_date = fund["time"].split()[0].replace("-", "") if fund["time"] else ""
    if latest_date and (not line_records or line_records[-1]["date"] < latest_date):
        line_records.append(
            {
                "date": latest_date,
                "open": fund["prev_close"],
                "high": fund["high"],
                "low": fund["low"],
                "close": fund["price"],
                "volume": fund["volume"],
                "amount": fund["amount"],
            }
        )

    items = []
    for index, record in enumerate(line_records):
        parts = [
            f"收盘价 {record['close']:.2f}",
            f"最高 {record['high']:.2f}",
            f"最低 {record['low']:.2f}",
            f"成交量 {record['volume']:.0f}",
            f"成交额 {record['amount']:.0f}",
        ]
        if index == len(line_records) - 1:
            change = 0.0
            if record["close"] and fund["prev_close"]:
                change = (record["close"] - fund["prev_close"]) / fund["prev_close"] * 100
            parts.extend(
                [
                    f"涨跌幅 {change:.2f}%",
                    f"主力净流入 {fund['main_net']:.0f}",
                    f"超大单净流入 {fund['super_net']:.0f}",
                    f"大单净流入 {fund['big_net']:.0f}",
                    f"中单净流入 {fund['mid_net']:.0f}",
                    f"小单净流入 {fund['small_net']:.0f}",
                ]
            )
            data = {
                "close": record["close"],
                "high": record["high"],
                "low": record["low"],
                "volume": record["volume"],
                "amount": record["amount"],
                "change_pct": change,
                "main_net": fund["main_net"],
                "super_net": fund["super_net"],
                "big_net": fund["big_net"],
                "mid_net": fund["mid_net"],
                "small_net": fund["small_net"],
            }
        else:
            data = {
                "close": record["close"],
                "high": record["high"],
                "low": record["low"],
                "volume": record["volume"],
                "amount": record["amount"],
            }
        items.append(
            {
                "title": f"{name} {record['date']} 收盘 {record['close']:.2f}",
                "link": f"ths:{code}:{record['date']}",
                "description": "，".join(parts),
                "published": record["date"],
                "data": data,
            }
        )
    return items


def _item_id(item: dict) -> str:
    key = item.get("link") or item.get("title") or json.dumps(item, ensure_ascii=False)
    return hashlib.sha1(key.encode("utf-8")).hexdigest()


def ingest(config: dict) -> Path:
    source = config["external_source"]
    source_type = source.get("type", "rss")
    limit = int(source.get("limit", 10))

    if source_type == "ths":
        items = fetch_ths(source)
    elif source_type == "api":
        items = fetch_api(source["url"], limit)
    else:
        items = fetch_rss(source["url"], limit)

    data_dir = Path(config["_data_dir"])
    external_dir = data_dir / "external"
    external_dir.mkdir(parents=True, exist_ok=True)
    seen_file = data_dir / "seen.json"

    seen = set()
    if seen_file.exists():
        seen = set(json.loads(seen_file.read_text(encoding="utf-8")))

    new_items = []
    for item in items:
        item_id = _item_id(item)
        if item_id not in seen:
            seen.add(item_id)
            new_items.append(item)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_file = external_dir / f"{timestamp}.json"
    output_file.write_text(
        json.dumps(
            {
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "source": source,
                "items": items,
                "new_items": new_items,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    seen_file.write_text(json.dumps(sorted(seen), ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已抓取 {len(items)} 条，新增 {len(new_items)} 条，输出到 {output_file}")
    return output_file
