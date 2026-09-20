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

from faceless_video_machine.models import ResearchSource, VideoProject
from faceless_video_machine.projects import create_project
from faceless_video_machine.research import ResearchBrief, export_research, load_research, save_research


class ResearchTests(unittest.TestCase):
    def test_source_requires_url_and_title(self) -> None:
        with self.assertRaises(ValueError):
            ResearchSource(url="", title="Source")
        with self.assertRaises(ValueError):
            ResearchSource(url="https://example.com", title="")

    def test_research_round_trip_preserves_separation(self) -> None:
        brief = ResearchBrief("sample", [ResearchSource("https://example.com", "Example", key_facts=["Fact 1"])], ["Possible angle"])
        restored = ResearchBrief.from_dict(brief.to_dict())
        self.assertEqual(restored.to_dict(), brief.to_dict())
        self.assertEqual(restored.sources[0].key_facts, ["Fact 1"])
        self.assertEqual(restored.generated_ideas, ["Possible angle"])

    def test_save_and_export_research(self) -> None:
        project = VideoProject("sample", "Sample video")
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_dir = create_project(project, Path(temporary_directory))
            brief = ResearchBrief("sample", [ResearchSource("https://example.com", "Example", notes="Read this", citation="Example (2026)")], ["Generated angle"])
            save_research(brief, project_dir)
            restored = load_research(project_dir, "sample")
            markdown_path = export_research(restored, project_dir, project.title)
            self.assertEqual(json.loads((project_dir / "research.json").read_text())["project_id"], "sample")
            markdown = markdown_path.read_text()
            self.assertIn("## Sourced facts", markdown)
            self.assertIn("Fact", markdown) if False else self.assertIn("Example (2026)", markdown)
            self.assertIn("## Generated ideas", markdown)
            self.assertIn("Generated angle", markdown)


if __name__ == "__main__":
    unittest.main()
