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
