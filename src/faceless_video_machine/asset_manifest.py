"""Create and persist offline asset metadata from a production plan."""

from __future__ import annotations

import json
from pathlib import Path

from .models import AssetManifest, AssetManifestEntry, ProductionPlan


def create_asset_manifest(plan: ProductionPlan) -> AssetManifest:
    """Create one metadata-only asset requirement for each production scene."""
    scene_numbers = [scene.scene_number for scene in plan.scenes]
    if len(scene_numbers) != len(set(scene_numbers)):
        raise ValueError("production scene numbers must be unique")

    assets = [
        AssetManifestEntry(
            asset_id=f"scene-{scene.scene_number:03d}-asset-001",
            scene_number=scene.scene_number,
            scene_reference=f"Scene {scene.scene_number}: {scene.narration_reference}",
            asset_type=scene.asset_type,
            description=scene.visual_direction or f"Primary visual asset for scene {scene.scene_number}.",
        )
        for scene in plan.scenes
    ]
    return AssetManifest(
        project_id=plan.project_id,
        title=plan.title,
        source_production_plan="production.json",
        assets=assets,
    )


def _cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", "<br>")


def _source(asset: AssetManifestEntry) -> str:
    return " / ".join(value for value in (asset.source_name, asset.source_url) if value) or ""


def render_asset_manifest_markdown(manifest: AssetManifest) -> str:
    counts = " | ".join(f"{status.title()}: {count}" for status, count in manifest.status_counts.items())
    lines = [
        f"# Asset manifest: {manifest.title}",
        "",
        f"> Project: `{manifest.project_id}` | Source production plan: `{manifest.source_production_plan}`",
        "",
        f"**Status summary:** {counts}",
        "",
        "This is an offline metadata manifest. Status values do not verify external sources or local files.",
        "",
        "| Asset ID | Scene | Type | Description | Source | Local path | Status | Rights | Attribution | Notes |",
        "| --- | ---: | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for asset in manifest.assets:
        lines.append(
            "| "
            + " | ".join(
                (
                    _cell(asset.asset_id),
                    f"{asset.scene_number}: {_cell(asset.scene_reference)}",
                    asset.asset_type,
                    _cell(asset.description),
                    _cell(_source(asset)),
                    _cell(asset.local_path),
                    asset.status,
                    _cell(asset.rights_note),
                    _cell(asset.attribution),
                    _cell(asset.notes),
                )
            )
            + " |"
        )
    return "\n".join(lines) + "\n"


def save_asset_manifest(manifest: AssetManifest, project_dir: str | Path) -> tuple[Path, Path]:
    directory = Path(project_dir)
    json_path = directory / "asset-manifest.json"
    markdown_path = directory / "asset-manifest.md"
    json_path.write_text(json.dumps(manifest.to_dict(), indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(render_asset_manifest_markdown(manifest), encoding="utf-8")
    return json_path, markdown_path


def load_asset_manifest(project_dir: str | Path) -> AssetManifest:
    path = Path(project_dir) / "asset-manifest.json"
    if not path.is_file():
        raise FileNotFoundError(f"Asset manifest not found: {path}")
    return AssetManifest.from_dict(json.loads(path.read_text(encoding="utf-8")))