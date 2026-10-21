from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parent
WEB_DIR = ROOT / "web"
PORT = 8765


def _latest_external() -> dict:
    files = sorted((ROOT / "data" / "external").glob("*.json"))
    if not files:
        return {}
    return json.loads(files[-1].read_text(encoding="utf-8"))


def _inventory_summary() -> dict:
    path = ROOT / "data" / "inventory.json"
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {
        "generated_at": data.get("generated_at"),
        "total_files": data.get("total_files"),
        "by_category": data.get("by_category"),
        "top_directories": data.get("top_directories", [])[:8],
    }


def _log_tail(limit: int = 40) -> str:
    path = ROOT / "output" / "agent.log"
    if not path.exists():
        return "暂无运行日志"
    lines = path.read_text(encoding="utf-8").splitlines()
    return "\n".join(lines[-limit:])


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path == "/api/latest":
            self._send_json(_latest_external())
        elif self.path == "/api/inventory":
            self._send_json(_inventory_summary())
        elif self.path == "/api/log":
            self._send_json({"log": _log_tail()})
        else:
            self._serve_static()

    def _send_json(self, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_static(self) -> None:
        relative = self.path.lstrip("/") or "index.html"
        if relative.startswith("api/"):
            self.send_error(404)
            return
        file_path = (WEB_DIR / relative).resolve()
        if WEB_DIR not in file_path.parents and file_path != WEB_DIR:
            self.send_error(403)
            return
        if not file_path.exists() or not file_path.is_file():
            self.send_error(404)
            return
        content = file_path.read_bytes()
        content_type = "text/html"
        if file_path.suffix == ".css":
            content_type = "text/css"
        elif file_path.suffix == ".js":
            content_type = "application/javascript"
        elif file_path.suffix == ".svg":
            content_type = "image/svg+xml"
        self.send_response(200)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def log_message(self, format: str, *args) -> None:
        return


def main() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"监控台已启动：http://127.0.0.1:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("已停止")


if __name__ == "__main__":
    main()
