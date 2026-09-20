"""Offline asset candidate metadata and provider interfaces."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol

from .models import (
    AssetCandidate,
    AssetCandidateMatch,
    AssetManifestEntry,
    AssetManifest,
    AssetSourcingPlan,
    AssetSource,
)


class AssetSourceError(Exception):
    """Base error for a future asset source adapter."""


class AssetSourceProvider(Protocol):
    """Interface for future free-source adapters; no implementation is included."""

    source: AssetSource

    def find_candidates(self, requirement: AssetManifestEntry) -> list[AssetCandidate]:
        """Return recorded candidate metadata for one manifest requirement."""


def create_asset_sourcing_plan(manifest: AssetManifest) -> AssetSourcingPlan:
    """Initialize an empty candidate plan from the authoritative asset manifest."""
    return AssetSourcingPlan(
        project_id=manifest.project_id,
        title=manifest.title,
        source_asset_manifest="asset-manifest.json",
        sources=[],
        candidates=[],
        matches=[],
    )


def validate_asset_sourcing_plan(plan: AssetSourcingPlan, manifest: AssetManifest) -> None:
    """Validate candidate and match asset IDs against the current manifest metadata."""
    if plan.project_id != manifest.project_id:
        raise ValueError("sourcing plan and asset manifest must have the same project_id")
    asset_ids = {asset.asset_id for asset in manifest.assets}
    unknown_candidates = {candidate.asset_id for candidate in plan.candidates} - asset_ids
    unknown_matches = {match.asset_id for match in plan.matches} - asset_ids
    if unknown_candidates or unknown_matches:
        raise ValueError("sourcing plan references an unknown manifest asset")
    candidate_assets = {candidate.candidate_id: candidate.asset_id for candidate in plan.candidates}
    for match in plan.matches:
        if candidate_assets[match.candidate_id] != match.asset_id:
            raise ValueError("candidate match asset_id does not match candidate asset_id")


def add_asset_candidate(
    plan: AssetSourcingPlan,
    manifest: AssetManifest,
    candidate: AssetCandidate,
    source: AssetSource,
) -> AssetSourcingPlan:
    """Record user-provided candidate metadata without contacting its URLs."""
    validate_asset_sourcing_plan(plan, manifest)
    if candidate.asset_id not in {asset.asset_id for asset in manifest.assets}:
        raise ValueError(f"unknown manifest asset: {candidate.asset_id}")
    if candidate.source_id != source.source_id:
        raise ValueError("candidate source_id must match source source_id")
    existing_source = next((item for item in plan.sources if item.source_id == source.source_id), None)
    if existing_source is not None and existing_source.to_dict() != source.to_dict():
        raise ValueError("source ID already exists with different metadata")
    if any(item.candidate_id == candidate.candidate_id for item in plan.candidates):
        raise ValueError("candidate IDs must be unique")
    sources = list(plan.sources)
    if existing_source is None:
        sources.append(source)
    candidates = [*plan.candidates, candidate]
    return AssetSourcingPlan(plan.project_id, plan.title, plan.source_asset_manifest, sources, candidates, list(plan.matches))


def merge_asset_candidates(
    plan: AssetSourcingPlan,
    manifest: AssetManifest,
    source: AssetSource,
    candidates: list[AssetCandidate],
) -> AssetSourcingPlan:
    """Add or replace provider candidates without changing manifest statuses."""
    updated = plan
    for candidate in candidates:
        existing = next((item for item in updated.candidates if item.candidate_id == candidate.candidate_id), None)
        if existing is None:
            updated = add_asset_candidate(updated, manifest, candidate, source)
            continue
        if existing.asset_id != candidate.asset_id or existing.source_id != candidate.source_id:
            raise ValueError(f"candidate ID conflicts with existing metadata: {candidate.candidate_id}")
        replacement = [candidate if item.candidate_id == candidate.candidate_id else item for item in updated.candidates]
        updated = AssetSourcingPlan(updated.project_id, updated.title, updated.source_asset_manifest, list(updated.sources), replacement, list(updated.matches))
    return updated


def link_asset_candidate(plan: AssetSourcingPlan, manifest: AssetManifest, match: AssetCandidateMatch) -> AssetSourcingPlan:
    """Record an editorial candidate relationship without changing manifest status."""
    validate_asset_sourcing_plan(plan, manifest)
    if match.asset_id not in {asset.asset_id for asset in manifest.assets}:
        raise ValueError(f"unknown manifest asset: {match.asset_id}")
    candidate = next((item for item in plan.candidates if item.candidate_id == match.candidate_id), None)
    if candidate is None:
        raise ValueError(f"unknown candidate: {match.candidate_id}")
    if candidate.asset_id != match.asset_id:
        raise ValueError("candidate match asset_id does not match candidate asset_id")
    matches = [*plan.matches, match]
    return AssetSourcingPlan(plan.project_id, plan.title, plan.source_asset_manifest, list(plan.sources), list(plan.candidates), matches)


def _cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", "<br>")


def _recorded(value: str) -> str:
    return value if value else "Not recorded"


def render_asset_sourcing_markdown(plan: AssetSourcingPlan) -> str:
    matches = {(match.asset_id, match.candidate_id): match for match in plan.matches}
    lines = [
        f"# Asset sourcing candidates: {plan.title}",
        "",
        f"> Project: `{plan.project_id}` | Source asset manifest: `{plan.source_asset_manifest}`",
        "",
        "This is a metadata-only candidate list. It does not fetch, download, inspect, or legally clear assets.",
        "",
    ]
    for candidate in plan.candidates:
        relationship = next((match.relationship for (asset_id, candidate_id), match in matches.items() if candidate_id == candidate.candidate_id), "candidate")
        lines.extend(
            [
                f"## {candidate.candidate_id}",
                "",
                f"- Asset requirement: `{candidate.asset_id}`",
                f"- Source: {_recorded(candidate.source_name)} (`{candidate.source_id}`)",
                f"- Relationship: **{relationship}** (editorial metadata only)",
                f"- Title: {_recorded(candidate.title)}",
                f"- Creator/author: {_recorded(candidate.creator)}",
                f"- URL: {_recorded(candidate.url)}",
                f"- Preview URL: {_recorded(candidate.preview_url)}",
                f"- License: {_recorded(candidate.license_name)}",
                f"- License URL: {_recorded(candidate.license_url)}",
                f"- Usage information: {_recorded(candidate.usage_information)}",
                f"- Attribution: {_recorded(candidate.attribution)}",
                f"- Rights note: {_recorded(candidate.rights_note)}",
                f"- Notes: {_recorded(candidate.notes)}",
                "",
            ]
        )
    if not plan.candidates:
        lines.extend(["No candidates recorded.", ""])
    return "\n".join(lines)


def save_asset_sourcing_plan(plan: AssetSourcingPlan, project_dir: str | Path) -> tuple[Path, Path]:
    directory = Path(project_dir)
    json_path = directory / "asset-sourcing.json"
    markdown_path = directory / "asset-sourcing.md"
    json_path.write_text(json.dumps(plan.to_dict(), indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(render_asset_sourcing_markdown(plan), encoding="utf-8")
    return json_path, markdown_path


def load_asset_sourcing_plan(project_dir: str | Path) -> AssetSourcingPlan:
    path = Path(project_dir) / "asset-sourcing.json"
    if not path.is_file():
        raise FileNotFoundError(f"Asset sourcing plan not found: {path}")
    return AssetSourcingPlan.from_dict(json.loads(path.read_text(encoding="utf-8")))