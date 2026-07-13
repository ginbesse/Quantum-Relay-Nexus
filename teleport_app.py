import argparse
import base64
import hashlib
import json
import os
import socket
import threading
import time
import uuid
import zlib
from pathlib import Path
from typing import List, Tuple


class TeleportServer:
    def __init__(self, storage_dir: str, host: str = "0.0.0.0", port: int = 9000, auth_token: str = "") -> None:
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.host = host
        self.port = port
        self.messages: List[str] = []
        self._socket: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self.address: Tuple[str, int] | None = None
        self._running = False
        self.auth_token = auth_token

    def start(self) -> None:
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._socket.bind((self.host, self.port))
        self._socket.listen(8)
        self.address = self._socket.getsockname()
        self._running = True
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()

    def _serve(self) -> None:
        while self._running:
            try:
                conn, _ = self._socket.accept()
            except OSError:
                break
            with conn:
                header = self._recv_exact(conn, 4)
                if not header:
                    continue
                length = int.from_bytes(header, "big")
                payload_bytes = self._recv_exact(conn, length)
                if not payload_bytes:
                    continue
                payload = json.loads(payload_bytes.decode("utf-8"))
                auth = payload.get("auth_token", "")
                if self.auth_token and auth != self.auth_token:
                    conn.sendall(b"NOK")
                    continue
                self._handle_payload(payload)
                conn.sendall(b"ACK")

    def _recv_exact(self, conn: socket.socket, length: int) -> bytes:
        data = b""
        while len(data) < length:
            chunk = conn.recv(length - len(data))
            if not chunk:
                break
            data += chunk
        return data

    def _handle_payload(self, payload: dict) -> None:
        if payload.get("type") == "message":
            self.messages.append(payload["content"])
            return
        if payload.get("type") == "file":
            target = self.storage_dir / payload["filename"]
            target.parent.mkdir(parents=True, exist_ok=True)
            content = payload["content"]
            if isinstance(content, str):
                content_bytes = base64.b64decode(content.encode("ascii"))
            else:
                content_bytes = content
            target.write_bytes(zlib.decompress(content_bytes))
        if payload.get("type") == "directory":
            root = self.storage_dir / payload["dirname"]
            root.mkdir(parents=True, exist_ok=True)
            for item in payload.get("items", []):
                rel_path = item["path"]
                target = root / rel_path
                target.parent.mkdir(parents=True, exist_ok=True)
                content = item["content"]
                if isinstance(content, str):
                    content_bytes = base64.b64decode(content.encode("ascii"))
                else:
                    content_bytes = content
                target.write_bytes(zlib.decompress(content_bytes))
        if payload.get("type") == "chunk":
            target = self.storage_dir / payload["filename"]
            target.parent.mkdir(parents=True, exist_ok=True)
            mode = "ab" if payload.get("chunk_index", 0) > 0 else "wb"
            with target.open(mode) as handle:
                handle.write(zlib.decompress(base64.b64decode(payload["content"].encode("ascii"))))

    def stop(self) -> None:
        self._running = False
        if self._socket is not None:
            try:
                self._socket.close()
            except OSError:
                pass
        if self._thread is not None:
            self._thread.join(timeout=1)


class TeleportClient:
    def __init__(self) -> None:
        self._timeout = 2.0

    def send_message(self, host: str, port: int, message: str) -> None:
        payload = {"type": "message", "content": message}
        self._send_payload(host, port, payload)

    def send_file(self, host: str, port: int, source_path: str, target_name: str) -> None:
        path = Path(source_path)
        content = path.read_bytes()
        payload = {
            "type": "file",
            "filename": target_name,
            "content": base64.b64encode(zlib.compress(content)).decode("ascii"),
        }
        self._send_payload(host, port, payload)

    def send_directory(self, host: str, port: int, source_dir: str, target_name: str, password: str = "") -> None:
        root = Path(source_dir)
        items = []
        for current_root, _, files in os.walk(root):
            for filename in files:
                full_path = Path(current_root) / filename
                rel_path = full_path.relative_to(root).as_posix()
                content = full_path.read_bytes()
                payload_content = base64.b64encode(zlib.compress(content)).decode("ascii")
                items.append({"path": rel_path, "content": payload_content})
        payload = {"type": "directory", "dirname": target_name, "items": items, "password": password}
        self._send_payload(host, port, payload)

    def send_file_chunked(self, host: str, port: int, source_path: str, target_name: str, chunk_size: int = 4096) -> None:
        path = Path(source_path)
        data = path.read_bytes()
        packet_id = str(uuid.uuid4())
        total_chunks = (len(data) + chunk_size - 1) // chunk_size
        for index in range(total_chunks):
            chunk = data[index * chunk_size:(index + 1) * chunk_size]
            payload = {
                "type": "chunk",
                "packet_id": packet_id,
                "chunk_index": index,
                "total_chunks": total_chunks,
                "filename": target_name,
                "content": base64.b64encode(zlib.compress(chunk)).decode("ascii"),
            }
            self._send_payload(host, port, payload)

    def _send_payload(self, host: str, port: int, payload: dict, auth_token: str = "", retries: int = 2) -> None:
        last_error: Exception | None = None
        for attempt in range(retries + 1):
            try:
                with socket.create_connection((host, port), timeout=self._timeout) as conn:
                    payload_with_auth = dict(payload)
                    if auth_token:
                        payload_with_auth["auth_token"] = auth_token
                    data = json.dumps(payload_with_auth).encode("utf-8")
                    header = len(data).to_bytes(4, "big")
                    conn.sendall(header + data)
                    ack = conn.recv(3)
                    if ack != b"ACK":
                        raise RuntimeError("Server did not acknowledge payload")
                    return
            except Exception as exc:  # pragma: no cover - defensive path
                last_error = exc
                time.sleep(0.2)
        if last_error is not None:
            raise last_error


def main() -> None:
    parser = argparse.ArgumentParser(description="A serious inter-server teleport demo for Termux")
    parser.add_argument("--mode", choices=["server", "client"], required=True)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=9000)
    parser.add_argument("--storage", default="./teleport_storage")
    parser.add_argument("--file", default="")
    parser.add_argument("--dir", default="")
    parser.add_argument("--name", default="")
    parser.add_argument("--message", default="")
    parser.add_argument("--target-host", default="")
    parser.add_argument("--target-port", type=int, default=9000)
    parser.add_argument("--password", default="")
    parser.add_argument("--auth-token", default="")
    parser.add_argument("--service", action="store_true", help="Run as a long-lived relay service")
    args = parser.parse_args()

    if args.mode == "server":
        server = TeleportServer(args.storage, host=args.host, port=args.port, auth_token=args.auth_token)
        server.start()
        print(f"Teleport server listening on {server.address}")
        print("Storage directory:", server.storage_dir)
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("Stopping server")
            server.stop()
    else:
        client = TeleportClient()
        if args.service:
            print("Relay service mode enabled")
        if args.message:
            client.send_message(args.target_host or args.host, args.target_port or args.port, args.message)
            print("Message sent")
        if args.file:
            client.send_file(args.target_host or args.host, args.target_port or args.port, args.file, args.name or Path(args.file).name)
            print(f"File sent: {args.file}")
        if args.dir:
            client.send_directory(args.target_host or args.host, args.target_port or args.port, args.dir, args.name or Path(args.dir).name, password=args.password)
            print(f"Directory sent: {args.dir}")


if __name__ == "__main__":
    main()
