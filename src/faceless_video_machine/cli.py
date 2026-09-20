"""CLI for project, research, planning, and draft-generation workflows."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .models import ResearchSource, VideoProject
from .projects import create_project, slugify
from .production_planning import create_production_plan, load_production_plan, render_production_plan_markdown, save_production_plan
from .research import export_research, load_research, save_research
from .script_generation import TemplateProvider, load_script_draft, render_script_markdown, save_script_draft
from .script_drafting import create_video_script, load_video_script, render_video_script_markdown, save_video_script
from .script_planning import create_script_plan, load_script_plan, render_script_plan_markdown, save_script_plan


def project_dir(root: str, project_id: str) -> Path:
    path = Path(root) / project_id
    if not path.is_dir():
        raise FileNotFoundError(f"Project not found: {path}")
    return path


def load_project(path: Path) -> VideoProject:
    brief = path / "brief.json"
    if not brief.is_file():
        raise FileNotFoundError(f"Project brief not found: {brief}")
    return VideoProject.from_dict(json.loads(brief.read_text(encoding="utf-8")))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fvm")
    subs = parser.add_subparsers(dest="command", required=True)
    create = subs.add_parser("create-project")
    create.add_argument("--title", required=True); create.add_argument("--topic", default=""); create.add_argument("--audience", default="")
    create.add_argument("--format", dest="video_format", default="explainer"); create.add_argument("--duration", type=float); create.add_argument("--notes", default=""); create.add_argument("--projects-dir", default="projects")
    source = subs.add_parser("add-source")
    source.add_argument("--project", required=True); source.add_argument("--url", required=True); source.add_argument("--title", required=True); source.add_argument("--notes", default=""); source.add_argument("--key-fact", action="append", default=[]); source.add_argument("--citation", default=""); source.add_argument("--projects-dir", default="projects")
    idea = subs.add_parser("add-idea"); idea.add_argument("--project", required=True); idea.add_argument("idea"); idea.add_argument("--projects-dir", default="projects")
    research = subs.add_parser("research-brief"); research.add_argument("--project", required=True); research.add_argument("--format", choices=("markdown", "json"), default="markdown"); research.add_argument("--output"); research.add_argument("--projects-dir", default="projects")
    plan = subs.add_parser("create-script-plan")
    plan.add_argument("--project", required=True); plan.add_argument("--format", dest="script_format"); plan.add_argument("--duration", type=float); plan.add_argument("--pacing", choices=("slow", "standard", "fast"), default="standard"); plan.add_argument("--premise", default=""); plan.add_argument("--question", default=""); plan.add_argument("--projects-dir", default="projects")
    view_plan = subs.add_parser("script-plan"); view_plan.add_argument("--project", required=True); view_plan.add_argument("--format", choices=("markdown", "json"), default="markdown"); view_plan.add_argument("--output"); view_plan.add_argument("--projects-dir", default="projects")
    draft = subs.add_parser("create-video-script", help="create an editable script from the project plan")
    draft.add_argument("--project", required=True); draft.add_argument("--projects-dir", default="projects")
    view_video_script = subs.add_parser("video-script", help="display or export an editable video script")
    view_video_script.add_argument("--project", required=True); view_video_script.add_argument("--format", choices=("markdown", "json"), default="markdown"); view_video_script.add_argument("--output"); view_video_script.add_argument("--projects-dir", default="projects")
    production = subs.add_parser("create-production-plan", help="create an editable production shot list from the video script")
    production.add_argument("--project", required=True); production.add_argument("--projects-dir", default="projects")
    view_production = subs.add_parser("production-plan", help="display or export an editable production shot list")
    view_production.add_argument("--project", required=True); view_production.add_argument("--format", choices=("markdown", "json"), default="markdown"); view_production.add_argument("--output"); view_production.add_argument("--projects-dir", default="projects")
    generate = subs.add_parser("generate-script", help="generate a structured draft with the free TemplateProvider")
    generate.add_argument("--project", required=True); generate.add_argument("--projects-dir", default="projects")
    view_script = subs.add_parser("script", help="display or export an existing structured script draft")
    view_script.add_argument("--project", required=True); view_script.add_argument("--format", choices=("markdown", "json"), default="markdown"); view_script.add_argument("--output"); view_script.add_argument("--projects-dir", default="projects")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "create-project":
            project = VideoProject(slugify(args.title), args.title, args.topic, args.audience, args.video_format, args.duration, args.notes)
            destination = create_project(project, args.projects_dir); print(f"Created project: {destination}"); return 0
        path = project_dir(args.projects_dir, args.project)
        if args.command == "create-script-plan":
            project = load_project(path)
            plan = create_script_plan(project.project_id, project.title, project.topic, project.audience, args.script_format or project.video_format, args.duration or project.duration_minutes or 8.0, args.pacing, args.premise, args.question)
            json_path, markdown_path = save_script_plan(plan, path); print(f"Created script plan: {json_path}"); print(f"Markdown plan: {markdown_path}"); return 0
        if args.command == "script-plan":
            plan = load_script_plan(path); content = json.dumps(plan.to_dict(), indent=2) + "\n" if args.format == "json" else render_script_plan_markdown(plan)
            if args.output: Path(args.output).write_text(content, encoding="utf-8"); print(f"Exported script plan: {args.output}")
            else: print(content, end="")
            return 0
        if args.command == "create-video-script":
            project = load_project(path); plan = load_script_plan(path)
            json_path, markdown_path = save_video_script(create_video_script(project, plan), path)
            print(f"Created video script: {json_path}"); print(f"Markdown script: {markdown_path}"); return 0
        if args.command == "video-script":
            script = load_video_script(path); content = json.dumps(script.to_dict(), indent=2) + "\n" if args.format == "json" else render_video_script_markdown(script)
            if args.output: Path(args.output).write_text(content, encoding="utf-8"); print(f"Exported video script: {args.output}")
            else: print(content, end="")
            return 0
        if args.command == "create-production-plan":
            script = load_video_script(path)
            json_path, markdown_path = save_production_plan(create_production_plan(script), path)
            print(f"Created production plan: {json_path}"); print(f"Markdown shot list: {markdown_path}"); return 0
        if args.command == "production-plan":
            plan = load_production_plan(path); content = json.dumps(plan.to_dict(), indent=2) + "\n" if args.format == "json" else render_production_plan_markdown(plan)
            if args.output: Path(args.output).write_text(content, encoding="utf-8"); print(f"Exported production plan: {args.output}")
            else: print(content, end="")
            return 0
        if args.command == "generate-script":
            project = load_project(path); plan = load_script_plan(path); brief = load_research(path, project.project_id)
            json_path, markdown_path = save_script_draft(TemplateProvider().generate(brief, plan), path)
            print(f"Generated script draft: {json_path}"); print(f"Markdown draft: {markdown_path}"); return 0
        if args.command == "script":
            draft = load_script_draft(path); content = json.dumps(draft.to_dict(), indent=2) + "\n" if args.format == "json" else render_script_markdown(draft)
            if args.output: Path(args.output).write_text(content, encoding="utf-8"); print(f"Exported script draft: {args.output}")
            else: print(content, end="")
            return 0
        project = load_project(path); brief = load_research(path, args.project)
        if args.command == "add-source":
            brief.sources.append(ResearchSource(args.url, args.title, args.notes, args.key_fact, args.citation)); save_research(brief, path); export_research(brief, path, project.title); print(f"Added source to {path / 'research.json'}"); return 0
        if args.command == "add-idea":
            brief.generated_ideas.append(args.idea); save_research(brief, path); export_research(brief, path, project.title); print(f"Added generated idea to {path / 'research.json'}"); return 0
        if args.command == "research-brief":
            content = json.dumps(brief.to_dict(), indent=2) + "\n" if args.format == "json" else export_research(brief, path, project.title).read_text(encoding="utf-8")
            if args.output: Path(args.output).write_text(content, encoding="utf-8"); print(f"Exported research brief: {args.output}")
            else: print(content, end="")
            return 0
    except (FileExistsError, FileNotFoundError, ValueError) as error:
        print(str(error), file=sys.stderr); return 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
