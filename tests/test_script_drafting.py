from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from faceless_video_machine.cli import main
from faceless_video_machine.models import VideoProject
from faceless_video_machine.projects import create_project
from faceless_video_machine.script_drafting import (
    create_video_script,
    load_video_script,
    render_video_script_markdown,
    save_video_script,
)
from faceless_video_machine.script_planning import create_script_plan, save_script_plan


class ScriptDraftingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.project = VideoProject("sample", "Sample video", "A topic", "Viewers")
        self.plan = create_script_plan("sample", "Sample video", "A topic", "Viewers")

    def test_plan_becomes_editable_structured_script(self) -> None:
        script = create_video_script(self.project, self.plan)
        self.assertEqual(
            [section.name for section in script.sections],
            ["Hook", "Introduction", "Main section 1", "Transition", "Main section 2", "Transition", "Main section 3", "Conclusion", "Call to action"],
        )
        self.assertTrue(all(section.estimated_word_count is not None for section in script.sections))
        self.assertTrue(all(section.visual_notes for section in script.sections))
        self.assertEqual(script.sections[0].narration, self.plan.cold_open)
        self.assertIn("### Visual / B-roll notes", render_video_script_markdown(script))

    def test_editable_json_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            directory = create_project(self.project, root)
            script = create_video_script(self.project, self.plan)
            script.sections[0].narration = "A revised opening."
            json_path, markdown_path = save_video_script(script, directory)
            loaded = load_video_script(directory)
            self.assertEqual(loaded.to_dict(), json.loads(json_path.read_text()))
            self.assertEqual(loaded.sections[0].narration, "A revised opening.")
            self.assertIn("A revised opening.", markdown_path.read_text())

    def test_project_and_plan_must_match(self) -> None:
        other_project = VideoProject("other", "Other video")
        with self.assertRaisesRegex(ValueError, "same project_id"):
            create_video_script(other_project, self.plan)

    def test_cli_creates_views_and_exports_video_script(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            directory = create_project(self.project, root)
            save_script_plan(self.plan, directory)
            with patch("sys.stdout") as stdout:
                self.assertEqual(main(["create-video-script", "--project", "sample", "--projects-dir", root]), 0)
            self.assertTrue((directory / "video-script.json").is_file())
            self.assertIn("Created video script", stdout.write.call_args_list[0].args[0])

            export_path = Path(root) / "export.json"
            self.assertEqual(main(["video-script", "--project", "sample", "--format", "json", "--output", str(export_path), "--projects-dir", root]), 0)
            self.assertEqual(json.loads(export_path.read_text()), load_video_script(directory).to_dict())


if __name__ == "__main__":
    unittest.main()