# Session 2: Agentic pipelines on Union

Two chapters. First you build a durable agent step by step and ship it behind a
hosted chat UI; then you use your CLI agent to run, inspect, and repair a
deliberately broken workflow. Chapter 1 is a notebook plus two standalone scripts;
chapter 2 is a hands-on exercise in scripts.

| Chapter | Notebook | Scripts | Covers |
|---------|----------|---------|--------|
| 1 · Agentic pipelines | [`notebooks/01_agentic_pipeline.ipynb`](./notebooks/01_agentic_pipeline.ipynb) | [`01_agentic_pipeline.py`](./workflows/01_agentic_pipeline.py) · [`01_ui_chat.py`](./workflows/01_ui_chat.py) | Build a durable agent: a `@flyte.trace` step → hand-rolled tool loop → the `Agent` harness → a parallel plan/fan-out/synthesize pipeline → shipping it behind a hosted chat UI |
| 2 · Agentic dev on Union | (CLI exercise) | [`02_fix_broken_workflow.py`](./workflows/02_fix_broken_workflow.py) | Run, inspect, and repair a deliberately broken Flyte 2.0 workflow with your CLI agent (the **flyte-sdk-author** skill plus the **flyte-docs** and **flyte-cluster** MCP servers). |

How the pieces fit together:

- **Chapter 1**: the notebook is the guided build. `01_agentic_pipeline.py` is the
  same research pipeline as a runnable script (entrypoint `research`), and
  `01_ui_chat.py` serves a `flyte.ai.agents.Agent` behind Flyte's built-in chat UI.
- **Chapter 2**: a debugging loop, no notebook. `02_fix_broken_workflow.py` fails on
  the cluster; the prompt at the top of that file tells your CLI agent to run it, read
  the failed run, and fix it.

## Setup

```bash
cd workflows      # or notebooks; each has its own .flyte/config.yaml
uv sync
```

`.flyte/config.yaml` ships as a blank template; fill in your cluster's
`endpoint` / `org` / `project` / `domain` (or run `flyte create config`) before
running remotely. The agent examples need an Anthropic API key as a Flyte secret;
note the scripts reference **different keys**, so create whichever you run:

```bash
flyte create secret ANTHROPIC_API_KEY          # used by 01_agentic_pipeline.py
```

## Running

```bash
# Chapter 1: the pipeline (entrypoint `research`)
uv run flyte run 01_agentic_pipeline.py research --question "Should we expand into the EU market?"

# Chapter 1: the hosted chat UI (self-contained; uv reads its inline deps)
uv run 01_ui_chat.py                              # deploys the chat app and prints its URL

# Chapter 2: the fix exercise (entrypoint `main`)
uv run flyte run 02_fix_broken_workflow.py main   # fails until fixed; inspect the run to see why
```

For the guided chapter-1 build, open `notebooks/01_agentic_pipeline.ipynb` and run it
top to bottom; the first cell calls `flyte.init_from_config`, and each run cell links
its run page.

> Note: the agent steps call an LLM, so run them **remotely** (the secret is injected
> on the cluster). Chapter 2's workflow is meant to fail on the first run; that failure
> is the exercise, and the clues live in the run's logs, not the source.
