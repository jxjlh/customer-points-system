from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from modules.crayotter_client import (
    CrayotterClient,
    build_backend_startup_source,
    merge_profile_config,
    safe_upload_name,
    save_uploaded_files,
)


class UploadedFileStub:
    def __init__(self, name: str, payload: bytes) -> None:
        self.name = name
        self._payload = payload

    def getbuffer(self) -> memoryview:
        return memoryview(self._payload)


class CrayotterClientTests(unittest.TestCase):
    def test_url_is_always_bound_to_private_backend(self) -> None:
        client = CrayotterClient(host="127.0.0.1", port=18765)

        self.assertEqual(client.url("health"), "http://127.0.0.1:18765/health")
        self.assertEqual(client.url("/jobs/job-1"), "http://127.0.0.1:18765/jobs/job-1")

    def test_backend_startup_arguments_are_all_strings(self) -> None:
        source = build_backend_startup_source(port=18766)

        self.assertIn("'18766'", source)
        self.assertNotIn("--port', 18766", source)

    def test_blank_secret_fields_preserve_existing_keys(self) -> None:
        existing = {
            "api_key": "main-secret",
            "video_api_key": "video-secret",
            "tts_api_key": "tts-secret",
            "base_url": "https://old.example/v1",
            "model_name": "old-model",
        }
        submitted = {
            "api_key": "",
            "video_api_key": "  ",
            "tts_api_key": "",
            "base_url": "https://new.example/v1",
            "model_name": "new-model",
        }

        merged = merge_profile_config(existing, submitted)

        self.assertEqual(merged["api_key"], "main-secret")
        self.assertEqual(merged["video_api_key"], "video-secret")
        self.assertEqual(merged["tts_api_key"], "tts-secret")
        self.assertEqual(merged["base_url"], "https://new.example/v1")
        self.assertEqual(merged["model_name"], "new-model")

    def test_safe_upload_name_removes_paths_and_unsafe_characters(self) -> None:
        self.assertEqual(safe_upload_name("../../实验 视频 (1).mp4"), "实验_视频_1.mp4")
        self.assertEqual(safe_upload_name("../.env"), "env")

    def test_save_uploaded_files_deduplicates_names(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            upload_dir = Path(tmp_dir)
            files = [
                UploadedFileStub("素材.mp4", b"first"),
                UploadedFileStub("素材.mp4", b"second"),
            ]

            saved = save_uploaded_files(files, upload_dir)

            self.assertEqual([item["name"] for item in saved], ["素材.mp4", "素材_2.mp4"])
            self.assertEqual((upload_dir / "素材.mp4").read_bytes(), b"first")
            self.assertEqual((upload_dir / "素材_2.mp4").read_bytes(), b"second")


if __name__ == "__main__":
    unittest.main()
