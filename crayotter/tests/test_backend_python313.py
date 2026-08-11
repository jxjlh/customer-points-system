from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.request import urlopen


CRAYOTTER_ROOT = Path(__file__).resolve().parents[1]
sys.path = [entry for entry in sys.path if Path(entry or ".").resolve() != CRAYOTTER_ROOT]
sys.path.insert(0, str(CRAYOTTER_ROOT))


class BackendPython313Tests(unittest.TestCase):
    def test_backend_imports_and_serves_health(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            os.environ["CRAYOTTER_RUNTIME_ROOT"] = tmp_dir
            from app.backend.server import build_http_server

            server = build_http_server("127.0.0.1", 0)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                host, port = server.server_address
                with urlopen(f"http://{host}:{port}/health", timeout=5) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                self.assertEqual(response.status, 200)
                self.assertEqual(payload, {"ok": True})
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

    def test_multipart_parser_reads_uploaded_file_without_cgi(self) -> None:
        from app.backend.server import parse_multipart_files

        boundary = "----codex-boundary"
        body = (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="files"; filename="素材.mp4"\r\n'
            "Content-Type: video/mp4\r\n\r\n"
        ).encode("utf-8") + b"video-bytes" + f"\r\n--{boundary}--\r\n".encode("utf-8")

        files = parse_multipart_files(
            f"multipart/form-data; boundary={boundary}",
            body,
        )

        self.assertEqual(files, [("素材.mp4", b"video-bytes")])


if __name__ == "__main__":
    unittest.main()
