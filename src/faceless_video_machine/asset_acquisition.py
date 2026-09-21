"""Controlled, explicit asset downloads with no media processing."""

from __future__ import annotations

import hashlib
import os
import re
import tempfile
import time
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener, urlopen

from .models import (
    AssetAcquisition,
    AssetAcquisitionPlan,
    AssetCandidate,
    AssetCandidateMatch,
    AssetDownloadResult,
    AssetManifest,
    AssetSourcingPlan,
)


class AssetAcquisitionError(Exception):
    """Base error for controlled local asset acquisition."""


class UnsupportedDownloadSchemeError(AssetAcquisitionError):
    """The candidate does not provide an HTTP(S) download URL."""


class AssetDownloadNetworkError(AssetAcquisitionError):
    """The download request failed before finalization."""


class AssetDownloadLimitError(AssetAcquisitionError):
    """The response exceeded the configured streaming byte limit."""


class AssetDownloadConfigurationError(AssetAcquisitionError):
    """The downloader configuration is invalid."""


class AssetDownloadIOError(AssetAcquisitionError):
    """The response or temporary-file I/O failed during acquisition."""


@dataclass(slots=True)
class AssetDownloadConfig:
    output_dir: str = "assets"
    max_bytes: int = 50 * 1024 * 1024
    timeout_seconds: float = 30.0
    max_redirects: int = 3

    def __post_init__(self) -> None:
        if not self.output_dir.strip() or self.max_bytes <= 0 or self.timeout_seconds <= 0 or self.max_redirects < 0:
            raise AssetDownloadConfigurationError("invalid asset download configuration")

    @classmethod
    def from_environment(cls, environ: dict[str, str] | None = None) -> "AssetDownloadConfig":
        values = os.environ if environ is None else environ
        return cls(
            output_dir=values.get("FVM_ASSET_OUTPUT_DIR", "assets"),
            max_bytes=int(values.get("FVM_ASSET_MAX_BYTES", str(50 * 1024 * 1024))),
            timeout_seconds=float(values.get("FVM_ASSET_DOWNLOAD_TIMEOUT_SECONDS", "30")),
            max_redirects=int(values.get("FVM_ASSET_MAX_REDIRECTS", "3")),
        )


class BoundedRedirectHandler(HTTPRedirectHandler):
    """Allow only a small number of HTTP(S) redirects."""

    def __init__(self, max_redirects: int) -> None:
        super().__init__()
        self.max_redirects = max_redirects
        self.redirect_count = 0

    def redirect_request(self, req: Request, fp, code: int, msg: str, headers, newurl: str):
        if urlsplit(newurl).scheme.lower() not in ("http", "https"):
            raise UnsupportedDownloadSchemeError("redirect target must use http or https")
        if self.redirect_count >= self.max_redirects:
            raise AssetAcquisitionError("maximum redirect count exceeded")
        self.redirect_count += 1
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _default_open(request: Request, timeout: float, max_redirects: int):
    opener = build_opener(BoundedRedirectHandler(max_redirects))
    return opener.open(request, timeout=timeout)


class UrlAssetDownloader:
    """Stream one explicitly selected HTTP(S) candidate to a local file."""

    name = "urllib"

    def __init__(
        self,
        config: AssetDownloadConfig,
        opener: Callable[[Request, float, int], object] = _default_open,
    ) -> None:
        self.config = config
        self._opener = opener

    def download(self, candidate: AssetCandidate, destination: Path, overwrite: bool = False) -> AssetDownloadResult:
        if not candidate.download_url.strip():
            raise AssetAcquisitionError("candidate has no download_url; url and notes are not used as fallbacks")
        parsed = urlsplit(candidate.download_url)
        if parsed.scheme.lower() not in ("http", "https") or not parsed.netloc:
            raise UnsupportedDownloadSchemeError("download_url must use http or https")
        if destination.exists() and not destination.is_file():
            raise AssetAcquisitionError(f"destination is not a file: {destination}")
        if destination.exists() and not overwrite:
            raise AssetAcquisitionError(f"destination already exists: {destination}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        request = Request(candidate.download_url, headers={"User-Agent": "faceless-video-machine/0.1"})
        temporary_path: Path | None = None
        response = None
        digest = hashlib.sha256()
        byte_count = 0
        try:
            try:
                response = self._opener(request, self.config.timeout_seconds, self.config.max_redirects)
            except (HTTPError, URLError, TimeoutError, OSError) as error:
                raise AssetDownloadNetworkError(f"asset download failed: {error}") from error
            try:
                fd, temporary_name = tempfile.mkstemp(prefix=f".{destination.name}.", dir=destination.parent)
                os.close(fd)
                temporary_path = Path(temporary_name)
                with temporary_path.open("wb") as output:
                    while True:
                        chunk = response.read(64 * 1024)
                        if not chunk:
                            break
                        byte_count += len(chunk)
                        if byte_count > self.config.max_bytes:
                            raise AssetDownloadLimitError("asset exceeds the configured maximum byte limit")
                        output.write(chunk)
                        digest.update(chunk)
            except AssetAcquisitionError:
                raise
            except (OSError, URLError, TimeoutError) as error:
                raise AssetDownloadIOError(f"asset response or temporary-file I/O failed: {error}") from error
            try:
                os.replace(temporary_path, destination)
            except OSError as error:
                raise AssetDownloadIOError(f"asset finalization failed: {error}") from error
            temporary_path = None
            headers = getattr(response, "headers", {})
            content_type = headers.get("Content-Type", "") if hasattr(headers, "get") else ""
            return AssetDownloadResult(str(destination), digest.hexdigest(), byte_count, content_type)
        finally:
            if response is not None and hasattr(response, "close"):
                try:
                    response.close()
                except OSError:
                    pass
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)


def create_asset_acquisition_plan(manifest: AssetManifest, sourcing: AssetSourcingPlan) -> AssetAcquisitionPlan:
    if manifest.project_id != sourcing.project_id:
        raise ValueError("asset manifest and sourcing plan must have the same project_id")
    return AssetAcquisitionPlan(manifest.project_id, manifest.title, "asset-manifest.json", "asset-sourcing.json", [])


def _selected_match(sourcing: AssetSourcingPlan, asset_id: str, candidate_id: str) -> AssetCandidateMatch:
    for match in sourcing.matches:
        if match.asset_id == asset_id and match.candidate_id == candidate_id and match.relationship == "selected":
            return match
    raise ValueError("candidate must be explicitly selected before acquisition")


def _safe_filename(asset_id: str, download_url: str) -> str:
    stem = re.sub(r"[^A-Za-z0-9_.-]+", "_", asset_id).strip(".") or "asset"
    suffix = Path(urlsplit(download_url).path).suffix
    suffix = suffix if re.fullmatch(r"\.[A-Za-z0-9]{1,8}", suffix) else ".bin"
    return f"{stem}{suffix}"


def acquire_asset(
    manifest: AssetManifest,
    sourcing: AssetSourcingPlan,
    asset_id: str,
    candidate_id: str,
    output_dir: Path,
    downloader: UrlAssetDownloader,
    allow_missing_rights_metadata: bool = False,
    overwrite: bool = False,
) -> tuple[AssetManifest, AssetAcquisition]:
    entry = next((item for item in manifest.assets if item.asset_id == asset_id), None)
    if entry is None:
        raise ValueError(f"unknown manifest asset: {asset_id}")
    _selected_match(sourcing, asset_id, candidate_id)
    candidate = next((item for item in sourcing.candidates if item.candidate_id == candidate_id), None)
    if candidate is None or candidate.asset_id != asset_id:
        raise ValueError("candidate does not belong to the requested asset")
    if (not candidate.license_name.strip() or not candidate.usage_information.strip()) and not allow_missing_rights_metadata:
        raise ValueError("missing license or usage metadata; pass --allow-missing-rights-metadata to override")
    destination = output_dir / _safe_filename(asset_id, candidate.download_url)
    try:
        result = downloader.download(candidate, destination, overwrite=overwrite)
    except AssetAcquisitionError as error:
        return manifest, AssetAcquisition(asset_id, candidate_id, "failed", downloaded_at=datetime.now(timezone.utc).isoformat(), error=str(error))
    updated_entries = [
        replace(
            item,
            local_path=result.local_path,
            status="downloaded",
            source_url=candidate.url,
            source_name=candidate.source_name,
            rights_note=candidate.rights_note,
            attribution=candidate.attribution,
        )
        if item.asset_id == asset_id else item
        for item in manifest.assets
    ]
    updated_manifest = AssetManifest(manifest.project_id, manifest.title, manifest.source_production_plan, updated_entries)
    acquisition = AssetAcquisition(asset_id, candidate_id, "downloaded", result.local_path, result.sha256, result.byte_count, result.content_type, datetime.now(timezone.utc).isoformat())
    return updated_manifest, acquisition


def save_asset_acquisition_plan(plan: AssetAcquisitionPlan, project_dir: str | Path) -> tuple[Path, Path]:
    import json

    directory = Path(project_dir)
    json_path = directory / "asset-acquisitions.json"
    markdown_path = directory / "asset-acquisitions.md"
    json_path.write_text(json.dumps(plan.to_dict(), indent=2) + "\n", encoding="utf-8")
    lines = [f"# Asset acquisitions: {plan.title}", "", "| Asset | Candidate | Status | Local path | Bytes | SHA-256 | Error |", "| --- | --- | --- | --- | ---: | --- | --- |"]
    for item in plan.acquisitions:
        lines.append(f"| {item.asset_id} | {item.candidate_id} | {item.status} | {item.local_path} | {item.byte_count if item.byte_count is not None else ''} | {item.sha256} | {item.error} |")
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, markdown_path


def load_asset_acquisition_plan(project_dir: str | Path) -> AssetAcquisitionPlan:
    import json

    path = Path(project_dir) / "asset-acquisitions.json"
    if not path.is_file():
        raise FileNotFoundError(f"Asset acquisition plan not found: {path}")
    return AssetAcquisitionPlan.from_dict(json.loads(path.read_text(encoding="utf-8")))