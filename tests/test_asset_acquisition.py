from __future__ import annotations

import hashlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from faceless_video_machine.asset_acquisition import (
    AssetDownloadConfig,
    AssetDownloadIOError,
    AssetDownloadLimitError,
    AssetAcquisitionError,
    BoundedRedirectHandler,
    UnsupportedDownloadSchemeError,
    UrlAssetDownloader,
    acquire_asset,
    create_asset_acquisition_plan,
    load_asset_acquisition_plan,
    save_asset_acquisition_plan,
)
from faceless_video_machine.asset_manifest import create_asset_manifest
from faceless_video_machine.asset_manifest import save_asset_manifest
from faceless_video_machine.asset_sourcing import create_asset_sourcing_plan, link_asset_candidate, save_asset_sourcing_plan
from faceless_video_machine.cli import main
from faceless_video_machine.models import AssetCandidate, AssetCandidateMatch, AssetDownloadResult, AssetManifest, AssetManifestEntry, AssetSource, AssetSourcingPlan, VideoProject
from faceless_video_machine.projects import create_project
from faceless_video_machine.production_planning import create_production_plan
from faceless_video_machine.script_drafting import create_video_script
from faceless_video_machine.script_planning import create_script_plan


class FakeResponse:
    def __init__(self, chunks: list[bytes], content_type: str = "image/jpeg") -> None:
        self.chunks = list(chunks)
        self.headers = {"Content-Type": content_type}
        self.closed = False

    def read(self, size: int) -> bytes:
        if not self.chunks:
            return b""
        return self.chunks.pop(0)

    def close(self) -> None:
        self.closed = True


class ReadFailureResponse(FakeResponse):
    def read(self, size: int) -> bytes:
        raise OSError("read failed")


class FakeDownloader:
    def __init__(self, response: FakeResponse | Exception) -> None:
        self.response = response

    def download(self, candidate: AssetCandidate, destination: Path, overwrite: bool = False):
        if isinstance(self.response, Exception):
            raise self.response
        return UrlAssetDownloader(AssetDownloadConfig(output_dir=str(destination.parent), max_bytes=100), lambda *_: self.response).download(candidate, destination, overwrite=overwrite)


class AssetAcquisitionTests(unittest.TestCase):
    def setUp(self) -> None:
        project = VideoProject("sample", "Sample")
        script_plan = create_script_plan("sample", "Sample", "Topic", "Audience")
        production = create_production_plan(create_video_script(project, script_plan))
        self.manifest = create_asset_manifest(production)
        self.source = AssetSource("manual", "Manual", source_kind="manual")
        self.candidate = AssetCandidate("candidate-1", "scene-001-asset-001", "manual", "Manual", "https://example.invalid/file", "A file", license_name="CC BY", usage_information="Attribution required", download_url="https://example.invalid/file.jpg")
        sourcing = create_asset_sourcing_plan(self.manifest)
        sourcing.sources.append(self.source)
        sourcing.candidates.append(self.candidate)
        self.sourcing = AssetSourcingPlan(sourcing.project_id, sourcing.title, sourcing.source_asset_manifest, sourcing.sources, sourcing.candidates, [AssetCandidateMatch(self.candidate.asset_id, self.candidate.candidate_id, "selected")])

    def test_streams_hashes_and_updates_only_after_success(self) -> None:
        content = [b"hello ", b"world"]
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "scene-001-asset-001.jpg"
            response = FakeResponse(content)
            updated, acquisition = acquire_asset(self.manifest, self.sourcing, self.candidate.asset_id, self.candidate.candidate_id, Path(root), FakeDownloader(response))
            self.assertEqual(acquisition.status, "downloaded")
            self.assertEqual(path.read_bytes(), b"hello world")
            self.assertEqual(acquisition.sha256, hashlib.sha256(b"hello world").hexdigest())
            self.assertEqual(updated.assets[0].status, "downloaded")
            self.assertEqual(updated.assets[0].local_path, str(path))
            self.assertEqual(self.manifest.assets[0].status, "needed")
            self.assertTrue(response.closed)
            self.assertEqual(acquisition.content_type, "image/jpeg")

    def test_older_candidate_json_defaults_download_url(self) -> None:
        data = self.candidate.to_dict()
        del data["download_url"]
        self.assertEqual(AssetCandidate.from_dict(data).download_url, "")

    def test_requires_selected_rights_and_structured_http_url(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            unselected = AssetSourcingPlan(self.sourcing.project_id, self.sourcing.title, self.sourcing.source_asset_manifest, self.sourcing.sources, self.sourcing.candidates, [])
            with self.assertRaisesRegex(ValueError, "explicitly selected"):
                acquire_asset(self.manifest, unselected, self.candidate.asset_id, self.candidate.candidate_id, Path(root), FakeDownloader(FakeResponse([b"x"])))
            no_url = AssetCandidate("candidate-2", self.candidate.asset_id, "manual", "Manual", "https://example.invalid/page", "No direct URL", license_name="CC BY", usage_information="Attribution required", download_url="file:///tmp/nope")
            sourcing = AssetSourcingPlan(self.sourcing.project_id, self.sourcing.title, self.sourcing.source_asset_manifest, self.sourcing.sources, [no_url], [AssetCandidateMatch(no_url.asset_id, no_url.candidate_id, "selected")])
            _, acquisition = acquire_asset(self.manifest, sourcing, no_url.asset_id, no_url.candidate_id, Path(root), UrlAssetDownloader(AssetDownloadConfig(max_bytes=10), lambda *_: FakeResponse([b"x"])))
            self.assertEqual(acquisition.status, "failed")
            self.assertIn("http or https", acquisition.error)

    def test_missing_rights_can_only_be_explicitly_overridden(self) -> None:
        candidate = AssetCandidate("candidate-3", self.candidate.asset_id, "manual", "Manual", "https://example.invalid/page", "No rights", download_url="https://example.invalid/file.jpg")
        sourcing = AssetSourcingPlan(self.sourcing.project_id, self.sourcing.title, self.sourcing.source_asset_manifest, self.sourcing.sources, [candidate], [AssetCandidateMatch(candidate.asset_id, candidate.candidate_id, "selected")])
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaisesRegex(ValueError, "missing license"):
                acquire_asset(self.manifest, sourcing, candidate.asset_id, candidate.candidate_id, Path(root), FakeDownloader(FakeResponse([b"x"])))
            updated, acquisition = acquire_asset(self.manifest, sourcing, candidate.asset_id, candidate.candidate_id, Path(root), FakeDownloader(FakeResponse([b"x"])), allow_missing_rights_metadata=True)
            self.assertEqual(acquisition.status, "downloaded")
            self.assertEqual(updated.assets[0].status, "downloaded")

    def test_partial_rights_metadata_is_blocked(self) -> None:
        for license_name, usage_information in (("CC BY", ""), ("", "Attribution required")):
            candidate = AssetCandidate("partial-rights", self.candidate.asset_id, "manual", "Manual", "https://example.invalid/page", "Partial rights", license_name=license_name, usage_information=usage_information, download_url="https://example.invalid/file.jpg")
            sourcing = AssetSourcingPlan(self.sourcing.project_id, self.sourcing.title, self.sourcing.source_asset_manifest, self.sourcing.sources, [candidate], [AssetCandidateMatch(candidate.asset_id, candidate.candidate_id, "selected")])
            with tempfile.TemporaryDirectory() as root:
                with self.assertRaisesRegex(ValueError, "missing license or usage metadata"):
                    acquire_asset(self.manifest, sourcing, candidate.asset_id, candidate.candidate_id, Path(root), FakeDownloader(FakeResponse([b"x"])))

    def test_streaming_limit_and_failure_preserve_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            updated, acquisition = acquire_asset(self.manifest, self.sourcing, self.candidate.asset_id, self.candidate.candidate_id, Path(root), FakeDownloader(FakeResponse([b"1234", b"5678"])))
            self.assertEqual(updated.assets[0].status, "downloaded")
            limited = UrlAssetDownloader(AssetDownloadConfig(max_bytes=3), lambda *_: FakeResponse([b"1234"]))
            with self.assertRaises(AssetDownloadLimitError):
                limited.download(self.candidate, Path(root) / "limited.jpg")
            failed_manifest, failed = acquire_asset(self.manifest, self.sourcing, self.candidate.asset_id, self.candidate.candidate_id, Path(root), FakeDownloader(AssetAcquisitionError("offline")))
            self.assertEqual(failed.status, "failed")
            self.assertEqual(failed_manifest.assets[0].status, "needed")

    def test_read_failure_cleans_temporary_file_and_records_failed_acquisition(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            output = Path(root)
            updated, acquisition = acquire_asset(self.manifest, self.sourcing, self.candidate.asset_id, self.candidate.candidate_id, output, UrlAssetDownloader(AssetDownloadConfig(max_bytes=100), lambda *_: ReadFailureResponse([])))
            self.assertEqual(acquisition.status, "failed")
            self.assertEqual(updated.assets[0].status, "needed")
            self.assertEqual(list(output.iterdir()), [])

    def test_write_failure_cleans_temporary_file(self) -> None:
        original_open = Path.open

        def fail_write(path: Path, *args, **kwargs):
            if args and args[0] == "wb":
                raise OSError("write failed")
            return original_open(path, *args, **kwargs)

        with tempfile.TemporaryDirectory() as root, patch("pathlib.Path.open", fail_write):
            with self.assertRaises(AssetDownloadIOError):
                UrlAssetDownloader(AssetDownloadConfig(max_bytes=100), lambda *_: FakeResponse([b"x"])).download(self.candidate, Path(root) / "asset.jpg")
            self.assertEqual(list(Path(root).iterdir()), [])

    def test_overwrite_preserves_existing_file_on_failure_and_replaces_on_success(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            output = Path(root)
            destination = output / "scene-001-asset-001.jpg"
            destination.write_bytes(b"old")
            failed_manifest, failed = acquire_asset(self.manifest, self.sourcing, self.candidate.asset_id, self.candidate.candidate_id, output, UrlAssetDownloader(AssetDownloadConfig(max_bytes=100), lambda *_: ReadFailureResponse([])), overwrite=True)
            self.assertEqual(failed.status, "failed")
            self.assertEqual(destination.read_bytes(), b"old")
            self.assertEqual(failed_manifest.assets[0].status, "needed")
            updated, success = acquire_asset(self.manifest, self.sourcing, self.candidate.asset_id, self.candidate.candidate_id, output, UrlAssetDownloader(AssetDownloadConfig(max_bytes=100), lambda *_: FakeResponse([b"new"])), overwrite=True)
            self.assertEqual(success.status, "downloaded")
            self.assertEqual(destination.read_bytes(), b"new")
            self.assertEqual(updated.assets[0].status, "downloaded")

    def test_redirect_handler_rejects_unsafe_and_excessive_redirects(self) -> None:
        handler = BoundedRedirectHandler(1)
        request = __import__("urllib.request", fromlist=["Request"]).Request("https://example.invalid")
        with self.assertRaises(UnsupportedDownloadSchemeError):
            handler.redirect_request(request, None, 302, "", {}, "file:///tmp/nope")
        handler.redirect_request(request, None, 302, "", {}, "https://example.invalid/one")
        with self.assertRaises(AssetAcquisitionError):
            handler.redirect_request(request, None, 302, "", {}, "https://example.invalid/two")

    def test_acquisition_persistence_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            plan = create_asset_acquisition_plan(self.manifest, self.sourcing)
            _, acquisition = acquire_asset(self.manifest, self.sourcing, self.candidate.asset_id, self.candidate.candidate_id, Path(root), FakeDownloader(FakeResponse([b"x"])))
            plan.acquisitions.append(acquisition)
            json_path, markdown_path = save_asset_acquisition_plan(plan, root)
            self.assertEqual(load_asset_acquisition_plan(root).to_dict(), json.loads(json_path.read_text()))
            self.assertIn("Asset acquisitions", markdown_path.read_text())

    def test_cli_success_failure_and_configuration_errors(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            directory = create_project(VideoProject("sample", "Sample"), root)
            save_asset_manifest(self.manifest, directory)
            save_asset_sourcing_plan(self.sourcing, directory)
            with patch.dict(os.environ, {"FVM_ASSET_OUTPUT_DIR": str(Path(root) / "assets")}, clear=False), patch("faceless_video_machine.asset_acquisition.UrlAssetDownloader.download", return_value=AssetDownloadResult(str(Path(root) / "assets" / "scene-001-asset-001.jpg"), "hash", 3, "image/jpeg")):
                self.assertEqual(main(["acquire-asset", "--project", "sample", "--asset-id", self.candidate.asset_id, "--candidate-id", self.candidate.candidate_id, "--projects-dir", root]), 0)
            saved_manifest = AssetManifest.from_dict(json.loads((directory / "asset-manifest.json").read_text()))
            self.assertEqual(saved_manifest.assets[0].status, "downloaded")
            with patch.dict(os.environ, {"FVM_ASSET_MAX_BYTES": "0"}, clear=False), patch("sys.stderr", io.StringIO()) as stderr:
                self.assertEqual(main(["acquire-asset", "--project", "sample", "--asset-id", self.candidate.asset_id, "--candidate-id", self.candidate.candidate_id, "--projects-dir", root]), 1)
                self.assertIn("invalid asset download configuration", stderr.getvalue())
            with patch("faceless_video_machine.asset_acquisition.UrlAssetDownloader.download", side_effect=AssetAcquisitionError("offline")), patch("sys.stderr", io.StringIO()) as stderr:
                self.assertEqual(main(["acquire-asset", "--project", "sample", "--asset-id", self.candidate.asset_id, "--candidate-id", self.candidate.candidate_id, "--projects-dir", root]), 1)
                self.assertIn("offline", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()