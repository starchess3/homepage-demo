#!/usr/bin/env python3
"""极简问答服务：stdlib http.server，无需 flask。

GET /query?q=...  返回混合检索 top-k 的带出处块（JSON）。
其余路径返回 app/index.html 静态页。
"""
from __future__ import annotations

import json
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from indexer import HybridIndex, load_chunks  # noqa: E402


CHUNKS_PATH = Path(__file__).parent.parent / "data" / "chunks.jsonl"
INDEX = HybridIndex(load_chunks(str(CHUNKS_PATH)))


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/query":
            q = urllib.parse.parse_qs(parsed.query).get("q", [""])[0]
            hits = INDEX.query(q, top_k=6)
            body = json.dumps({"query": q, "hits": hits}, ensure_ascii=False).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        html = (Path(__file__).parent / "index.html").read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(html)))
        self.end_headers()
        self.wfile.write(html)

    def log_message(self, *args):  # 静默日志
        pass


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    print(f"服务启动: http://localhost:{port}  (索引已加载，{len(INDEX.records)} 块)")
    HTTPServer(("127.0.0.1", port), Handler).serve_forever()
