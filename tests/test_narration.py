from __future__ import annotations

import json
import sys
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from faceless_video_machine.cli import main
from faceless_video_machine.models import VideoProject
from faceless_video_machine.narration import add_narration, create_narration_plan, load_narration_plan, save_narration_plan, validate_narration
from faceless_video_machine.projects import create_project
from faceless_video_machine.script_drafting import create_video_script
from faceless_video_machine.script_planning import create_script_plan


class NarrationTests(unittest.TestCase):
    def setUp(self) -> None:
        project = VideoProject("sample", "Sample")
        plan = create_script_plan("sample", "Sample", "Topic", "Audience")
        self.script = create_video_script(project, plan)
        self.narration = create_narration_plan(self.script)

    def _wav(self, directory: str, name: str = "voice.wav") -> Path:
        path = Path(directory) / name
        with wave.open(str(path), "wb") as audio:
            audio.setnchannels(1); audio.setsampwidth(2); audio.setframerate(10); audio.writeframes(b"\0\0" * 20)
        return path

    def test_creates_one_segment_per_script_section_and_validates_wav(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            path = self._wav(root)
            updated = self.narration
            for section_index in range(1, len(self.script.sections) + 1):
                updated = add_narration(updated, self.script, section_index, str(path))
            updated, result = validate_narration(updated, self.script)
            self.assertTrue(result.valid)
            self.assertEqual(len(updated.segments), len(self.script.sections))
            self.assertEqual(updated.segments[0].status, "validated")
            self.assertEqual(updated.segments[0].duration_seconds, 2.0)

    def test_non_wav_requires_manual_duration(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "voice.mp3"
            path.write_bytes(b"audio placeholder")
            recorded = self.narration
            for section_index in range(1, len(self.script.sections) + 1):
                recorded = add_narration(recorded, self.script, section_index, str(path))
            _, failed = validate_narration(recorded, self.script)
            self.assertFalse(failed.valid)
            recorded = self.narration
            for section_index in range(1, len(self.script.sections) + 1):
                recorded = add_narration(recorded, self.script, section_index, str(path), 3.5)
            validated, result = validate_narration(recorded, self.script)
            self.assertTrue(result.valid)
            self.assertEqual(validated.segments[0].duration_seconds, 3.5)

    def test_missing_files_leave_plan_unchanged(self) -> None:
        recorded = add_narration(self.narration, self.script, 1, "/missing/voice.wav")
        updated, result = validate_narration(recorded, self.script)
        self.assertFalse(result.valid)
        self.assertEqual(updated.to_dict(), recorded.to_dict())

    def test_persistence_and_cli_workflow(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            directory = create_project(VideoProject("sample", "Sample"), root)
            (directory / "video-script.json").write_text(json.dumps(self.script.to_dict()), encoding="utf-8")
            save_narration_plan(self.narration, directory)
            wav = self._wav(str(directory), "voice.wav")
            for section_index in range(1, len(self.script.sections) + 1):
                self.assertEqual(main(["add-narration", "--project", "sample", "--section", str(section_index), "--path", str(wav), "--projects-dir", root]), 0)
            with patch("sys.stdout") as stdout:
                self.assertEqual(main(["validate-narration", "--project", "sample", "--projects-dir", root]), 0)
            self.assertIn("Narration validated", stdout.write.call_args_list[0].args[0])
            self.assertEqual(load_narration_plan(directory).segments[0].status, "validated")


if __name__ == "__main__":
    unittest.main()