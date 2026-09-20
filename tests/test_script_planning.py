from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from faceless_video_machine.models import VideoProject
from faceless_video_machine.projects import create_project
from faceless_video_machine.script_planning import create_script_plan, load_script_plan, retention_checklist, save_script_plan


class ScriptPlanningTests(unittest.TestCase):
    def test_duration_pacing_and_formats(self) -> None:
        plan = create_script_plan("id", "Title", "Topic", "Audience", "case study", 10, "fast")
        self.assertEqual(plan.target_word_count, 1750)
        for video_format in ("explainer", "documentary/story", "case study", "timeline / what happened", "list video"):
            self.assertEqual(create_script_plan("id", "T", "X", "A", video_format).format, video_format)

    def test_retention_flags(self) -> None:
        plan = create_script_plan("id", "T", "X", "A")
        plan.cold_open = "Today we are going to talk about this topic"
        plan.main_curiosity_question = ""
        plan.progressive_reveals = []
        plan.payoff = ""
        flags = retention_checklist(plan)
        self.assertIn("Weak or missing cold open", flags)
        self.assertIn("Missing curiosity question", flags)
        self.assertIn("No progressive reveals", flags)
        self.assertIn("Missing payoff", flags)

    def test_json_and_markdown_persistence(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            directory = create_project(VideoProject("id", "Title"), root)
            plan = create_script_plan("id", "Title", "Topic", "Audience")
            json_path, markdown_path = save_script_plan(plan, directory)
            self.assertEqual(load_script_plan(directory).to_dict(), json.loads(json_path.read_text()))
            self.assertIn("Cold open / first 5 seconds", markdown_path.read_text())
            self.assertIn("Retention checklist", markdown_path.read_text())


if __name__ == "__main__":
    unittest.main()
