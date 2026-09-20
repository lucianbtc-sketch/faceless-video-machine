"""Standard-library script planning and retention checks."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

PACING_WPM = {"slow": 125, "standard": 150, "fast": 175}
FORMATS = (
    "explainer",
    "documentary/story",
    "case study",
    "timeline / what happened",
    "list video",
)


@dataclass(slots=True)
class ScriptPlan:
    project_id: str
    format: str
    pacing: str
    target_duration_minutes: float
    target_word_count: int
    working_premise: str
    target_audience: str
    cold_open: str
    main_curiosity_question: str
    context: str
    progressive_reveals: list[str] = field(default_factory=list)
    curiosity_loops: list[str] = field(default_factory=list)
    pattern_interrupts: list[str] = field(default_factory=list)
    payoff: str = ""
    conclusion: str = ""
    call_to_action: str = ""
    retention_flags: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.format not in FORMATS:
            raise ValueError(f"unsupported script format: {self.format}")
        if self.pacing not in PACING_WPM:
            raise ValueError(f"unsupported pacing: {self.pacing}")
        if self.target_duration_minutes <= 0 or self.target_word_count <= 0:
            raise ValueError("duration and word count must be greater than zero")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ScriptPlan":
        return cls(**data)


def estimate_word_count(duration_minutes: float, pacing: str) -> int:
    if pacing not in PACING_WPM:
        raise ValueError(f"unsupported pacing: {pacing}")
    if duration_minutes <= 0:
        raise ValueError("duration must be greater than zero")
    return round(duration_minutes * PACING_WPM[pacing])


def retention_checklist(plan: ScriptPlan) -> list[str]:
    flags: list[str] = []
    generic = {"", "today we are going to talk about this topic", "in this video we will discuss this topic"}
    if plan.cold_open.strip().lower() in generic:
        flags.append("Weak or missing cold open")
    if not plan.main_curiosity_question.strip():
        flags.append("Missing curiosity question")
    if not plan.working_premise.strip():
        flags.append("Generic or missing introduction/premise")
    for name, value in (("Context", plan.context), ("Payoff", plan.payoff), ("Conclusion", plan.conclusion), ("Call to action", plan.call_to_action)):
        if not value.strip():
            flags.append(f"Section with no clear purpose: {name}")
    if not plan.progressive_reveals:
        flags.append("No progressive reveals")
    if not plan.curiosity_loops:
        flags.append("No curiosity loops")
    if not plan.pattern_interrupts:
        flags.append("No pattern interrupts")
    if not plan.payoff.strip():
        flags.append("Missing payoff")
    if len(plan.cold_open.split()) > max(30, round(plan.target_word_count * 0.10)):
        flags.append("Excessive intro length")
    return flags


def _format_name(value: str) -> str:
    aliases = {"documentary": "documentary/story", "case-study": "case study", "timeline": "timeline / what happened", "list": "list video"}
    value = aliases.get(value.strip().lower(), value.strip().lower())
    if value not in FORMATS:
        raise ValueError(f"unsupported script format: {value}")
    return value


def create_script_plan(project_id: str, title: str, topic: str, audience: str, video_format: str = "explainer", duration_minutes: float = 8.0, pacing: str = "standard", premise: str = "", question: str = "") -> ScriptPlan:
    fmt = _format_name(video_format)
    subject = topic or title
    plan = ScriptPlan(
        project_id=project_id,
        format=fmt,
        pacing=pacing,
        target_duration_minutes=duration_minutes,
        target_word_count=estimate_word_count(duration_minutes, pacing),
        working_premise=premise or f"Reveal the central tension behind {subject}.",
        target_audience=audience or "General viewers interested in the topic",
        cold_open=f"Open with the most surprising consequence of {subject}, before explaining the background.",
        main_curiosity_question=question or f"Why does {subject} matter, and what is the surprising answer?",
        context=f"Give only the context needed to understand {subject}; avoid a long preamble.",
        progressive_reveals=["Establish the expected explanation.", "Introduce evidence that complicates it.", "Reveal the least expected factor."],
        curiosity_loops=["Promise the answer to the main question early.", "Open a smaller question before each reveal and resolve it after the next beat."],
        pattern_interrupts=["Change the visual or example every 20–40 seconds.", "Use a contrast, question, quote, or data point between major beats."],
        payoff="Resolve the main curiosity question and connect the final reveal to the opening.",
        conclusion="Restate the key takeaway and why it matters to the audience.",
        call_to_action="Invite viewers to comment with their interpretation or suggest a related topic.",
    )
    plan.retention_flags = retention_checklist(plan)
    return plan


def render_script_plan_markdown(plan: ScriptPlan) -> str:
    def bullets(items: list[str]) -> str:
        return "\n".join(f"- {item}" for item in items) or "- None planned"
    flags = bullets(plan.retention_flags) if plan.retention_flags else "- No current flags"
    return f"""# Script plan: {plan.project_id}

> Planning scaffold only; this is not the final script.

## Planning settings

| Field | Value |
| --- | --- |
| Format | {plan.format} |
| Pacing | {plan.pacing} ({PACING_WPM[plan.pacing]} words/minute) |
| Target duration | {plan.target_duration_minutes:g} minutes |
| Target word count | {plan.target_word_count} |
| Target audience | {plan.target_audience} |

## Working premise
{plan.working_premise}

## Cold open / first 5 seconds
{plan.cold_open}

## Main curiosity question
{plan.main_curiosity_question}

## Context
{plan.context}

## Progressive reveals
{bullets(plan.progressive_reveals)}

## Curiosity loops
{bullets(plan.curiosity_loops)}

## Pattern interrupts
{bullets(plan.pattern_interrupts)}

## Payoff
{plan.payoff}

## Conclusion
{plan.conclusion}

## Call to action
{plan.call_to_action}

## Retention checklist
{flags}
"""


def save_script_plan(plan: ScriptPlan, project_dir: str | Path) -> tuple[Path, Path]:
    directory = Path(project_dir)
    json_path, markdown_path = directory / "script-plan.json", directory / "script-plan.md"
    json_path.write_text(json.dumps(plan.to_dict(), indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(render_script_plan_markdown(plan), encoding="utf-8")
    return json_path, markdown_path


def load_script_plan(project_dir: str | Path) -> ScriptPlan:
    path = Path(project_dir) / "script-plan.json"
    if not path.is_file():
        raise FileNotFoundError(f"Script plan not found: {path}")
    return ScriptPlan.from_dict(json.loads(path.read_text(encoding="utf-8")))
