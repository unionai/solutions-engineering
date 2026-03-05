# Workshop: Traditional ML on Union

**Duration:** 1 hour
**Prerequisites:** Python 3.10+, `uv` package manager

## Agenda

| Time | Section | Description |
|------|---------|-------------|
| 0:00 | **Setup & Orientation** | Environment setup, connect to cluster, first run |
| 0:10 | **Part 1: Fundamentals** | Tasks, environments, parallel execution |
| 0:25 | **Part 2: ML Pipeline** | Caching, artifacts, reports, HPO |
| 0:40 | **Part 3: Production** | Scheduling, Streamlit dashboards, BigQuery |
| 0:55 | **Q&A & Next Steps** | Discussion, workshop 2 preview (agentic AI) |

## Setup

```bash
uv venv && source .venv/bin/activate
uv pip install -r requirements.txt
flyte create config
```

## Workshop Files

| File | Concepts |
|------|----------|
| `00_hello_union.py` | TaskEnvironment, @env.task, flyte.map(), flyte.run() |
| `01_parallel_processing.py` | Fan-out with flyte.map(), resource allocation, error handling |
| `02_ml_pipeline.py` | Caching, flyte.io.File, flyte.report, image building, OOM retry |
| `03_hyperparameter_tuning.py` | Parallel HPO with Optuna, asyncio.gather, env-level caching |
| `04_production.py` | Cron triggers, BigQuery connector, flyte.deploy() |
| `05_streamlit_dashboard.py` | AppEnvironment, Streamlit hosting, flyte.serve() |
| `workshop.ipynb` | Interactive notebook with all exercises |

## Next Workshop

Workshop 2: **Agentic AI on Union** — LangGraph, real-time inference, app serving, batch LLM workflows.
