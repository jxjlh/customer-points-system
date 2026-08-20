from __future__ import annotations

import unittest
from pathlib import Path


class VideoEditorModuleBoundaryTests(unittest.TestCase):
    def test_video_editor_is_native_streamlit_without_iframe(self) -> None:
        source = Path("modules/video_editor.py").read_text(encoding="utf-8")

        self.assertNotIn("<iframe", source.lower())
        self.assertNotIn("components.html", source)
        self.assertIn("CrayotterClient", source)
        self.assertIn("st.file_uploader", source)
        self.assertIn("st.video", source)


if __name__ == "__main__":
    unittest.main()

