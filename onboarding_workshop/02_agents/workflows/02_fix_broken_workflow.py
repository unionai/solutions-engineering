"""
Part 2: Agentic development on Union, fix a broken workflow with your CLI agent

Prompt for an agent with flyte-plugins and flyte mcp servers installed:

    Use the `flyte-sdk-author` skill to read and edit this Flyte 2.0
    workflow correctly.
    Use the `flyte-docs` MCP server to look up the right Flyte 2.0 API or
    pattern whenever an error points at one.
    Use the `flyte-cluster` (Flyte server) MCP server to RUN this file and
    then INSPECT the failed run (its actions, logs, and errorInfo) to
    find each root cause.

    Work in a loop on 02_fix_broken_workflow until it succeeds.
    Write to a new file instead of editing in this one.
"""

import asyncio
from pathlib import Path

import flyte

image = flyte.Image.from_debian_base()

worker_env = flyte.TaskEnvironment(
    name="enrich_worker",
    image=image,
    resources=flyte.Resources(cpu=1, memory="500Mi"),
)

driver_env = flyte.TaskEnvironment(
    name="enrich_driver",
    image=image,
    resources=flyte.Resources(cpu=1, memory="500Mi"),
)


@worker_env.task
async def enrich(x: float) -> float:
    import numpy as np

    return float(np.log1p(x) * 100.0)


@driver_env.task
async def main(values: list[float] = [1.0, 2.0, 3.0, 10.0]) -> list[float]:
    with flyte.group("enrich-fanout"):
        scores = await asyncio.gather(*[enrich(v) for v in values])
    print(f"enriched {len(scores)} values")
    return list(scores)


if __name__ == "__main__":
    flyte.init_from_config(
        root_dir=Path(__file__).parent,
        path_or_config=Path(__file__).parent / ".flyte" / "config.yaml",
    )
    run = flyte.run(main)
    print(f"Run URL: {run.url}")
    run.wait()
    print(run.outputs())
