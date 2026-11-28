"""Serve the read-only evaluation viewer on localhost."""

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote

UI = Path(__file__).resolve().parent
RESULTS = UI.parent / "results"
ASSETS = {
    "/": ("index.html", "text/html"),
    "/app.js": ("app.js", "text/javascript"),
    "/styles.css": ("styles.css", "text/css"),
}


def result_file(path: Path) -> bool:
    return not path.name.startswith(".") and not path.is_symlink() and path.is_file()


def list_results() -> list[dict[str, str | int]]:
    files = []
    for path in RESULTS.iterdir() if RESULTS.is_dir() else ():
        if result_file(path):
            try:
                stat = path.stat()
            except FileNotFoundError:
                continue
            files.append((stat.st_mtime_ns, path.name, stat.st_size))
    return [
        {"name": name, "size": size} for _, name, size in sorted(files, reverse=True)
    ]


class Viewer(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        server = self.server
        assert isinstance(server, ThreadingHTTPServer)
        host = self.headers.get("Host", "")
        port = server.server_port
        if host not in (f"127.0.0.1:{port}", f"localhost:{port}"):
            self.send_error(400)
            return
        route = self.path.partition("?")[0]
        try:
            if route in ASSETS:
                filename, media_type = ASSETS[route]
                self.send_content((UI / filename).read_bytes(), media_type)
            elif route == "/api/files":
                self.send_content(
                    json.dumps(list_results()).encode(), "application/json"
                )
            elif route.startswith("/api/files/"):
                name = unquote(route.removeprefix("/api/files/"))
                if not name or name != Path(name).name or "\0" in name:
                    self.send_error(404)
                    return
                path = RESULTS / name
                if not result_file(path):
                    self.send_error(404)
                    return
                self.send_content(path.read_bytes(), "text/plain")
            else:
                self.send_error(404)
        except FileNotFoundError:
            self.send_error(404)
        except (OSError, ValueError):
            self.send_error(500)

    def send_content(self, body: bytes, media_type: str) -> None:
        self.send_response(200)
        self.send_header("Content-Type", f"{media_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; base-uri 'none'; frame-ancestors 'none'; object-src 'none'",
        )
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    with ThreadingHTTPServer(("127.0.0.1", args.port), Viewer) as server:
        print(
            f"Eval results viewer at http://127.0.0.1:{server.server_port}", flush=True
        )
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
