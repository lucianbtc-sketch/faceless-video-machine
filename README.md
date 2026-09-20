# faceless-video-machine

A free, dependency-light toolkit for planning faceless YouTube videos.

## Step 1: Create a video project

This first version provides a standard-library-only Python package with a small CLI. It creates a project directory containing structured JSON data and a readable Markdown brief.

### Requirements

- Python 3.11 or newer
- No third-party dependencies

### Install locally

From the repository root:

```bash
python -m pip install -e .
```

### Create a project

```bash
fvm create-project \
  --title "Why Cities Are Getting Hotter" \
  --topic "The urban heat island effect" \
  --audience "Curious general viewers" \
  --format explainer \
  --duration 8
```

The command creates a slugged directory under `projects/` by default:

```text
projects/why-cities-are-getting-hotter/
├── brief.json
└── brief.md
```

The same command can be run without installation using the module entry point:

```bash
python -m faceless_video_machine create-project --title "My first video"
```

Use `--projects-dir` to store projects elsewhere. The command refuses to overwrite an existing project directory.

### Run tests

```bash
python -m unittest discover -s tests -v
```

## Scope

Currently this repository only implements project creation and the underlying data model. Research, AI integrations, text-to-speech, video generation, thumbnails, batching, and other workflow features are intentionally not included yet.
