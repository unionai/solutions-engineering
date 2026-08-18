# Session 1: Intro to Flyte

The general onboarding to Flyte 2.0: concepts and best practices. Three chapters
that build on each other, each shipped **both** as a runnable notebook (in
[`notebooks/`](./notebooks)) and as the same code in a standalone script (in
[`workflows/`](./workflows)). The slides for the live session are
[`session1-v1.html`](./session1-v1.html).

| Chapter | Notebook | Script | Covers |
|---------|----------|--------|--------|
| 1 · Hello Flyte | [`notebooks/01_hello_flyte.ipynb`](./notebooks/01_hello_flyte.ipynb) | [`workflows/01_hello_flyte.py`](./workflows/01_hello_flyte.py) | `TaskEnvironment`, `@env.task` (sync + async), a workflow is just a task calling tasks, `flyte.run`, local vs remote, and reading runs & actions |
| 2 · Core pipeline | [`notebooks/02_core_pipeline.ipynb`](./notebooks/02_core_pipeline.ipynb) | [`workflows/02_core_pipeline.py`](./workflows/02_core_pipeline.py) | A text-processing pipeline: fan-out (`asyncio.gather` + `flyte.group`, `flyte.map` with `return_exceptions`), typed I/O with a pydantic result and `File`, and multiple environments (images, resources, `depends_on`, a secret) |
| 3 · Production pipeline | [`notebooks/03_production_pipeline.ipynb`](./notebooks/03_production_pipeline.ipynb) | [`workflows/03_production_pipeline.py`](./workflows/03_production_pipeline.py) | The same pipeline hardened: reusable containers, caching + retries + timeouts, `.override()` for one heavy task, `@flyte.trace`, and an HTML report |

Chapters 2 and 3 are **structurally identical on purpose**: diff `02_core_pipeline`
against `03_production_pipeline` to see exactly what production hardening adds.
Every script's entrypoint is `main`.

## Setup

```bash
cd workflows      # or notebooks; each has its own .flyte/config.yaml
uv sync
```

`.flyte/config.yaml` ships as a blank template. Fill in your cluster's
`endpoint` / `org` / `project` / `domain` (or run `flyte create config`) before
running remotely. Chapters 2 and 3 expect an `ANTHROPIC_API_KEY` secret in the
project; they only check that it is injected as an env var, so no API call is made:

```bash
flyte create secret ANTHROPIC_API_KEY
```

## Running

Each script has a `__main__` block, so run it directly or via the CLI:

```bash
uv run flyte run --local 01_hello_flyte.py main      # fast local dev loop, no cluster
uv run flyte run 01_hello_flyte.py main              # remote
uv run flyte run 02_core_pipeline.py main
uv run flyte run 03_production_pipeline.py main      # run twice: the 2nd run is a cache hit
```

The notebooks cover the same code chapter by chapter. Open them in Jupyter and run
top to bottom; the first cell calls `flyte.init_from_config` against the same
`.flyte/config.yaml`, then each later cell submits a run and links its run page.

> Tip: start every chapter with `flyte run --local` for an instant inner loop, then
> drop `--local` to run the identical code on the cluster and walk the run page
> (graph, logs, inputs/outputs, per-task actions).
