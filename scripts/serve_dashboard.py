"""Serve dashboard/public locally with correct MIME types (Windows' registry maps .js to text/plain, which breaks ES modules).
  python scripts/serve_dashboard.py 8100      ->  http://localhost:8100/index.html?as=guest
The page talks to the deployed API by default; add ?api=http://localhost:8080 to use a local `python main.py` instead."""
import http.server
import os
import socketserver
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "dashboard", "public")
TYPES = {".js": "text/javascript", ".json": "application/json", ".css": "text/css", ".html": "text/html"}


class Handler(http.server.SimpleHTTPRequestHandler):
    extensions_map = {**http.server.SimpleHTTPRequestHandler.extensions_map, **TYPES}

    def __init__(self, *a, **kw):
        super().__init__(*a, directory=ROOT, **kw)

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8100
    socketserver.ThreadingTCPServer.allow_reuse_address = True
    print(f"Serving {os.path.abspath(ROOT)} on http://localhost:{port}/index.html")
    socketserver.ThreadingTCPServer(("", port), Handler).serve_forever()
