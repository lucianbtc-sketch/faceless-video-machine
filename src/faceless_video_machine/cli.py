"""Command-line interface for the first project workflow."""

from __future__ import annotations

import argparse
import sys

from .models import VideoProject
from .projects import create_project, slugify


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fvm", description="Create and manage faceless video project briefs."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    create = subparsers.add_parser(
        "create-project", help="create a project directory with JSON and Markdown briefs"
    )
    create.add_argument("--title", required=True, help="working title of the video")
    create.add_argument("--topic", default="", help="topic or central question")
    create.add_argument("--audience", default="", help="intended audience")
    create.add_argument("--format", dest="video_format", default="explainer", help="video format")
    create.add_argument("--duration", type=float, help="target duration in minutes")
    create.add_argument("--notes", default="", help="initial planning notes")
    create.add_argument("--projects-dir", default="projects", help="parent directory for projects")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "create-project":
        project = VideoProject(
            project_id=slugify(args.title),
            title=args.title,
            topic=args.topic,
            audience=args.audience,
            video_format=args.video_format,
            duration_minutes=args.duration,
            notes=args.notes,
        )
        try:
            destination = create_project(project, args.projects_dir)
        except FileExistsError as error:
            print(str(error), file=sys.stderr)
            return 1
        print(f"Created project: {destination}")
        print(f"JSON brief: {destination / 'brief.json'}")
        print(f"Markdown brief: {destination / 'brief.md'}")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
