"""Core data structures for faceless video projects."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass(slots=True)
class VideoProject:
    """The metadata needed to start planning one video."""

    project_id: str
    title: str
    topic: str = ""
    audience: str = ""
    video_format: str = "explainer"
    duration_minutes: float | None = None
    notes: str = ""
    status: str = "idea"
    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.project_id.strip():
            raise ValueError("project_id cannot be empty")
        if not self.title.strip():
            raise ValueError("title cannot be empty")
        if self.duration_minutes is not None and self.duration_minutes <= 0:
            raise ValueError("duration_minutes must be greater than zero")
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation of the project."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "VideoProject":
        """Build a project from data previously saved as JSON."""
        return cls(**data)


@dataclass(slots=True)
class ScriptSection:
    """An editable part of a video script."""

    name: str
    narration: str = ""
    visual_notes: str = ""
    estimated_duration_seconds: float | None = None
    estimated_word_count: int | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("script section name cannot be empty")
        if self.estimated_duration_seconds is not None and self.estimated_duration_seconds < 0:
            raise ValueError("estimated duration cannot be negative")
        if self.estimated_word_count is not None and self.estimated_word_count < 0:
            raise ValueError("estimated word count cannot be negative")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ScriptSection":
        return cls(**data)


@dataclass(slots=True)
class VideoScript:
    """A structured, editable script associated with one project and plan."""

    project_id: str
    title: str
    target_duration_minutes: float
    sections: list[ScriptSection]
    pacing: str = "standard"

    def __post_init__(self) -> None:
        if not self.project_id.strip():
            raise ValueError("project_id cannot be empty")
        if not self.title.strip():
            raise ValueError("title cannot be empty")
        if self.target_duration_minutes <= 0:
            raise ValueError("target_duration_minutes must be greater than zero")

    @property
    def estimated_word_count(self) -> int:
        return sum(section.estimated_word_count or 0 for section in self.sections)

    @property
    def estimated_duration_seconds(self) -> float:
        return sum(section.estimated_duration_seconds or 0 for section in self.sections)

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "title": self.title,
            "target_duration_minutes": self.target_duration_minutes,
            "pacing": self.pacing,
            "sections": [section.to_dict() for section in self.sections],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "VideoScript":
        return cls(
            project_id=data["project_id"],
            title=data["title"],
            target_duration_minutes=data["target_duration_minutes"],
            pacing=data.get("pacing", "standard"),
            sections=[ScriptSection.from_dict(item) for item in data.get("sections", [])],
        )


@dataclass(slots=True)
class ResearchSource:
    """A manually recorded source and the facts taken from it."""

    url: str
    title: str
    notes: str = ""
    key_facts: list[str] | None = None
    citation: str = ""

    def __post_init__(self) -> None:
        if not self.url.strip():
            raise ValueError("source url cannot be empty")
        if not self.title.strip():
            raise ValueError("source title cannot be empty")
        if self.key_facts is None:
            self.key_facts = []

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ResearchSource":
        return cls(**data)
