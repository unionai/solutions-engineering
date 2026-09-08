# Session 3: Serving & ML training on Union

One model, followed end to end. The **Review Radar** story takes a firehose of raw
product reviews all the way to a live prediction service — and every hand-off between
chapters is a versioned **Artifact**, so the whole lineage (dataset → model →
predictions → app) shows up in the UI.

```
raw reviews ─▶ [1] prep at scale ─▶ review-dataset ─▶ [2] HPO + train ─▶ review-classifier
                                                              │
                                                              ├─▶ [3] batch inference ─▶ review-predictions
                                                              └─▶ [4] serve (API + dashboard)
```

Four chapters. Each is a guided notebook plus the same pipeline as a runnable script.

| Chapter | Notebook | Scripts | Covers |
|---------|----------|---------|--------|
| 1 · Data prep at scale | [`notebooks/01_data_prep.ipynb`](./notebooks/01_data_prep.ipynb) | [`01_data_prep.py`](./workflows/01_data_prep.py) | Micro-batching, `@flyte.trace` checkpoints, reusable workers, producing an **Artifact**, and rescuing a failed run with **recover** & **fork** |
| 2 · Training | [`notebooks/02_training.ipynb`](./notebooks/02_training.ipynb) | [`02_hpo.py`](./workflows/02_hpo.py) · [`02_train.py`](./workflows/02_train.py) | Parallel **HPO** fan-out, picking the winner, training it, and publishing the **model Artifact** (+ how the same shape scales to GPU / distributed) |
| 3 · Batch inference | [`notebooks/03_batch_inference.ipynb`](./notebooks/03_batch_inference.ipynb) | [`03_batch_inference.py`](./workflows/03_batch_inference.py) | Fan-out/map scoring, a shared **`DynamicBatcher`** loaded **once per replica** that aggregates records across concurrent callers, consuming the model Artifact and publishing predictions |
| 4 · Serving | [`notebooks/04_serving.ipynb`](./notebooks/04_serving.ipynb) | [`04_app_api.py`](./workflows/04_app_api.py) · [`04_app_dashboard.py`](./workflows/04_app_dashboard.py) | Flyte **Apps**: a FastAPI endpoint and a Streamlit dashboard that **mount the model Artifact**, `requires_auth`, scale-to-zero, `flyte serve` vs `flyte deploy` |

How the pieces fit:

- **Notebooks** are the guided build — run each top to bottom; the first cell calls
  `flyte.init_from_config`, and each run cell links its run page. Notebook task I/O uses
  built-in types (a class defined in a cell isn't importable on the cluster); the scripts
  use `@dataclass` for the same flow.
- **Scripts** are the same pipelines, runnable from the CLI, and are what you point
  `flyte fork` / `flyte serve` at.

Because every chapter's output is an Artifact, chapters are loosely coupled: Chapter 2
consumes `review-dataset`, Chapters 3–4 consume `review-classifier`. Re-running a chapter
publishes a new **version** of its Artifact.

## Setup

```bash
cd workflows      # or notebooks; each has its own .flyte/config.yaml
uv sync
```

`.flyte/config.yaml` ships pointed at the demo cluster (`demo` org, `leon-demo` project) —
swap `endpoint` / `org` / `project` / `domain` for your own cluster (or run
`flyte create config`) before running remotely. Everything runs on **CPU**; no secrets and
no GPU are required for the core path.

> The classifier is a small TF-IDF + LogisticRegression model that trains in milliseconds,
> so every core cell finishes inside a workshop slot. Each chapter flags where the identical
> shape scales up (GPU fine-tune, multi-node distributed training, GPU batchers) — those are
> shown as reference, not run.

## Running

```bash
# Chapter 1 — data prep (entrypoint `main`); fails at the quality gate on defaults
uv run flyte run 01_data_prep.py main --min_quality 0.7      # happy path → review-dataset
uv run flyte run 01_data_prep.py main                        # fails; then rescue it:
flyte rerun <run-name> --recover --min_quality 0.7           # reuse batches, re-run only the gate
flyte fork  <run-name> 01_data_prep.py main --min_quality 0.7  # same, with your working-tree code

# Chapter 2 — HPO then train the winner
uv run flyte run 02_hpo.py optimize
uv run flyte run 02_train.py train --c 10.0 --ngram 2        # → review-classifier

# Chapter 3 — batch inference (pass the model URI printed by Chapter 2)
uv run flyte run 03_batch_inference.py score --model s3://.../review_classifier.pkl

# Chapter 4 — serve the model
uv run flyte serve 04_app_api.py app_env                     # REST endpoint; curl it
uv run flyte serve 04_app_dashboard.py app_env               # Streamlit dashboard
```

> Recover vs fork: both reuse the succeeded actions of a failed run. `recover` replays the
> **source run's** code; `fork` rebuilds from **your working tree**, so a code fix re-executes
> only the actions it touched. `flyte rerun <run>` (no `--recover`) re-runs everything.

> Apps keep serving until stopped. Deactivate from the console, or
> `flyte.remote.App.get(name="review-radar-api").deactivate()`.
