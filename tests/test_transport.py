import tempfile
import unittest
from pathlib import Path

from teleport_app import TeleportClient, TeleportServer


class TransportTests(unittest.TestCase):
    def test_file_and_message_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            storage_dir = tmp_path / "storage"
            storage_dir.mkdir()

            server = TeleportServer(str(storage_dir), host="127.0.0.1", port=0)
            server.start()
            try:
                host, port = server.address

                source_file = tmp_path / "payload.txt"
                source_file.write_text("teleport works\n", encoding="utf-8")

                client = TeleportClient()
                client.send_file(host, port, str(source_file), "payload.txt")
                client.send_message(host, port, "hello from client")

                self.assertTrue((storage_dir / "payload.txt").exists())
                self.assertEqual((storage_dir / "payload.txt").read_text(encoding="utf-8"), "teleport works\n")
                self.assertEqual(server.messages[-1], "hello from client")
            finally:
                server.stop()

    def test_directory_roundtrip_with_password(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            storage_dir = tmp_path / "storage"
            storage_dir.mkdir()

            server = TeleportServer(str(storage_dir), host="127.0.0.1", port=0)
            server.start()
            try:
                host, port = server.address

                source_dir = tmp_path / "future_bundle"
                source_dir.mkdir()
                (source_dir / "core.txt").write_text("future core\n", encoding="utf-8")
                nested = source_dir / "nested"
                nested.mkdir()
                (nested / "node.txt").write_text("relay node\n", encoding="utf-8")

                client = TeleportClient()
                client.send_directory(host, port, str(source_dir), "future_bundle", password="lattice")

                self.assertTrue((storage_dir / "future_bundle" / "core.txt").exists())
                self.assertTrue((storage_dir / "future_bundle" / "nested" / "node.txt").exists())
                self.assertEqual((storage_dir / "future_bundle" / "core.txt").read_text(encoding="utf-8"), "future core\n")
                self.assertEqual((storage_dir / "future_bundle" / "nested" / "node.txt").read_text(encoding="utf-8"), "relay node\n")
            finally:
                server.stop()

    def test_chunked_transfer_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            storage_dir = tmp_path / "storage"
            storage_dir.mkdir()

            server = TeleportServer(str(storage_dir), host="127.0.0.1", port=0)
            server.start()
            try:
                host, port = server.address

                source_file = tmp_path / "chunked.bin"
                source_file.write_bytes(b"A" * 20000)

                client = TeleportClient()
                client.send_file_chunked(host, port, str(source_file), "chunked.bin", chunk_size=4096)

                self.assertTrue((storage_dir / "chunked.bin").exists())
                self.assertEqual((storage_dir / "chunked.bin").read_bytes(), b"A" * 20000)
            finally:
                server.stop()

    def test_retry_and_auth_header(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            storage_dir = tmp_path / "storage"
            storage_dir.mkdir()

            server = TeleportServer(str(storage_dir), host="127.0.0.1", port=0)
            server.start()
            try:
                host, port = server.address

                client = TeleportClient()
                payload = {"type": "message", "content": "secure relay"}
                client._send_payload(host, port, payload, auth_token="neo")

                self.assertEqual(server.messages[-1], "secure relay")
            finally:
                server.stop()


if __name__ == "__main__":
    unittest.main()
