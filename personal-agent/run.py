from __future__ import annotations

import argparse

from agent.analyze import analyze
from agent.config import load
from agent.ingest import ingest
from agent.inventory import inventory
from agent.notify import notify
from agent.schedule import generate_plist


def main() -> None:
    parser = argparse.ArgumentParser(description="个人自动化 agent")
    parser.add_argument("command", choices=["ingest", "inventory", "analyze", "run", "schedule"])
    parser.add_argument("-c", "--config", default="config.json", help="配置文件路径")
    args = parser.parse_args()

    config = load(args.config)

    if args.command == "ingest":
        ingest(config)
    elif args.command == "inventory":
        inventory(config)
    elif args.command == "analyze":
        analyze(config)
    elif args.command == "run":
        ingest(config)
        inventory(config)
        report_path = analyze(config)
        notify(config, report_path)
    elif args.command == "schedule":
        generate_plist(config)


if __name__ == "__main__":
    main()
