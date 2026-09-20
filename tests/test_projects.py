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
from faceless_video_machine.projects import create_project, render_markdown, slugify


class VideoProjectTests(unittest.TestCase):
    def test_project_defaults_and_serialization(self) -> None:
        project = VideoProject(project_id="sample", title="Sample video")

        self.assertEqual(project.status, "idea")
        self.assertEqual(project.video_format, "explainer")
        self.assertTrue(project.created_at)
        self.assertEqual(VideoProject.from_dict(project.to_dict()), project)

    def test_invalid_project_data_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            VideoProject(project_id="", title="A title")
        with self.assertRaises(ValueError):
            VideoProject(project_id="sample", title="A title", duration_minutes=0)


class ProjectCreationTests(unittest.TestCase):
    def test_slugify_and_render_markdown(self) -> None:
        self.assertEqual(slugify("  Why Cities Are Hotter? "), "why-cities-are-hotter")
        project = VideoProject(project_id="sample", title="Sample video", topic="Heat")
        markdown = render_markdown(project)
        self.assertIn("# Sample video", markdown)
        self.assertIn("Heat", markdown)

    def test_create_project_writes_json_and_markdown(self) -> None:
        project = VideoProject(
            project_id="sample-video",
            title="Sample video",
            topic="A topic",
            duration_minutes=7.5,
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            destination = create_project(project, Path(temporary_directory) / "projects")
            json_path = destination / "brief.json"
            markdown_path = destination / "brief.md"

            self.assertTrue(json_path.is_file())
            self.assertTrue(markdown_path.is_file())
            self.assertEqual(json.loads(json_path.read_text()), project.to_dict())
            with self.assertRaises(FileExistsError):
                create_project(project, Path(temporary_directory) / "projects")


if __name__ == "__main__":
    unittest.main()
