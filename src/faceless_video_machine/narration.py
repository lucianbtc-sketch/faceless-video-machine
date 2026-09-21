"""Manage user-provided local narration files without recording or TTS."""

from __future__ import annotations

import json
import wave
from dataclasses import replace
from pathlib import Path

from .models import NarrationPlan, NarrationSegment, NarrationValidationResult, VideoScript


def create_narration_plan(script: VideoScript) -> NarrationPlan:
    return NarrationPlan(
        script.project_id,
        script.title,
        "video-script.json",
        [NarrationSegment(f"segment-{index:03d}", index) for index, _ in enumerate(script.sections, 1)],
    )


def add_narration(
    plan: NarrationPlan,
    script: VideoScript,
    section_index: int,
    local_path: str,
    duration_seconds: float | None = None,
    notes: str = "",
) -> NarrationPlan:
    if section_index <= 0 or section_index > len(script.sections):
        raise ValueError(f"unknown script section: {section_index}")
    if not local_path.strip():
        raise ValueError("local_path cannot be empty")
    segments = [
        replace(segment, local_path=local_path, status="recorded", duration_seconds=duration_seconds, notes=notes)
        if segment.script_section_index == section_index else segment
        for segment in plan.segments
    ]
    if not any(segment.script_section_index == section_index for segment in plan.segments):
        raise ValueError(f"narration segment not found for script section: {section_index}")
    return NarrationPlan(plan.project_id, plan.title, plan.source_script, segments)


def validate_narration(plan: NarrationPlan, script: VideoScript) -> tuple[NarrationPlan, NarrationValidationResult]:
    checks: list[str] = []
    errors: list[str] = []
    if plan.project_id != script.project_id:
        errors.append("narration plan and script must have the same project_id")
    if len(plan.segments) != len(script.sections):
        errors.append("narration plan must contain one segment per script section")

    updated: list[NarrationSegment] = []
    for segment in plan.segments:
        if segment.script_section_index > len(script.sections):
            errors.append(f"unknown script section: {segment.script_section_index}")
            updated.append(segment)
            continue
        if not segment.local_path.strip():
            errors.append(f"missing narration file for section {segment.script_section_index}")
            updated.append(segment)
            continue
        path = Path(segment.local_path)
        if not path.exists():
            errors.append(f"narration file does not exist: {segment.local_path}")
            updated.append(segment)
            continue
        if not path.is_file():
            errors.append(f"narration path is not a regular file: {segment.local_path}")
            updated.append(segment)
            continue
        if path.stat().st_size == 0:
            errors.append(f"narration file is empty: {segment.local_path}")
            updated.append(segment)
            continue

        duration = segment.duration_seconds
        if path.suffix.lower() == ".wav":
            try:
                with wave.open(str(path), "rb") as audio:
                    frame_rate = audio.getframerate()
                    frame_count = audio.getnframes()
                if frame_rate <= 0 or frame_count <= 0:
                    raise ValueError("WAV has no audio frames")
                duration = frame_count / frame_rate
                checks.append(f"WAV duration read for section {segment.script_section_index}")
            except (OSError, EOFError, wave.Error, ValueError) as error:
                errors.append(f"invalid WAV narration for section {segment.script_section_index}: {error}")
                updated.append(segment)
                continue
        elif duration is None or duration <= 0:
            errors.append(f"non-WAV narration needs a positive manual duration for section {segment.script_section_index}")
            updated.append(segment)
            continue
        else:
            checks.append(f"manual duration recorded for section {segment.script_section_index}")
        checks.append(f"narration file exists for section {segment.script_section_index}")
        updated.append(replace(segment, status="validated", duration_seconds=duration))

    result = NarrationValidationResult(not errors, checks, errors)
    return (NarrationPlan(plan.project_id, plan.title, plan.source_script, updated) if result.valid else plan), result


def render_narration_markdown(plan: NarrationPlan) -> str:
    lines = [
        f"# Narration: {plan.title}",
        "",
        f"> Project: `{plan.project_id}` | Source script: `{plan.source_script}`",
        "",
        "User-provided local narration only. No TTS or recording is performed.",
        "",
        "| Segment | Script section | Status | Local path | Duration | Notes |",
        "| --- | ---: | --- | --- | ---: | --- |",
    ]
    for segment in plan.segments:
        duration = f"{segment.duration_seconds:g}s" if segment.duration_seconds is not None else ""
        lines.append(f"| {segment.segment_id} | {segment.script_section_index} | {segment.status} | {segment.local_path} | {duration} | {segment.notes} |")
    return "\n".join(lines) + "\n"


def save_narration_plan(plan: NarrationPlan, project_dir: str | Path) -> tuple[Path, Path]:
    directory = Path(project_dir)
    json_path = directory / "narration.json"
    markdown_path = directory / "narration.md"
    json_path.write_text(json.dumps(plan.to_dict(), indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(render_narration_markdown(plan), encoding="utf-8")
    return json_path, markdown_path


def load_narration_plan(project_dir: str | Path) -> NarrationPlan:
    path = Path(project_dir) / "narration.json"
    if not path.is_file():
        raise FileNotFoundError(f"Narration plan not found: {path}")
    return NarrationPlan.from_dict(json.loads(path.read_text(encoding="utf-8")))