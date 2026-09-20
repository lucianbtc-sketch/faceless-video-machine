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

from faceless_video_machine.asset_manifest import (
    create_asset_manifest,
    load_asset_manifest,
    render_asset_manifest_markdown,
    save_asset_manifest,
)
from faceless_video_machine.cli import main
from faceless_video_machine.models import AssetManifest, AssetManifestEntry, VideoProject
from faceless_video_machine.production_planning import create_production_plan, save_production_plan
from faceless_video_machine.projects import create_project
from faceless_video_machine.script_drafting import create_video_script
from faceless_video_machine.script_planning import create_script_plan


class AssetManifestTests(unittest.TestCase):
    def setUp(self) -> None:
        project = VideoProject("sample", "Sample video", "A topic", "Viewers")
        script_plan = create_script_plan("sample", "Sample video", "A topic", "Viewers")
        self.production = create_production_plan(create_video_script(project, script_plan))

    def test_creates_deterministic_metadata_only_asset_requirements(self) -> None:
        manifest = create_asset_manifest(self.production)
        self.assertEqual(len(manifest.assets), len(self.production.scenes))
        self.assertEqual(manifest.assets[0].asset_id, "scene-001-asset-001")
        self.assertEqual(manifest.assets[-1].asset_id, "scene-009-asset-001")
        self.assertEqual(manifest.assets[0].scene_number, self.production.scenes[0].scene_number)
        self.assertEqual(manifest.assets[0].status, "needed")
        self.assertEqual(manifest.assets[0].source_url, "")
        self.assertEqual(manifest.assets[0].local_path, "")
        self.assertNotIn("Open with the most surprising", manifest.assets[0].to_dict()["description"])

    def test_validation_covers_lifecycle_metadata_without_filesystem_checks(self) -> None:
        with self.assertRaisesRegex(ValueError, "sourced assets need"):
            AssetManifestEntry("asset-1", 1, "Scene 1", "image", "An image", status="sourced")
        with self.assertRaisesRegex(ValueError, "downloaded assets need"):
            AssetManifestEntry("asset-1", 1, "Scene 1", "image", "An image", status="downloaded")
        with self.assertRaisesRegex(ValueError, "rejected assets need"):
            AssetManifestEntry("asset-1", 1, "Scene 1", "image", "An image", status="rejected")
        ready = AssetManifestEntry("asset-1", 1, "Scene 1", "image", "An image", local_path="does-not-exist.jpg", status="ready")
        self.assertEqual(ready.status, "ready")
        with self.assertRaisesRegex(ValueError, "asset IDs must be unique"):
            AssetManifest("sample", "Sample", "production.json", [ready, ready])

    def test_markdown_persistence_and_cli_workflow(self) -> None:
        manifest = create_asset_manifest(self.production)
        markdown = render_asset_manifest_markdown(manifest)
        self.assertIn("| Asset ID | Scene | Type |", markdown)
        self.assertIn("Status summary", markdown)
        with tempfile.TemporaryDirectory() as root:
            directory = create_project(VideoProject("sample", "Sample video"), root)
            save_production_plan(self.production, directory)
            json_path, markdown_path = save_asset_manifest(manifest, directory)
            self.assertEqual(load_asset_manifest(directory).to_dict(), json.loads(json_path.read_text()))
            self.assertIn("metadata manifest", markdown_path.read_text())
            with patch("sys.stdout") as stdout:
                self.assertEqual(main(["create-asset-manifest", "--project", "sample", "--projects-dir", root]), 0)
            self.assertIn("Created asset manifest", stdout.write.call_args_list[0].args[0])
            export_path = Path(root) / "asset-manifest-export.json"
            self.assertEqual(main(["asset-manifest", "--project", "sample", "--format", "json", "--output", str(export_path), "--projects-dir", root]), 0)
            self.assertEqual(json.loads(export_path.read_text()), load_asset_manifest(directory).to_dict())


if __name__ == "__main__":
    unittest.main()