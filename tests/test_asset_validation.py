from __future__ import annotations

import hashlib
import io
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

from faceless_video_machine.asset_acquisition import create_asset_acquisition_plan
from faceless_video_machine.asset_manifest import save_asset_manifest
from faceless_video_machine.asset_sourcing import create_asset_sourcing_plan
from faceless_video_machine.asset_validation import validate_asset
from faceless_video_machine.cli import main
from faceless_video_machine.models import AssetAcquisition, AssetAcquisitionPlan, AssetManifest, AssetManifestEntry, VideoProject
from faceless_video_machine.projects import create_project


class AssetValidationTests(unittest.TestCase):
    def _fixture(self, root: str, content: bytes = b"asset data") -> tuple[AssetManifest, AssetAcquisitionPlan, Path]:
        path = Path(root) / "assets" / "scene-001-asset-001.jpg"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        entry = AssetManifestEntry("scene-001-asset-001", 1, "Scene 1: Hook", "image", "A local asset", local_path=str(path), status="downloaded")
        manifest = AssetManifest("sample", "Sample", "production.json", [entry])
        acquisition = AssetAcquisition("scene-001-asset-001", "candidate-1", "downloaded", str(path), hashlib.sha256(content).hexdigest(), len(content), "image/jpeg")
        history = AssetAcquisitionPlan("sample", "Sample", "asset-manifest.json", "asset-sourcing.json", [acquisition])
        return manifest, history, path

    def test_valid_asset_becomes_ready(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            manifest, history, _ = self._fixture(root)
            updated, result = validate_asset(manifest, history, "scene-001-asset-001")
            self.assertTrue(result.valid)
            self.assertEqual(updated.assets[0].status, "ready")

    def test_failed_checks_leave_manifest_and_history_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            manifest, history, path = self._fixture(root)
            original_history = history.to_dict()
            path.write_bytes(b"changed")
            updated, result = validate_asset(manifest, history, "scene-001-asset-001")
            self.assertFalse(result.valid)
            self.assertEqual(updated.to_dict(), manifest.to_dict())
            self.assertEqual(history.to_dict(), original_history)

    def test_missing_empty_and_directory_files_fail(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            manifest, history, path = self._fixture(root, b"")
            updated, result = validate_asset(manifest, history, manifest.assets[0].asset_id)
            self.assertFalse(result.valid)
            self.assertEqual(updated.assets[0].status, "downloaded")
            path.unlink()
            updated, result = validate_asset(manifest, history, manifest.assets[0].asset_id)
            self.assertIn("does not exist", result.errors[0])
            path.mkdir()
            updated, result = validate_asset(manifest, history, manifest.assets[0].asset_id)
            self.assertIn("not a regular file", result.errors[0])

    def test_status_and_acquisition_metadata_are_required(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            manifest, history, _ = self._fixture(root)
            manifest = AssetManifest("sample", "Sample", "production.json", [AssetManifestEntry("scene-001-asset-001", 1, "Scene 1", "image", "Asset", local_path=manifest.assets[0].local_path, status="needed")])
            updated, result = validate_asset(manifest, history, manifest.assets[0].asset_id)
            self.assertFalse(result.valid)
            self.assertEqual(updated.assets[0].status, "needed")
            history = AssetAcquisitionPlan("sample", "Sample", "asset-manifest.json", "asset-sourcing.json", [])
            updated, result = validate_asset(manifest, history, "scene-001-asset-001")
            self.assertTrue(any("record not found" in error for error in result.errors))

    def test_cli_success_and_clean_failure(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            directory = create_project(VideoProject("sample", "Sample"), root)
            manifest, history, _ = self._fixture(str(directory))
            save_asset_manifest(manifest, directory)
            (directory / "asset-acquisitions.json").write_text(json.dumps(history.to_dict()), encoding="utf-8")
            with patch("sys.stdout", io.StringIO()) as stdout:
                self.assertEqual(main(["validate-asset", "--project", "sample", "--asset-id", "scene-001-asset-001", "--projects-dir", root]), 0)
                self.assertIn("Asset is ready", stdout.getvalue())
            self.assertEqual(json.loads((directory / "asset-manifest.json").read_text())["assets"][0]["status"], "ready")
            manifest, history, path = self._fixture(str(directory))
            path.write_bytes(b"bad")
            save_asset_manifest(manifest, directory)
            stderr = io.StringIO()
            with patch("sys.stderr", stderr):
                self.assertEqual(main(["validate-asset", "--project", "sample", "--asset-id", "scene-001-asset-001", "--projects-dir", root]), 1)
            self.assertIn("Asset validation failed", stderr.getvalue())
            self.assertNotIn("Traceback", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()