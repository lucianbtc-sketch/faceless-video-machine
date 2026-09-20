"""Create and persist editable video scripts from existing project plans."""

from __future__ import annotations

import json
from pathlib import Path

from .models import ScriptSection, VideoProject, VideoScript
from .script_planning import PACING_WPM, ScriptPlan


def _section(name: str, narration: str, visual_notes: str, pacing: str) -> ScriptSection:
    word_count = len(narration.split())
    duration = word_count / PACING_WPM[pacing] * 60 if word_count else 0.0
    return ScriptSection(name, narration, visual_notes, round(duration, 1), word_count)


def create_video_script(project: VideoProject, plan: ScriptPlan) -> VideoScript:
    """Turn a project and its plan into an editable narration and visual scaffold."""
    if project.project_id != plan.project_id:
        raise ValueError("project and script plan must have the same project_id")

    sections = [
        _section(
            "Hook",
            plan.cold_open,
            "Open on the most striking relevant footage, image, or data point; avoid a logo intro.",
            plan.pacing,
        ),
        _section(
            "Introduction",
            f"{plan.working_premise}\n\n{plan.main_curiosity_question}",
            "Establish the subject and show the question the viewer should keep watching to answer.",
            plan.pacing,
        ),
    ]
    for index, reveal in enumerate(plan.progressive_reveals, 1):
        sections.append(
            _section(
                f"Main section {index}",
                reveal,
                "Use evidence, archival visuals, diagrams, or screen captures that directly support this beat.",
                plan.pacing,
            )
        )
        if index < len(plan.progressive_reveals):
            transition = plan.curiosity_loops[index - 1] if index <= len(plan.curiosity_loops) else "Bridge into the next reveal with an unanswered question."
            interrupt = plan.pattern_interrupts[index - 1] if index <= len(plan.pattern_interrupts) else "Change the visual treatment before the next section."
            sections.append(_section("Transition", f"{transition}\n\n{interrupt}", "Change shot, rhythm, graphic treatment, or supporting example.", plan.pacing))

    sections.extend(
        [
            _section("Conclusion", f"{plan.payoff}\n\n{plan.conclusion}", "Return to the opening image or question and land on the central takeaway.", plan.pacing),
            _section("Call to action", plan.call_to_action, "Show a simple end card or relevant next-video visual.", plan.pacing),
        ]
    )
    return VideoScript(project.project_id, project.title, plan.target_duration_minutes, sections, plan.pacing)


def render_video_script_markdown(script: VideoScript) -> str:
    lines = [
        f"# Video script: {script.title}",
        "",
        f"> Project: `{script.project_id}` | Target duration: {script.target_duration_minutes:g} minutes | Estimated words: {script.estimated_word_count}",
        "",
    ]
    for section in script.sections:
        duration = f"{section.estimated_duration_seconds:g}s" if section.estimated_duration_seconds is not None else "not estimated"
        words = str(section.estimated_word_count) if section.estimated_word_count is not None else "not estimated"
        lines.extend([f"## {section.name}", "", f"**Estimated:** {duration} | {words} words", "", "### Narration", "", section.narration or "_No narration yet._", "", "### Visual / B-roll notes", "", section.visual_notes or "_No visual notes yet._", ""])
    return "\n".join(lines).rstrip() + "\n"


def save_video_script(script: VideoScript, project_dir: str | Path) -> tuple[Path, Path]:
    directory = Path(project_dir)
    json_path = directory / "video-script.json"
    markdown_path = directory / "video-script.md"
    json_path.write_text(json.dumps(script.to_dict(), indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(render_video_script_markdown(script), encoding="utf-8")
    return json_path, markdown_path


def load_video_script(project_dir: str | Path) -> VideoScript:
    path = Path(project_dir) / "video-script.json"
    if not path.is_file():
        raise FileNotFoundError(f"Video script not found: {path}")
    return VideoScript.from_dict(json.loads(path.read_text(encoding="utf-8")))