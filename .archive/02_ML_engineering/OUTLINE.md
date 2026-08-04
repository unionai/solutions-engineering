# Session 2 — Machine Learning Engineering on Union

**Format:** live session (~90 min), recorded; recording + slides + this repo handed over for
self-paced use.  
**Audience:** users doing data processing and model training — classic ML and LLM fine-tuning.
Assumes session 1 (core concepts).

This stream bundles **data transformation, model training, and hosting models as apps** (apps are
covered in both this and the agentic stream).

## Agenda

| # | Section | Contents |
|---|---------|----------|
| 1 | Data transformation pipelines | `flyte.io.File`/`Dir`/`DataFrame`, download-before-use pattern, SQL/pandas ETL |
| 2 | Training pipeline | end-to-end ML pipeline: caching, artifacts, `flyte.report`, image building |
| 3 | GPU training | requesting GPUs, ML images (torch/transformers), fine-tuning example |
| 4 | Scaling experiments | parallel hyperparameter tuning (Optuna + `asyncio.gather`), fan-out over configs |
| 5 | Robustness | retries, `OOMError` self-healing with `.override()` |
| 6 | Production | cron triggers, `flyte.deploy()`, connectors |
| 7 | Hosting models as apps | `AppEnvironment` / `FastAPIAppEnvironment`, `flyte.serve()`, Streamlit dashboards |
| 8 | Q&A | |

## Code examples (in `examples/`)

| Example | Source | Covers |
|---------|--------|--------|
| `duckdb-etl/` | workshops/tutorials/starter-examples | CSV extract/transform with DuckDB + pandas, reports |
| `02_ml_pipeline.py` | solutions-engineering/onboarding_workshop | caching, `flyte.io.File`, `flyte.report`, image building, OOM retry |
| `03_hyperparameter_tuning.py` | solutions-engineering/onboarding_workshop | parallel HPO with Optuna, env-level caching |
| `image-classifier/` | workshops/tutorials/starter-examples | fine-tune ResNet18 on a HuggingFace dataset (GPU, multi-task pipeline) |
| `bert-fine-tuning-emotion/` | workshops/tutorials | BERT fine-tuning pipeline + Gradio serving (GPU) — the repo the "BERT Fine-tune" deck walks through |
| `llm-fine-tuning-lora-qlora/` | workshops/tutorials | LoRA/QLoRA fine-tuning pipeline + serving — the repo the "LLM LoRa & QLoRA" and "GRPO" decks walk through |
| `oom-self-healing/` | workshops/tutorials/starter-examples | catch `OOMError`, retry with more memory via `.override()` |
| `04_production.py` | solutions-engineering/onboarding_workshop | cron triggers, BigQuery connector, `flyte.deploy()` |
| `fastapi_app/` | solutions-engineering/hands_on/04 | simplest FastAPI app on Union — intro to apps |
| `vllm_serving/` | solutions-engineering/hands_on/05 | hosting an LLM as an app with vLLM |
| `wikipedia_embedding/` | solutions-engineering/hands_on/05 | full embedding pipeline (batch + serving) |
| `05_streamlit_dashboard.py` | solutions-engineering/onboarding_workshop | Streamlit app hosting via `flyte.serve()` |

## Slides

- [**BERT Fine-tune**](https://docs.google.com/presentation/d/16XJQGG-KGVpqFte6SFTD0VbxgifhRZbEMziic4E4j3s/edit?slide=id.g3e967f01592_0_0#slide=id.g3e967f01592_0_0) — why fine-tune, what BERT is, HF Transformers, → `bert-fine-tuning-emotion` repo
- [**LLM LoRa & QLoRA**](https://docs.google.com/presentation/d/1uNy2x9797xfE2hN7mTmGqqLMhmXpDztdclj9CNgsVfU/edit?slide=id.g3e967f01592_0_0#slide=id.g3e967f01592_0_0) — why fine-tune, LoRA vs QLoRA, PEFT, bitsandbytes, → `llm-fine-tuning-lora-qlora` repo
- [**DETR Workshop**](https://docs.google.com/presentation/d/1W3GaA5q_4E1FfONI78qwT_Ys13DR9kGwk538mBKXy5w/edit?usp=sharing) — object detection, data annotation, DETR, MLOps/why-workflows slides, → `detr-object-detection` repo
- [**Fraud Detection**](https://docs.google.com/presentation/d/17LO6_SkBYOwifsn_Z4x0HJcpg6wYmtHCwVHHBKQdifA/edit?usp=sharing) — feature-store challenges, Feast, XGBoost, → `fraud-detection-feast` repo

