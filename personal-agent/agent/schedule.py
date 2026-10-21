from __future__ import annotations

import plistlib
from pathlib import Path


def generate_plist(config: dict) -> Path:
    project_root = Path(config["_project_root"])
    output_dir = Path(config["_output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)
    label = config["schedule"]["launch_agent_label"]
    hour, minute = (int(part) for part in config["schedule"]["time"].split(":"))
    weekdays = [int(day) for day in config["schedule"].get("weekdays", [1, 2, 3, 4, 5])]

    calendar_intervals = [{"Hour": hour, "Minute": minute, "Weekday": day} for day in weekdays]

    plist = {
        "Label": label,
        "ProgramArguments": [
            "/usr/local/bin/python3",
            str(project_root / "run.py"),
            "run",
        ],
        "WorkingDirectory": str(project_root),
        "StartCalendarInterval": calendar_intervals,
        "RunAtLoad": False,
        "StandardOutPath": str(output_dir / "agent.log"),
        "StandardErrorPath": str(output_dir / "agent.error.log"),
    }
    output_file = output_dir / f"{label}.plist"
    output_file.write_bytes(plistlib.dumps(plist))
    print(f"已生成 LaunchAgent 配置：{output_file}")
    print(f"安装命令：cp '{output_file}' ~/Library/LaunchAgents/ && launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/{label}.plist && launchctl enable gui/$(id -u)/{label}")
    return output_file
