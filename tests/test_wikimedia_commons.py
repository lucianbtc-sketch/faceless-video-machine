from __future__ import annotations

import json
import io
import sys
import tempfile
import unittest
from pathlib import Path
from urllib.error import HTTPError
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from faceless_video_machine.asset_manifest import save_asset_manifest
from faceless_video_machine.asset_sourcing import create_asset_sourcing_plan, merge_asset_candidates, save_asset_sourcing_plan
from faceless_video_machine.cli import main
from faceless_video_machine.models import AssetCandidate, AssetManifest, AssetManifestEntry, AssetSource, VideoProject
from faceless_video_machine.projects import create_project
from faceless_video_machine.wikimedia_commons import (
    AssetSourceConfigurationError,
    AssetSourceNetworkError,
    AssetSourceRateLimitError,
    AssetSourceResponseError,
    WikimediaCommonsConfig,
    WikimediaCommonsProvider,
    query_for_requirement,
)


class FakeOpener:
    def __init__(self, payload: object | Exception) -> None:
        self.payload = payload
        self.requests = []

    def __call__(self, request, timeout: float) -> bytes:
        self.requests.append((request, timeout))
        if isinstance(self.payload, Exception):
            raise self.payload
        if isinstance(self.payload, bytes):
            return self.payload
        return json.dumps(self.payload).encode("utf-8")


def requirement() -> AssetManifestEntry:
    return AssetManifestEntry("scene-001-asset-001", 1, "Scene 1: Hook", "image", "Historic city skyline")


class WikimediaCommonsTests(unittest.TestCase):
    def test_query_and_response_map_to_candidate_without_media_request(self) -> None:
        payload = {
            "query": {
                "pages": {
                    "42": {
                        "pageid": 42,
                        "title": "File:City skyline.jpg",
                        "imageinfo": [{
                            "descriptionurl": "https://commons.wikimedia.org/wiki/File:City_skyline.jpg",
                            "thumburl": "https://thumb.example/42.jpg",
                            "url": "https://upload.example/42.jpg",
                            "mime": "image/jpeg",
                            "extmetadata": {
                                "Artist": {"value": "<b>Example Creator</b>"},
                                "LicenseShortName": {"value": "CC BY-SA 4.0"},
                                "LicenseUrl": {"value": "https://creativecommons.org/licenses/by-sa/4.0/"},
                                "UsageTerms": {"value": "Attribution-ShareAlike"},
                            },
                        }],
                    }
                }
            }
        }
        opener = FakeOpener(payload)
        provider = WikimediaCommonsProvider(WikimediaCommonsConfig(user_agent="fvm-test/1.0 (test@example.invalid)", request_interval_seconds=0), opener, lambda _: None)
        candidates = provider.find_candidates(requirement())
        self.assertEqual(query_for_requirement(requirement()), "Historic city skyline")
        self.assertEqual(len(candidates), 1)
        candidate = candidates[0]
        self.assertEqual(candidate.candidate_id, "wikimedia-commons-42")
        self.assertEqual(candidate.creator, "Example Creator")
        self.assertEqual(candidate.license_name, "CC BY-SA 4.0")
        self.assertEqual(candidate.url, "https://commons.wikimedia.org/wiki/File:City_skyline.jpg")
        self.assertIn("verify", candidate.rights_note.lower())
        self.assertIn("upload.example", candidate.notes)
        self.assertEqual(len(opener.requests), 1)
        self.assertEqual(opener.requests[0][0].headers["User-agent"], "fvm-test/1.0 (test@example.invalid)")

    def test_missing_license_metadata_stays_missing(self) -> None:
        payload = {"query": {"pages": {"7": {"pageid": 7, "title": "File:Unknown.jpg", "imageinfo": [{"descriptionurl": "https://commons.wikimedia.org/wiki/File:Unknown.jpg"}]}}}}
        provider = WikimediaCommonsProvider(WikimediaCommonsConfig(user_agent="test", request_interval_seconds=0), FakeOpener(payload), lambda _: None)
        self.assertEqual(provider.find_candidates(requirement())[0].license_name, "")

    def test_configuration_parses_environment_values(self) -> None:
        config = WikimediaCommonsConfig.from_environment({
            "FVM_WIKIMEDIA_USER_AGENT": "fvm-test/1.0",
            "FVM_WIKIMEDIA_TIMEOUT_SECONDS": "3.5",
            "FVM_WIKIMEDIA_REQUEST_INTERVAL_SECONDS": "0.25",
            "FVM_WIKIMEDIA_MAX_RESULTS": "4",
        })
        self.assertEqual(config.user_agent, "fvm-test/1.0")
        self.assertEqual(config.timeout_seconds, 3.5)
        self.assertEqual(config.request_interval_seconds, 0.25)
        self.assertEqual(config.max_results, 4)

    def test_continuation_fetches_second_page_until_limit(self) -> None:
        first = {"query": {"pages": {"1": {"pageid": 1, "title": "File:One.jpg", "imageinfo": [{"descriptionurl": "https://commons.example/one"}]} }}, "continue": {"gsroffset": 1, "continue": "-||"}}
        second = {"query": {"pages": {"2": {"pageid": 2, "title": "File:Two.jpg", "imageinfo": [{"descriptionurl": "https://commons.example/two"}]}}}}

        class PaginatedOpener(FakeOpener):
            def __init__(self) -> None:
                super().__init__(None)
                self.payloads = [first, second]

            def __call__(self, request, timeout: float) -> bytes:
                self.requests.append((request, timeout))
                return json.dumps(self.payloads.pop(0)).encode("utf-8")

        opener = PaginatedOpener()
        provider = WikimediaCommonsProvider(WikimediaCommonsConfig(user_agent="test", request_interval_seconds=0, max_results=2), opener, lambda _: None)
        self.assertEqual([item.candidate_id for item in provider.find_candidates(requirement())], ["wikimedia-commons-1", "wikimedia-commons-2"])
        self.assertEqual(len(opener.requests), 2)
        self.assertIn("gsroffset=1", opener.requests[1][0].full_url)

    def test_malformed_pages_are_skipped_and_invalid_pages_shape_fails(self) -> None:
        payload = {"query": {"pages": {"bad": {"pageid": "not-an-int"}, "missing": {"pageid": 3, "title": "File:Missing.jpg", "imageinfo": []}}}}
        provider = WikimediaCommonsProvider(WikimediaCommonsConfig(user_agent="test", request_interval_seconds=0), FakeOpener(payload), lambda _: None)
        self.assertEqual(provider.find_candidates(requirement()), [])
        invalid = WikimediaCommonsProvider(WikimediaCommonsConfig(user_agent="test", request_interval_seconds=0), FakeOpener({"query": {"pages": []}}), lambda _: None)
        with self.assertRaises(AssetSourceResponseError):
            invalid.find_candidates(requirement())

    def test_configuration_and_network_errors_are_explicit(self) -> None:
        with self.assertRaises(AssetSourceConfigurationError):
            WikimediaCommonsConfig()
        provider = WikimediaCommonsProvider(WikimediaCommonsConfig(user_agent="test", request_interval_seconds=0), FakeOpener(HTTPError("url", 429, "slow down", {}, None)), lambda _: None)
        with self.assertRaises(AssetSourceRateLimitError):
            provider.find_candidates(requirement())
        provider = WikimediaCommonsProvider(WikimediaCommonsConfig(user_agent="test", request_interval_seconds=0), FakeOpener(OSError("offline")), lambda _: None)
        with self.assertRaises(AssetSourceNetworkError):
            provider.find_candidates(requirement())

    def test_api_errors_and_invalid_json_are_explicit(self) -> None:
        rate_payload = {"error": {"code": "maxlag", "info": "try later"}}
        provider = WikimediaCommonsProvider(WikimediaCommonsConfig(user_agent="test", request_interval_seconds=0), FakeOpener(rate_payload), lambda _: None)
        with self.assertRaises(AssetSourceRateLimitError):
            provider.find_candidates(requirement())
        provider = WikimediaCommonsProvider(WikimediaCommonsConfig(user_agent="test", request_interval_seconds=0), FakeOpener(b"not-json"), lambda _: None)
        with self.assertRaises(AssetSourceResponseError):
            provider.find_candidates(requirement())

    def test_candidate_merge_replaces_stable_provider_ids(self) -> None:
        manifest = AssetManifest("sample", "Sample", "production.json", [requirement()])
        source = AssetSource("wikimedia-commons", "Wikimedia Commons", source_kind="other")
        plan = create_asset_sourcing_plan(manifest)
        first = AssetCandidate("wikimedia-commons-42", requirement().asset_id, source.source_id, source.name, "https://commons.example/42", "Old title")
        second = AssetCandidate("wikimedia-commons-42", requirement().asset_id, source.source_id, source.name, "https://commons.example/42", "Updated title")
        plan = merge_asset_candidates(plan, manifest, source, [first])
        plan = merge_asset_candidates(plan, manifest, source, [second])
        self.assertEqual(len(plan.candidates), 1)
        self.assertEqual(plan.candidates[0].title, "Updated title")
        self.assertEqual(manifest.assets[0].status, "needed")

    def test_cli_reports_provider_errors_without_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            directory = create_project(VideoProject("sample", "Sample"), root)
            manifest = AssetManifest("sample", "Sample", "production.json", [requirement()])
            save_asset_manifest(manifest, directory)
            save_asset_sourcing_plan(create_asset_sourcing_plan(manifest), directory)
            stderr = io.StringIO()
            with patch.dict("os.environ", {"FVM_WIKIMEDIA_USER_AGENT": "test"}, clear=False), patch("faceless_video_machine.wikimedia_commons.WikimediaCommonsProvider.find_candidates", side_effect=AssetSourceNetworkError("offline")), patch("sys.stderr", stderr):
                result = main(["search-asset-candidates", "--project", "sample", "--asset-id", requirement().asset_id, "--projects-dir", root])
            self.assertEqual(result, 1)
            self.assertEqual(stderr.getvalue().strip(), "offline")
            self.assertNotIn("Traceback", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()