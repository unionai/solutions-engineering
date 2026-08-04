# Session 1 — Introduction to Union: Concepts & Best Practices

**Format:** live session (~90 min), recorded; recording + slides + this repo handed over for
self-paced onboarding of future users.  
**Audience:** all users — researchers/engineers new to Union, often coming from batch schedulers
(e.g. SLURM), notebooks, or code running locally / on VMs.

## Goals

- Everyone leaves able to run their first workflow on the customer's Union cluster.
- Build the shared vocabulary (tasks, environments, workflows, runs, projects) the two follow-up
  sessions assume.
- Answer the batch-scheduler-user question up front: "where is my job, why is it queued, what is
  my quota?"

## Agenda

| # | Section | Contents |
|---|---------|----------|
| 1 | What is Union / Flyte 2.0 | Platform overview: tasks, environments, workflows, runs, projects |
| 2 | Getting access & setup | UI tour, CLI install, config, login flow, projects & domains |
| 3 | First task & first run | `TaskEnvironment`, `@env.task`, `flyte.run()`, `flyte run --local`, reading the run page |
| 4 | Workflows = tasks calling tasks | async tasks, fan-out with `flyte.map()` / `asyncio.gather` / `flyte.group` |
| 5 | Environments, images, resources | `flyte.Resources`, `Image.from_debian_base().with_pip_packages(...)`, declaring dependencies, pulling images from a customer registry |
| 6 | Best practices | Caching, traces, retries, reusable environments, queues |
| 7 | Getting help | Docs, Slack channel, MCP |
| 8 | Q&A + preview of sessions 2 & 3 | |

## Code examples (in `examples/`)

| Example | Source | Covers |
|---------|--------|--------|
| `00_hello_union.py` | solutions-engineering/onboarding_workshop | `TaskEnvironment`, `@env.task`, `flyte.map()`, `flyte.run()` |
| `01_parallel_processing.py` | solutions-engineering/onboarding_workshop | fan-out, resource allocation, error handling |
| `union_quickstart/` | solutions-engineering/hands_on/01 | minimal project layout with `pyproject.toml` + config |
| `fanout_fanin/` | solutions-engineering/hands_on/02 | fan-out / fan-in pattern |
| `trigger/` | solutions-engineering/hands_on/03 | scheduled/triggered runs (teaser for session 2 production part) |
| `flyte-basics/` | workshops/tutorials/starter-examples | Flyte 2 fundamentals incl. `ReusePolicy` |
| `flyte-local-dev/` | workshops/tutorials/starter-examples | local dev: cache, report, `@flyte.trace`, TUI, local serving |

## Slides

AI agent slidedecks ([Reserach AI Agents](https://docs.google.com/presentation/d/1nrqtsgEcIXB58GbnLf2SMijsSYRFwGaMXwuyfcDm8WM/edit?usp=sharing), [Planner AI Agents](https://docs.google.com/presentation/d/1pj6PvRHEL-N32_uEK4SJ93jB0HJv3GT6-jdWYYYwaOg/edit?usp=sharing)) introducing:
- async fan-out
- try/catch
- image builder
- tasks
- environments (compute-aware, image spec, secrets,
reuse)
- traces 
- out-of-the-box retries
- error handling / dynamic recovery
