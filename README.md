# faceless-video-machine

Free, dependency-light faceless YouTube workflow tooling.

## Step 3: High-retention script planning

Create a structured planning scaffold for an existing project. It does not generate the final script and uses only Python's standard library.

Supported formats: `explainer`, `documentary/story`, `case study`, `timeline / what happened`, and `list video`.

Pacing options are `slow` (125 words/minute), `standard` (150), and `fast` (175). Duration is configurable and defaults to the project's duration or 8 minutes.

```bash
fvm create-script-plan \
  --project why-cities-are-getting-hotter \
  --format explainer \
  --duration 8 \
  --pacing standard \
  --premise "Reveal why familiar city design creates an invisible heat trap" \
  --question "Why are some city blocks dramatically hotter than others?"
```

The command writes `script-plan.json` and `script-plan.md` inside the project directory. View or export the plan:

```bash
fvm script-plan --project why-cities-are-getting-hotter
fvm script-plan --project why-cities-are-getting-hotter --format json --output plan-export.json
```

The plan contains the premise, audience, word-count/runtime target, cold open, curiosity question, context, reveals, loops, pattern interrupts, payoff, conclusion, call to action, and retention checklist. The checklist flags generic introductions, weak opens, missing questions, empty sections, missing payoff, and overly long cold opens.

### Tests

```bash
python -m unittest discover -s tests -v
```

No AI APIs, paid services, external dependencies, TTS, video generation, thumbnails, or final script generation are included.
