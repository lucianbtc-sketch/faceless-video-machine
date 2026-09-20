"""Create and persist offline production shot lists from editable video scripts."""

from __future__ import annotations

import json
from pathlib import Path

from .models import ProductionPlan, ProductionScene, VideoScript


def _asset_type(section_name: str) -> str:
    name = section_name.strip().lower()
    if name == "call to action":
        return "text_card"
    if name == "transition":
        return "graphic"
    return "video"


def create_production_plan(script: VideoScript) -> ProductionPlan:
    """Create one editable production scene per source script section."""
    scenes = [
        ProductionScene(
            scene_number=index,
            script_section_index=index,
            narration_reference=f"VideoScript section {index}: {section.name}",
            estimated_duration_seconds=section.estimated_duration_seconds or 0.0,
            visual_direction=section.visual_notes,
            asset_type=_asset_type(section.name),
        )
        for index, section in enumerate(script.sections, 1)
    ]
    return ProductionPlan(
        project_id=script.project_id,
        title=script.title,
        target_duration_minutes=script.target_duration_minutes,
        source_script="video-script.json",
        scenes=scenes,
    )


def _cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", "<br>")


def render_production_plan_markdown(plan: ProductionPlan) -> str:
    lines = [
        f"# Production shot list: {plan.title}",
        "",
        f"> Project: `{plan.project_id}` | Source script: `{plan.source_script}` | Target duration: {plan.target_duration_minutes:g} minutes",
        "",
        "The source script remains authoritative for narration. Scene references point back to its sections.",
        "",
        "| Scene | Narration reference | Duration | Asset type | Visual / B-roll direction | On-screen text | Notes |",
        "| ---: | --- | ---: | --- | --- | --- | --- |",
    ]
    for scene in plan.scenes:
        lines.append(
            "| "
            + " | ".join(
                (
                    str(scene.scene_number),
                    _cell(scene.narration_reference),
                    f"{scene.estimated_duration_seconds:g}s",
                    scene.asset_type,
                    _cell(scene.visual_direction),
                    _cell(scene.on_screen_text),
                    _cell(scene.notes),
                )
            )
            + " |"
        )
    return "\n".join(lines) + "\n"


def save_production_plan(plan: ProductionPlan, project_dir: str | Path) -> tuple[Path, Path]:
    directory = Path(project_dir)
    json_path = directory / "production.json"
    markdown_path = directory / "production.md"
    json_path.write_text(json.dumps(plan.to_dict(), indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(render_production_plan_markdown(plan), encoding="utf-8")
    return json_path, markdown_path


def load_production_plan(project_dir: str | Path) -> ProductionPlan:
    path = Path(project_dir) / "production.json"
    if not path.is_file():
        raise FileNotFoundError(f"Production plan not found: {path}")
    return ProductionPlan.from_dict(json.loads(path.read_text(encoding="utf-8")))