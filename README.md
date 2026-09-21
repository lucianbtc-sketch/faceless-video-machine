# faceless-video-machine

Free, dependency-light faceless YouTube workflow tooling.

## Step 4: Free AI-assisted script generation

Step 4 adds a provider interface and a deterministic `TemplateProvider`. It requires no API key, model download, external service, or subscription. The provider turns an existing research brief and script plan into a structured draft; it does not pretend that generated ideas are sourced facts and does not generate unsupported factual claims.

Create a plan first, then generate a draft:

```bash
fvm create-script-plan --project why-cities-are-getting-hotter --format explainer --duration 8 --pacing standard
fvm generate-script --project why-cities-are-getting-hotter
```

The result is saved inside the project directory as:

```text
script.json
script.md
```

View or export the draft:

```bash
fvm script --project why-cities-are-getting-hotter
fvm script --project why-cities-are-getting-hotter --format json --output script-export.json
```

Create an editable narration and visual-notes script directly from the plan:

```bash
fvm create-video-script --project why-cities-are-getting-hotter
fvm video-script --project why-cities-are-getting-hotter
fvm video-script --project why-cities-are-getting-hotter --format json --output video-script-export.json
```

This saves `video-script.json` and `video-script.md`. Each Hook, Introduction, main section, Transition, Conclusion, and Call to action has editable narration, optional visual/B-roll notes, estimated words, and estimated duration. The files are plain JSON and Markdown and can be edited offline.

Create an editable production shot list from the video script:

```bash
fvm create-production-plan --project why-cities-are-getting-hotter
fvm production-plan --project why-cities-are-getting-hotter
fvm production-plan --project why-cities-are-getting-hotter --format json --output production-export.json
```

This saves `production.json` and `production.md`. The shot list starts with one scene per script section and includes scene numbers, narration references, estimated durations, visual/B-roll direction, asset types, on-screen text, and optional notes. Narration remains in `video-script.json`, which is the authoritative source.

Create an offline asset manifest from the production shot list:

```bash
fvm create-asset-manifest --project why-cities-are-getting-hotter
fvm asset-manifest --project why-cities-are-getting-hotter
fvm asset-manifest --project why-cities-are-getting-hotter --format json --output asset-manifest-export.json
```

This saves `asset-manifest.json` and `asset-manifest.md`. It creates one initial requirement per production scene with a deterministic asset ID, source and local-path fields, lifecycle status, rights metadata, attribution, and notes. The manifest is metadata-only: it does not search for, download, inspect, or validate assets. `production.json` remains the authoritative production-plan source.

Initialize and edit an offline asset-candidate plan:

```bash
fvm create-asset-candidates --project why-cities-are-getting-hotter
fvm asset-candidates --project why-cities-are-getting-hotter
fvm add-asset-candidate --project why-cities-are-getting-hotter --asset-id scene-001-asset-001 --candidate-id candidate-001 --source-id manual-notes --source-name "Manual notes" --url "https://example.invalid/item" --title "Recorded candidate" --license "" --usage ""
fvm link-asset-candidate --project why-cities-are-getting-hotter --asset-id scene-001-asset-001 --candidate-id candidate-001 --relationship shortlisted
fvm asset-candidates --project why-cities-are-getting-hotter --format json --output asset-sourcing-export.json
```

This saves `asset-sourcing.json` and `asset-sourcing.md`. It records candidate URLs, source metadata, creators, license and usage information, previews, attribution, rights notes, and editorial relationships. Missing rights metadata stays explicitly missing. `selected` means editorial selection only; it is not legal approval. This layer never fetches, scrapes, downloads, inspects, or validates URLs, and never changes `asset-manifest.json` statuses.

Optionally search Wikimedia Commons for candidate metadata:

```bash
export FVM_WIKIMEDIA_USER_AGENT="faceless-video-machine/0.1 (you@example.com)"
fvm search-asset-candidates --project why-cities-are-getting-hotter --asset-id scene-001-asset-001 --limit 5
```

The adapter uses the official Wikimedia Commons Action API and stores file-page URLs, previews, creators, and license metadata in `asset-sourcing.json`. It does not require an API key, download media, or change asset-manifest statuses. A meaningful User-Agent is required; optional settings include `FVM_WIKIMEDIA_API_URL`, `FVM_WIKIMEDIA_TIMEOUT_SECONDS`, `FVM_WIKIMEDIA_REQUEST_INTERVAL_SECONDS`, and `FVM_WIKIMEDIA_MAX_RESULTS`. License and attribution data must still be reviewed on each file page. Candidates are not legally cleared, and `selected` remains an editorial choice only.

Acquire one explicitly selected candidate into the local asset library:

```bash
fvm acquire-asset --project why-cities-are-getting-hotter --asset-id scene-001-asset-001 --candidate-id wikimedia-commons-123
fvm asset-acquisitions --project why-cities-are-getting-hotter
```

Acquisition requires an HTTP(S) `download_url`, an editorially selected candidate, and recorded license or usage metadata by default. It streams to a temporary file, enforces a byte limit, computes a SHA-256 hash, then atomically finalizes the file under `assets/`. It records history in `asset-acquisitions.json` and updates the authoritative manifest to `downloaded`, never `ready`. It does not process media or claim legal clearance. `--allow-missing-rights-metadata` only overrides the metadata block and adds no legal approval.

The draft includes the cold open, hook, context, curiosity loops, progressive reveals, pattern interrupts, payoff, conclusion, CTA, sourced facts, and references. A future free/local provider can implement the `ScriptProvider` interface without changing the CLI's project layout.

### Existing workflow commands

- `create-project`
- `add-source`
- `add-idea`
- `research-brief`
- `create-script-plan`
- `script-plan`
- `create-video-script`
- `video-script`
- `create-production-plan`
- `production-plan`
- `create-asset-manifest`
- `asset-manifest`
- `create-asset-candidates`
- `asset-candidates`
- `add-asset-candidate`
- `link-asset-candidate`
- `search-asset-candidates`
- `acquire-asset`
- `asset-acquisitions`
- `generate-script`
- `script`

### Tests

```bash
python -m unittest discover -s tests -v
```

No Claude, OpenAI, ElevenLabs, paid APIs, TTS, video generation, thumbnails, or subscription services are used.
