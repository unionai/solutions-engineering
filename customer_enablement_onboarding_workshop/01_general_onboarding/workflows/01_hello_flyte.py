"""
Framing: What is Flyte & Why - Sections 0 - 2
==========================================
TaskEnvironment -> @env.task -> flyte.run(). Tasks can be sync or async, and
tasks can call other tasks — each call becomes its own action on the run page.

- TaskEnvironment: shared config (image, resources) for a group of tasks
- @env.task:       turns a Python function into a containerized job
- workflow:        a task that calls other tasks
- run/action:      one execution of a workflow, and each task call inside it

The dev loop:
1. flyte run --local 01_hello_flyte.py main   # fast, runs in-process
2. flyte run 01_hello_flyte.py main           # remote, containerized
3. Open the run URL and read the run page: one run, one action per task call.

Docs: https://www.union.ai/docs/v2/union/user-guide/core-concepts/tasks/
      https://www.union.ai/docs/v2/union/user-guide/core-concepts/task-environment/
      https://www.union.ai/docs/v2/union/user-guide/run-modes/running-locally/
      https://www.union.ai/docs/v2/union/user-guide/core-concepts/runs-and-actions/
"""

from pathlib import Path

import flyte

env = flyte.TaskEnvironment(
    name="first_task",
    resources=flyte.Resources(cpu=1, memory="250Mi"),
)


# Sync task — a plain Python function.
@env.task
def join_names(first_name: str, last_name: str, config: dict) -> str:
    return f"{first_name} {last_name}"


# Async task — same decorator, async def. Use this when you want to await
# other tasks or run I/O concurrently (chapter 3).
@env.task
async def get_name_length(name: str) -> int:
    return len(name)


@env.task
async def main(first_name: str = "Ada", last_name: str = "Lovelace") -> str:
    print("Starting first workflow...")

    full_name = join_names(first_name, last_name, {"01": "value"})  # sync task call
    name_length = await get_name_length(full_name)  # async task call

    result = f"'{full_name}' has {name_length} characters"
    print(result)
    return result


if __name__ == "__main__":
    flyte.init_from_config(
        root_dir=Path(__file__).parent,
        path_or_config=Path(__file__).parent / ".flyte" / "config.yaml",
    )
    run = flyte.run(main)
    print(f"Run URL: {run.url}")
    run.wait()
