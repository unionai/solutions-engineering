"""
Unit tests for 01_best_practices.py, the Flyte 2.0 way.
=======================================================
Flyte gives you two ways to invoke an `@env.task` in a test
(https://www.union.ai/docs/v2/union/user-guide/tasks/task-programming/unit-testing/):

- **Direct invocation**: call the task like a normal function (sync) or `await`
  it (async). This *bypasses* Flyte machinery (no serialization, caching, or type
  checks), so it's the fast way to test business logic. No cluster needed.
- **`flyte.run(...)`**: engages the full machinery: serialization, type
  transformations, caching, and `flyte.errors` for unsupported types. Use it to
  verify the *serialized* path. It submits a run, so it's marked below and skipped
  unless a cluster is configured.

Run:  pytest test_best_practices.py          (the direct-invocation tests need no cluster)
"""

import importlib.util
from pathlib import Path

import pytest

# The module name starts with a digit, so load it by path.
_spec = importlib.util.spec_from_file_location(
    "best_practices", Path(__file__).parent / "01_best_practices.py"
)
bp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bp)


# --- Business logic: plain function, called directly ------------------------


def test_score_logic():
    assert bp.score({"id": 1, "value": 10, "weight": 2}) == 20
    assert bp.score({"id": 2, "value": 5}) == 5  # weight defaults to 1


def test_score_rejects_malformed():
    with pytest.raises(ValueError):
        bp.score({"id": 3, "weight": 3})


# --- Task bodies: direct invocation (no cluster) ----------------------------
# A sync task is called directly; an async task is awaited. Either way the body
# runs in-process, bypassing serialization/caching/retries.


@pytest.mark.asyncio
async def test_score_record_task():
    # `score_record` is an async @worker_env.task, await it to run the body.
    assert await bp.score_record({"id": 1, "value": 10, "weight": 2}) == 20


@pytest.mark.asyncio
async def test_score_record_propagates_user_error():
    with pytest.raises(ValueError):
        await bp.score_record({"id": 3, "weight": 3})  # missing 'value'


# --- Serialized path: flyte.run() (needs a cluster) -------------------------
# Verifies the *serialized* round-trip and typed output. Skipped by default
# because it submits a run; drop the skip once a cluster is configured.


@pytest.mark.skip(reason="submits a real run, enable when a cluster is configured")
@pytest.mark.asyncio
async def test_main_serialized_path():
    import flyte

    flyte.init_from_config(
        root_dir=Path(__file__).parent,
        path_or_config=Path(__file__).parent / ".flyte" / "config.yaml",
    )
    run = flyte.run(bp.main)
    run.wait()
    report = run.outputs()
    assert report.scored == 3 and report.skipped == 1  # one malformed record skipped
