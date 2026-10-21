from __future__ import annotations

import copy
import json
from pathlib import Path


DEFAULT_CONFIG = {
    "data_dir": "data",
    "output_dir": "output",
    "external_source": {
        "type": "rss",
        "url": "https://sspai.com/feed",
        "limit": 10,
    },
    "inventory": {
        "roots": ["~"],
        "exclude_dirs": [
            "Library",
            ".Trash",
            ".cache",
            ".npm",
            ".cargo",
            ".rustup",
            ".conda",
            ".pyenv",
            ".virtualenvs",
            "node_modules",
            ".git",
            ".venv",
            "venv",
            "__pycache__",
            "Applications",
            "System",
            "private",
            ".local",
            ".codex",
            ".agents",
        ],
        "max_files": 20000,
        "max_depth": 8,
        "max_file_bytes": 10 * 1024 * 1024,
    },
    "email": {
        "enabled": False,
        "smtp_host": "",
        "smtp_port": 587,
        "username": "",
        "password_env": "AGENT_EMAIL_PASSWORD",
        "from": "",
        "to": "",
    },
    "schedule": {
        "interval_seconds": 6 * 60 * 60,
        "launch_agent_label": "com.user.personal-agent",
    },
}


def _deep_update(base: dict, override: dict) -> None:
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _deep_update(base[key], value)
        else:
            base[key] = value


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def load(config_path: str = "config.json") -> dict:
    root = project_root()
    path = Path(config_path)
    if not path.is_absolute():
        path = root / path

    config = copy.deepcopy(DEFAULT_CONFIG)
    if path.exists():
        user_config = json.loads(path.read_text(encoding="utf-8"))
        _deep_update(config, user_config)

    config["_project_root"] = str(root)
    config["_config_path"] = str(path)

    data_dir = Path(config["data_dir"]).expanduser()
    output_dir = Path(config["output_dir"]).expanduser()
    if not data_dir.is_absolute():
        data_dir = root / data_dir
    if not output_dir.is_absolute():
        output_dir = root / output_dir
    config["_data_dir"] = str(data_dir)
    config["_output_dir"] = str(output_dir)
    return config


def expand_home(path: str) -> str:
    return str(Path(path).expanduser())
