"""Dependency-free local integrity validation for acquired assets."""

from __future__ import annotations

import hashlib
from dataclasses import replace
from pathlib import Path

from .models import AssetAcquisitionPlan, AssetManifest, AssetValidationResult


def validate_asset(
    manifest: AssetManifest,
    acquisitions: AssetAcquisitionPlan,
    asset_id: str,
) -> tuple[AssetManifest, AssetValidationResult]:
    """Validate one downloaded asset and promote it to ready only on success."""
    entry = next((item for item in manifest.assets if item.asset_id == asset_id), None)
    if entry is None:
        raise ValueError(f"unknown manifest asset: {asset_id}")

    checks: list[str] = []
    errors: list[str] = []
    if entry.status != "downloaded":
        errors.append(f"asset status must be downloaded, got {entry.status}")
    else:
        checks.append("manifest status is downloaded")

    record = next(
        (
            item
            for item in reversed(acquisitions.acquisitions)
            if item.asset_id == asset_id and item.status == "downloaded"
        ),
        None,
    )
    if record is None:
        errors.append("successful acquisition record not found")
    elif record.local_path != entry.local_path:
        errors.append("acquisition local path does not match manifest local path")
    else:
        checks.append("acquisition record matches manifest")

    if not entry.local_path.strip():
        errors.append("local path is missing")
    else:
        path = Path(entry.local_path)
        if not path.exists():
            errors.append("local file does not exist")
        elif not path.is_file():
            errors.append("local path is not a regular file")
        else:
            digest = hashlib.sha256()
            byte_count = 0
            try:
                with path.open("rb") as source:
                    while chunk := source.read(64 * 1024):
                        byte_count += len(chunk)
                        digest.update(chunk)
            except OSError as error:
                errors.append(f"local file could not be read: {error}")
            else:
                if byte_count == 0:
                    errors.append("local file is empty")
                else:
                    checks.append("local file exists and is readable")
                if record is not None:
                    if record.byte_count != byte_count:
                        errors.append("byte count does not match acquisition record")
                    else:
                        checks.append("byte count matches acquisition record")
                    if record.sha256 != digest.hexdigest():
                        errors.append("SHA-256 does not match acquisition record")
                    else:
                        checks.append("SHA-256 matches acquisition record")

    result = AssetValidationResult(asset_id, not errors, checks, errors)
    if not result.valid:
        return manifest, result

    updated_entries = [
        replace(item, status="ready") if item.asset_id == asset_id else item
        for item in manifest.assets
    ]
    return AssetManifest(manifest.project_id, manifest.title, manifest.source_production_plan, updated_entries), result