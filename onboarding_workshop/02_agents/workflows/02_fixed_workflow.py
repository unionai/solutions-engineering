"""
Part 3: Agentic development on Union — fixed version of the broken workflow.

Fixes applied vs 03_fix_broken_workflow.py:
  1. worker image now declares the `numpy` pip package (enrich() imports numpy).
  2. driver_env declares depends_on=[worker_env] because main() calls enrich().
"""

import asyncio
from pathlib import Path

import flyte

worker_image = flyte.Image.from_debian_base().with_pip_packages("numpy")
driver_image = flyte.Image.from_debian_base()

worker_env = flyte.TaskEnvironment(
    name="enrich_worker",
    image=worker_image,
    resources=flyte.Resources(cpu=1, memory="500Mi"),
)

driver_env = flyte.TaskEnvironment(
    name="enrich_driver",
    image=driver_image,
    resources=flyte.Resources(cpu=1, memory="500Mi"),
    depends_on=[worker_env],
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
