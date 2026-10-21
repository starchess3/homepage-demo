from __future__ import annotations

import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


EXTENSION_CATEGORIES = {
    "data": {".csv", ".tsv", ".json", ".xlsx", ".xls", ".db", ".sqlite", ".parquet", ".feather"},
    "code": {
        ".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".c", ".cpp", ".h", ".go",
        ".rs", ".rb", ".php", ".swift", ".sh", ".zsh", ".bash", ".ipynb",
    },
    "docs": {".md", ".txt", ".pdf", ".doc", ".docx", ".rtf", ".pages", ".pptx", ".ppt"},
    "media": {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".mp4", ".mov", ".mp3", ".wav"},
    "config": {".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf", ".env"},
}


def _classify(path: Path) -> str:
    if path.name == "SKILL.md" or ".codex/skills" in str(path):
        return "skill"
    suffix = path.suffix.lower()
    for category, suffixes in EXTENSION_CATEGORIES.items():
        if suffix in suffixes:
            return category
    return "other"


def _scan_skills(home: Path) -> list[dict]:
    """专门扫描 Codex 技能目录，补充技能地图，避免被通用排除规则漏掉。"""
    skills_root = home / ".codex" / "skills"
    if not skills_root.exists():
        return []
    entries = []
    for skill_file in skills_root.rglob("SKILL.md"):
        try:
            stat = skill_file.stat()
        except OSError:
            continue
        entries.append(
            {
                "path": str(skill_file.relative_to(home)),
                "root": str(home),
                "category": "skill",
                "extension": ".md",
                "size": stat.st_size,
                "mtime": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
            }
        )
    return entries


def inventory(config: dict) -> Path:
    inventory_config = config["inventory"]
    roots = inventory_config.get("roots", ["~"])
    exclude_dirs = set(inventory_config.get("exclude_dirs", []))
    max_files = int(inventory_config.get("max_files", 20000))
    max_depth = int(inventory_config.get("max_depth", 8))
    max_file_bytes = int(inventory_config.get("max_file_bytes", 10 * 1024 * 1024))

    entries = []
    dir_counter = Counter()
    category_counter = Counter()
    skipped = 0

    for root in roots:
        root_path = Path(root).expanduser().resolve()
        if not root_path.exists():
            print(f"跳过不存在的目录：{root_path}")
            continue

        for current_dir, dirs, files in os.walk(root_path, topdown=True, followlinks=False):
            relative_dir = Path(current_dir)
            depth = len(relative_dir.relative_to(root_path).parts)
            dirs[:] = sorted(
                d for d in dirs if d not in exclude_dirs and not d.startswith(".")
                if depth < max_depth
            )

            for filename in files:
                if len(entries) >= max_files:
                    break
                path = Path(current_dir) / filename
                try:
                    stat = path.stat()
                except OSError:
                    skipped += 1
                    continue
                if stat.st_size > max_file_bytes:
                    continue
                if path.is_symlink():
                    continue

                category = _classify(path)
                try:
                    rel = str(path.relative_to(root_path))
                except ValueError:
                    rel = str(path)
                entry = {
                    "path": rel,
                    "root": str(root_path),
                    "category": category,
                    "extension": path.suffix.lower(),
                    "size": stat.st_size,
                    "mtime": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                }
                entries.append(entry)
                category_counter[category] += 1
                dir_counter[str(relative_dir)] += 1

            if len(entries) >= max_files:
                break

    home = Path.home()
    skill_entries = _scan_skills(home)
    entries.extend(skill_entries)
    for entry in skill_entries:
        category_counter[entry["category"]] += 1
        dir_counter[str(Path(entry["root"]) / Path(entry["path"]).parent)] += 1

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "roots": [str(Path(r).expanduser().resolve()) for r in roots],
        "total_files": len(entries),
        "skipped_unreadable": skipped,
        "by_category": dict(category_counter),
        "top_directories": dir_counter.most_common(20),
        "entries": entries,
    }

    output_file = Path(config["_data_dir"]) / "inventory.json"
    output_file.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已盘点 {len(entries)} 个文件，输出到 {output_file}")
    return output_file
