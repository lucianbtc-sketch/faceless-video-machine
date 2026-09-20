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

The draft includes the cold open, hook, context, curiosity loops, progressive reveals, pattern interrupts, payoff, conclusion, CTA, sourced facts, and references. A future free/local provider can implement the `ScriptProvider` interface without changing the CLI's project layout.

### Existing workflow commands

- `create-project`
- `add-source`
- `add-idea`
- `research-brief`
- `create-script-plan`
- `script-plan`
- `generate-script`
- `script`

### Tests

```bash
python -m unittest discover -s tests -v
```

No Claude, OpenAI, ElevenLabs, paid APIs, TTS, video generation, thumbnails, or subscription services are used.
