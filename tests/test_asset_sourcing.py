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

from faceless_video_machine.asset_manifest import create_asset_manifest, save_asset_manifest
from faceless_video_machine.asset_sourcing import (
    add_asset_candidate,
    create_asset_sourcing_plan,
    link_asset_candidate,
    load_asset_sourcing_plan,
    render_asset_sourcing_markdown,
    save_asset_sourcing_plan,
)
from faceless_video_machine.cli import main
from faceless_video_machine.models import AssetCandidate, AssetCandidateMatch, AssetSource, VideoProject
from faceless_video_machine.production_planning import create_production_plan, save_production_plan
from faceless_video_machine.projects import create_project
from faceless_video_machine.script_drafting import create_video_script, save_video_script
from faceless_video_machine.script_planning import create_script_plan


class AssetSourcingTests(unittest.TestCase):
    def setUp(self) -> None:
        project = VideoProject("sample", "Sample video", "A topic", "Viewers")
        plan = create_script_plan("sample", "Sample video", "A topic", "Viewers")
        script = create_video_script(project, plan)
        self.production = create_production_plan(script)
        self.manifest = create_asset_manifest(self.production)
        self.source = AssetSource("manual-notes", "Manual notes")
        self.candidate = AssetCandidate("candidate-001", "scene-001-asset-001", "manual-notes", "Manual notes", "https://example.invalid/item", "Recorded candidate")

    def test_initial_plan_and_candidate_metadata_round_trip(self) -> None:
        sourcing = create_asset_sourcing_plan(self.manifest)
        self.assertEqual(sourcing.source_asset_manifest, "asset-manifest.json")
        self.assertEqual(sourcing.candidates, [])
        sourcing = add_asset_candidate(sourcing, self.manifest, self.candidate, self.source)
        sourcing = link_asset_candidate(sourcing, self.manifest, AssetCandidateMatch(self.candidate.asset_id, self.candidate.candidate_id, "selected"))
        self.assertEqual(sourcing.matches[0].relationship, "selected")
        self.assertEqual(self.manifest.assets[0].status, "needed")
        self.assertIn("Not recorded", render_asset_sourcing_markdown(sourcing))
        self.assertIn("editorial metadata only", render_asset_sourcing_markdown(sourcing))

    def test_deterministic_validation_rejects_unknown_or_duplicate_metadata(self) -> None:
        sourcing = create_asset_sourcing_plan(self.manifest)
        with self.assertRaisesRegex(ValueError, "unknown manifest asset"):
            add_asset_candidate(sourcing, self.manifest, AssetCandidate("candidate-001", "unknown", "manual-notes", "Manual notes", "url", "Title"), self.source)
        sourcing = add_asset_candidate(sourcing, self.manifest, self.candidate, self.source)
        with self.assertRaisesRegex(ValueError, "candidate IDs must be unique"):
            add_asset_candidate(sourcing, self.manifest, self.candidate, self.source)
        with self.assertRaisesRegex(ValueError, "unknown candidate"):
            link_asset_candidate(sourcing, self.manifest, AssetCandidateMatch("scene-001-asset-001", "missing"))
        with self.assertRaisesRegex(ValueError, "candidate match asset_id"):
            link_asset_candidate(sourcing, self.manifest, AssetCandidateMatch("scene-002-asset-001", "candidate-001"))

    def test_persistence_cli_and_manifest_are_not_modified(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            directory = create_project(VideoProject("sample", "Sample video"), root)
            save_video_script(create_video_script(VideoProject("sample", "Sample video"), create_script_plan("sample", "Sample video", "A topic", "Viewers")), directory)
            save_production_plan(self.production, directory)
            save_asset_manifest(self.manifest, directory)
            original_manifest = (directory / "asset-manifest.json").read_text()
            with patch("sys.stdout") as stdout:
                self.assertEqual(main(["create-asset-candidates", "--project", "sample", "--projects-dir", root]), 0)
            self.assertIn("Created asset candidate plan", stdout.write.call_args_list[0].args[0])
            self.assertEqual((directory / "asset-manifest.json").read_text(), original_manifest)
            export_path = Path(root) / "asset-sourcing-export.json"
            self.assertEqual(main(["add-asset-candidate", "--project", "sample", "--asset-id", "scene-001-asset-001", "--candidate-id", "candidate-001", "--source-id", "manual-notes", "--source-name", "Manual notes", "--url", "https://example.invalid/item", "--title", "Recorded candidate", "--projects-dir", root]), 0)
            self.assertEqual(main(["link-asset-candidate", "--project", "sample", "--asset-id", "scene-001-asset-001", "--candidate-id", "candidate-001", "--relationship", "shortlisted", "--projects-dir", root]), 0)
            self.assertEqual(main(["asset-candidates", "--project", "sample", "--format", "json", "--output", str(export_path), "--projects-dir", root]), 0)
            self.assertEqual(json.loads(export_path.read_text()), load_asset_sourcing_plan(directory).to_dict())

    def test_json_persistence(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            sourcing = add_asset_candidate(create_asset_sourcing_plan(self.manifest), self.manifest, self.candidate, self.source)
            json_path, markdown_path = save_asset_sourcing_plan(sourcing, root)
            self.assertEqual(load_asset_sourcing_plan(root).to_dict(), json.loads(json_path.read_text()))
            self.assertIn("Asset sourcing candidates", markdown_path.read_text())


if __name__ == "__main__":
    unittest.main()