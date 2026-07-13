import json
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse

from teleport_app import TeleportServer


class RelayHandler(BaseHTTPRequestHandler):
    server_version = "QuantumRelay/1.0"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/status":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            payload = {"status": "online"}
            self.wfile.write(json.dumps(payload).encode("utf-8"))
            return
        if parsed.path == "/":
            content = (Path(__file__).parent / "templates" / "index.html").read_text(encoding="utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(content.encode("utf-8"))
            return
        self.send_response(404)
        self.end_headers()

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/relay":
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length)
            data = json.loads(body.decode("utf-8"))
            token = data.get("auth_token", "")
            if self.server.teleport_server.auth_token and token != self.server.teleport_server.auth_token:
                self.send_response(403)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"accepted": False, "reason": "unauthorized"}).encode("utf-8"))
                return
            self.server.teleport_server.messages.append(data.get("message", ""))
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"accepted": True}).encode("utf-8"))
            return
        self.send_response(404)
        self.end_headers()

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return


class RelayWebServer:
    def __init__(self, host: str = "0.0.0.0", port: int = 8080, storage_dir: str = "./teleport_storage") -> None:
        self.host = host
        self.port = port
        self.storage_dir = storage_dir
        self.server = None
        self.thread = None
        self.teleport_server = TeleportServer(storage_dir, host=host, port=9000)

    def start(self) -> None:
        self.teleport_server.start()
        self.server = HTTPServer((self.host, self.port), RelayHandler)
        self.server.teleport_server = self.teleport_server
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        print(f"Web relay running on http://{self.host}:{self.port}")

    def stop(self) -> None:
        if self.server is not None:
            self.server.shutdown()
            self.server.server_close()
        self.teleport_server.stop()


if __name__ == "__main__":
    web = RelayWebServer()
    web.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        web.stop()
