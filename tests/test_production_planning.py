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
from faceless_video_machine.models import ProductionScene, VideoProject
from faceless_video_machine.production_planning import (
    create_production_plan,
    load_production_plan,
    render_production_plan_markdown,
    save_production_plan,
)
from faceless_video_machine.projects import create_project
from faceless_video_machine.script_drafting import create_video_script, save_video_script
from faceless_video_machine.script_planning import create_script_plan


class ProductionPlanningTests(unittest.TestCase):
    def setUp(self) -> None:
        project = VideoProject("sample", "Sample video", "A topic", "Viewers")
        plan = create_script_plan("sample", "Sample video", "A topic", "Viewers")
        self.script = create_video_script(project, plan)

    def test_creates_one_scene_per_script_section_without_copying_narration(self) -> None:
        production = create_production_plan(self.script)
        self.assertEqual(len(production.scenes), len(self.script.sections))
        self.assertEqual(production.scenes[0].narration_reference, "VideoScript section 1: Hook")
        self.assertEqual(production.scenes[-1].asset_type, "text_card")
        self.assertEqual(production.scenes[0].visual_direction, self.script.sections[0].visual_notes)
        self.assertNotIn(self.script.sections[0].narration, production.to_dict()["scenes"][0]["narration_reference"])

    def test_scene_validation_and_markdown(self) -> None:
        with self.assertRaisesRegex(ValueError, "unsupported production asset type"):
            ProductionScene(1, 1, "Hook", 1.0, "Open", asset_type="audio")
        production = create_production_plan(self.script)
        markdown = render_production_plan_markdown(production)
        self.assertIn("| Scene | Narration reference |", markdown)
        self.assertIn("source script remains authoritative", markdown)

    def test_json_round_trip_and_cli_export(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            directory = create_project(VideoProject("sample", "Sample video"), root)
            save_video_script(self.script, directory)
            production = create_production_plan(self.script)
            json_path, markdown_path = save_production_plan(production, directory)
            self.assertEqual(load_production_plan(directory).to_dict(), json.loads(json_path.read_text()))
            self.assertIn("Production shot list", markdown_path.read_text())

            with patch("sys.stdout") as stdout:
                self.assertEqual(main(["create-production-plan", "--project", "sample", "--projects-dir", root]), 0)
            self.assertIn("Created production plan", stdout.write.call_args_list[0].args[0])
            export_path = Path(root) / "production-export.json"
            self.assertEqual(main(["production-plan", "--project", "sample", "--format", "json", "--output", str(export_path), "--projects-dir", root]), 0)
            self.assertEqual(json.loads(export_path.read_text()), load_production_plan(directory).to_dict())


if __name__ == "__main__":
    unittest.main()