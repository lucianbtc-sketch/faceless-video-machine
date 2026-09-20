"""Research notes and source tracking for a video project."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .models import ResearchSource


@dataclass(slots=True)
class ResearchBrief:
    """A research record with sourced facts kept apart from ideas."""

    project_id: str
    sources: list[ResearchSource] = field(default_factory=list)
    generated_ideas: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "sources": [source.to_dict() for source in self.sources],
            "generated_ideas": list(self.generated_ideas),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ResearchBrief":
        return cls(
            project_id=data["project_id"],
            sources=[ResearchSource.from_dict(item) for item in data.get("sources", [])],
            generated_ideas=list(data.get("generated_ideas", [])),
        )


def research_path(project_dir: str | Path) -> Path:
    return Path(project_dir) / "research.json"


def load_research(project_dir: str | Path, project_id: str) -> ResearchBrief:
    path = research_path(project_dir)
    if not path.exists():
        return ResearchBrief(project_id=project_id)
    return ResearchBrief.from_dict(json.loads(path.read_text(encoding="utf-8")))


def save_research(brief: ResearchBrief, project_dir: str | Path) -> Path:
    path = research_path(project_dir)
    path.write_text(json.dumps(brief.to_dict(), indent=2) + "\n", encoding="utf-8")
    return path


def render_research_markdown(brief: ResearchBrief, project_title: str | None = None) -> str:
    title = project_title or brief.project_id
    lines = [f"# Research brief: {title}", "", "## Sourced facts", ""]
    if not brief.sources:
        lines.append("No sources recorded yet.")
    for index, source in enumerate(brief.sources, 1):
        lines.extend([
            f"### Source {index}: {source.title}",
            f"- URL: {source.url}",
            f"- Citation/reference: {source.citation or 'Not specified'}",
            f"- Notes: {source.notes or 'None'}",
            "- Key facts:",
        ])
        lines.extend(f"  - {fact}" for fact in (source.key_facts or []) or ["None recorded."])
        lines.append("")
    lines.extend(["## Generated ideas", ""])
    if brief.generated_ideas:
        lines.extend(f"- {idea}" for idea in brief.generated_ideas)
    else:
        lines.append("No generated ideas recorded. These are separate from sourced facts.")
    return "\n".join(lines).rstrip() + "\n"


def export_research(brief: ResearchBrief, project_dir: str | Path, project_title: str | None = None) -> Path:
    path = Path(project_dir) / "research.md"
    path.write_text(render_research_markdown(brief, project_title), encoding="utf-8")
    return path
