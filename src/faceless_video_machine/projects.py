"""Create and persist video project files."""

from __future__ import annotations

import json
import re
from pathlib import Path

from .models import VideoProject


def slugify(value: str) -> str:
    """Convert a project title into a filesystem-friendly identifier."""
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "untitled-project"


def render_markdown(project: VideoProject) -> str:
    """Render a human-readable project brief."""
    duration = (
        f"{project.duration_minutes:g} minutes"
        if project.duration_minutes is not None
        else "Not specified"
    )
    notes = project.notes.strip() or "No notes yet."
    return f"""# {project.title}

## Project details

| Field | Value |
| --- | --- |
| Project ID | `{project.project_id}` |
| Topic | {project.topic or "Not specified"} |
| Audience | {project.audience or "Not specified"} |
| Format | {project.video_format} |
| Target duration | {duration} |
| Status | {project.status} |
| Created | {project.created_at} |

## Notes

{notes}

## Next steps

- [ ] Research topic
- [ ] Create outline
- [ ] Draft script
- [ ] Plan scenes
- [ ] Prepare voiceover
"""


def create_project(project: VideoProject, projects_dir: str | Path = "projects") -> Path:
    """Create a project directory and write its JSON and Markdown brief."""
    destination = Path(projects_dir) / project.project_id
    if destination.exists():
        raise FileExistsError(f"Project already exists: {destination}")

    destination.mkdir(parents=True)
    (destination / "brief.json").write_text(
        json.dumps(project.to_dict(), indent=2) + "\n", encoding="utf-8"
    )
    (destination / "brief.md").write_text(
        render_markdown(project), encoding="utf-8"
    )
    return destination
