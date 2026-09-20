"""Command-line interface for the project and research workflows."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .models import ResearchSource, VideoProject
from .projects import create_project, slugify
from .research import ResearchBrief, export_research, load_research, save_research


def _project_dir(projects_dir: str, project_id: str) -> Path:
    path = Path(projects_dir) / project_id
    if not path.is_dir():
        raise FileNotFoundError(f"Project not found: {path}")
    return path


def _load_project_title(project_dir: Path) -> str:
    brief = project_dir / "brief.json"
    if not brief.exists():
        return project_dir.name
    return VideoProject.from_dict(json.loads(brief.read_text(encoding="utf-8"))).title


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fvm", description="Create and manage faceless video project briefs.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    create = subparsers.add_parser("create-project", help="create a project directory with JSON and Markdown briefs")
    create.add_argument("--title", required=True)
    create.add_argument("--topic", default="")
    create.add_argument("--audience", default="")
    create.add_argument("--format", dest="video_format", default="explainer")
    create.add_argument("--duration", type=float)
    create.add_argument("--notes", default="")
    create.add_argument("--projects-dir", default="projects")

    source = subparsers.add_parser("add-source", help="record a source and its facts for an existing project")
    source.add_argument("--project", required=True, help="project ID, usually the title slug")
    source.add_argument("--url", required=True)
    source.add_argument("--title", required=True, help="source title or publisher name")
    source.add_argument("--notes", default="")
    source.add_argument("--key-fact", action="append", default=[], help="repeat for multiple sourced facts")
    source.add_argument("--citation", default="", help="citation or reference text")
    source.add_argument("--projects-dir", default="projects")

    idea = subparsers.add_parser("add-idea", help="record a generated idea separately from sourced facts")
    idea.add_argument("--project", required=True)
    idea.add_argument("idea")
    idea.add_argument("--projects-dir", default="projects")

    research = subparsers.add_parser("research-brief", help="display or export a project's research brief")
    research.add_argument("--project", required=True)
    research.add_argument("--format", choices=("markdown", "json"), default="markdown")
    research.add_argument("--output", help="optional output file; defaults to research.md for Markdown")
    research.add_argument("--projects-dir", default="projects")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "create-project":
            project = VideoProject(project_id=slugify(args.title), title=args.title, topic=args.topic, audience=args.audience, video_format=args.video_format, duration_minutes=args.duration, notes=args.notes)
            destination = create_project(project, args.projects_dir)
            print(f"Created project: {destination}")
            print(f"JSON brief: {destination / 'brief.json'}")
            print(f"Markdown brief: {destination / 'brief.md'}")
            return 0

        project_dir = _project_dir(args.projects_dir, args.project)
        brief = load_research(project_dir, args.project)
        if args.command == "add-source":
            brief.sources.append(ResearchSource(url=args.url, title=args.title, notes=args.notes, key_facts=args.key_fact, citation=args.citation))
            save_research(brief, project_dir)
            export_research(brief, project_dir, _load_project_title(project_dir))
            print(f"Added source to {project_dir / 'research.json'}")
            return 0
        if args.command == "add-idea":
            brief.generated_ideas.append(args.idea)
            save_research(brief, project_dir)
            export_research(brief, project_dir, _load_project_title(project_dir))
            print(f"Added generated idea to {project_dir / 'research.json'}")
            return 0
        if args.command == "research-brief":
            if args.format == "json":
                content = json.dumps(brief.to_dict(), indent=2) + "\n"
                default_output = project_dir / "research.json"
            else:
                content = export_research(brief, project_dir, _load_project_title(project_dir)).read_text(encoding="utf-8")
                default_output = project_dir / "research.md"
            if args.output:
                Path(args.output).write_text(content, encoding="utf-8")
                print(f"Exported research brief: {args.output}")
            else:
                print(content, end="")
            return 0
    except (FileExistsError, FileNotFoundError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
