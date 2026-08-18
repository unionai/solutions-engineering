"""
Part 1, Best Practices: testing, task outputs, integration
===========================================================
Three questions the Manas team raised on Slack, answered with one small,
runnable pipeline (no LLM yet, that's Part 2):

  1. Testing: how do we keep prod tasks free of user errors and let them
                      recover from system errors?
  2. Infrastructure: how do people track / aggregate / use task outputs?
  3. Integration: wrap Flyte in internal tools, or use Flyte directly?

The pipeline scores a batch of records. It is deliberately tiny so the *practices*
stay in focus:

- Testing:      two invocation methods (see test_best_practices.py): call a task
                **directly** to test its body with no cluster (sync task: call it;
                async task: `await` it), and `flyte.run(...)` to test the serialized
                path. For system errors, `retries` + `timeout` + `cache` on the task.
- User errors:  a bad record raises inside its task; `asyncio.gather(..., return_exceptions=True)`
                turns that failure into a value we can skip instead of killing the run.
- Outputs:      a typed pydantic result is durably persisted; read it back with
                `run.outputs()` or query it later with the `flyte.remote` API
                (that's your hook for aggregating into a DB / dashboard).
- Integration:  `flyte.run(...)` from plain Python: Flyte is a library you call,
                so wrapping it in an internal tool is just more Python.

Run locally:  flyte run --local 01_best_practices.py main
Run remote:   flyte run 01_best_practices.py main
Unit tests:   pytest test_best_practices.py           (direct-invocation tests need no cluster)
"""

import asyncio
import random
from datetime import timedelta
from pathlib import Path

import flyte
from pydantic import BaseModel

# Workers run the scoring tasks; the driver coordinates them. The split teaches
# `depends_on` (a driver that calls worker tasks declares it): the same shape
# Part 2's agent pipeline uses. Warm/reusable containers are a Part 2 concern.
worker_env = flyte.TaskEnvironment(
    name="best_practices_worker",
    resources=flyte.Resources(cpu=1, memory="500Mi"),
)

driver_env = flyte.TaskEnvironment(
    name="best_practices_driver",
    resources=flyte.Resources(cpu=1, memory="500Mi"),
    depends_on=[worker_env],
)


# Question 2 (outputs): a typed result. Flyte serializes and durably persists it,
# so downstream tasks (and the `flyte.remote` API later) get structured data,
# not a blob to re-parse.
class Report(BaseModel):
    scored: int
    skipped: int
    total_score: int


# --- Plain business logic (NO Flyte) ---------------------------------------
# Question 1 (testing): keep the real logic in plain functions. They have no
# cluster dependency, so a unit test is a normal `assert`. `score` is what we test.


def score(record: dict) -> int:
    """Score one record. Raises on a malformed record, that's a *user* error."""
    if "value" not in record:
        raise ValueError(f"record {record.get('id', '?')} is missing 'value'")
    return int(record["value"]) * int(record.get("weight", 1))


# --- Tasks ------------------------------------------------------------------


# Question 1 (system errors): cache on inputs, retry transient failures, and cap
# runtime with a timeout. Together these let the task recover from the "rate
# limits and network hiccups" class of failure with no custom code. (Flyte can't
# tell a user error from a system one, so a deterministic ValueError also burns
# its retries before surfacing: validate inputs early when that matters.)
@worker_env.task(cache="auto", retries=2, timeout=timedelta(minutes=2))
async def score_record(record: dict, flaky: bool = False) -> int:
    # Simulate a transient system error to show retries working. On a real task
    # this is the network call that occasionally 503s; Flyte just re-runs it.
    if flaky and random.random() < 0.5:
        raise ConnectionError("transient upstream 503, Flyte will retry this attempt")
    return score(record)


@driver_env.task
async def main(flaky: bool = False) -> Report:
    # One record is missing 'value' on purpose, it exercises the user-error path.
    records = [
        {"id": 1, "value": 10, "weight": 2},
        {"id": 2, "value": 5},
        {"id": 3, "weight": 3},  # <- malformed: no 'value'
        {"id": 4, "value": 7, "weight": 4},
    ]

    # Fan-out: one action per record, grouped on the run page. `return_exceptions=True`
    # hands back the bad record's ValueError as a value, so we skip it and the run
    # still succeeds. (`flyte.map(score_record, records, return_exceptions=True)` is
    # the equivalent mapping idiom when you want a single map node instead of gather.)
    with flyte.group("score-fanout"):
        results = await asyncio.gather(
            *[score_record(r, flaky=flaky) for r in records],
            return_exceptions=True,
        )

    scored, skipped, total = 0, 0, 0
    for record, result in zip(records, results):
        if isinstance(result, Exception):
            print(f"skipping record {record.get('id', '?')}: {result}")
            skipped += 1
        else:
            scored += 1
            total += result

    report = Report(scored=scored, skipped=skipped, total_score=total)
    print(f"scored={report.scored} skipped={report.skipped} total={report.total_score}")
    return report


# Question 1 (testing): the unit tests live in test_best_practices.py and use the
# two official invocation methods: direct invocation for task/business logic
# (no cluster) and flyte.run(...) for the serialized path. Run: pytest test_best_practices.py


if __name__ == "__main__":
    flyte.init_from_config(
        root_dir=Path(__file__).parent,
        path_or_config=Path(__file__).parent / ".flyte" / "config.yaml",
    )

    # Question 3 (integration): this is the whole "wrap vs direct" answer, Flyte
    # is a library. `flyte.run` submits from plain Python and hands back a run
    # object, so an internal tool wraps Flyte by... importing it and calling this.
    run = flyte.run(main)
    print(f"Run URL: {run.url}")
    run.wait()

    # Question 2 (outputs): pull the typed result straight back out of the run.
    # The same values are queryable later via flyte.remote (see the notebook),
    # that's the hook for aggregating outputs into a database or dashboard.
    print(f"Outputs: {run.outputs()}")
