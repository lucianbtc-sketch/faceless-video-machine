# faceless-video-machine

A free, dependency-light toolkit for planning faceless YouTube videos.

## Step 1: Create a video project

This version provides a standard-library-only Python package with a small CLI. It creates a project directory containing structured JSON data and a readable Markdown brief.

### Requirements

- Python 3.11 or newer
- No third-party runtime dependencies

### Install locally

```bash
python -m pip install -e .
```

### Create a project

```bash
fvm create-project --title "Why Cities Are Getting Hotter" --topic "The urban heat island effect" --audience "Curious general viewers" --format explainer --duration 8
```

## Step 2: Track research and sources

Each project can have a `research.json` data file and a human-readable `research.md` brief. Sourced facts are stored under sources; generated ideas are stored separately and are never presented as sourced facts.

Add a source (repeat `--key-fact` for multiple facts):

```bash
fvm add-source --project why-cities-are-getting-hotter --url https://example.org/article --title "Example source" --notes "Useful context" --key-fact "A sourced fact" --citation "Example Organization, 2026"
```

Add a clearly separate generated idea:

```bash
fvm add-idea --project why-cities-are-getting-hotter "Compare this trend with a nearby city"
```

Display the Markdown research brief:

```bash
fvm research-brief --project why-cities-are-getting-hotter
```

Export JSON or Markdown to a chosen path:

```bash
fvm research-brief --project why-cities-are-getting-hotter --format json --output research-export.json
fvm research-brief --project why-cities-are-getting-hotter --output research-export.md
```

The commands use manually supplied information only. No APIs, API keys, scraping services, AI providers, or paid services are used.

### Run tests

```bash
python -m unittest discover -s tests -v
```

## Scope

Research tracking is implemented. AI integrations, text-to-speech, video generation, thumbnails, batching, and other later workflow features are intentionally not included yet.
