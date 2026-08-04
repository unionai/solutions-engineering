"""
Exercise 0: Hello Union
========================
Core concepts: TaskEnvironment, @env.task, flyte.map(), flyte.run()

Run locally:   flyte run --local 00_hello_union.py main
Run on Union:  flyte run 00_hello_union.py main
"""

import flyte

# TaskEnvironment = shared config for a group of tasks
env = flyte.TaskEnvironment(
    name="hello_union",
    resources=flyte.Resources(memory="250Mi"),
)


# @env.task turns a Python function into a containerized job
@env.task
def greet(name: str) -> str:
    return f"Hello, {name}!"


# Tasks can call other tasks — each runs in its own container
@env.task
def main(names: list[str] = ["Alice", "Bob", "Charlie", "Diana"]) -> list[str]:
    # flyte.map = parallel execution across inputs
    greetings = list(flyte.map(greet, names))
    return greetings


if __name__ == "__main__":
    flyte.init_from_config()
    run = flyte.run(main)
    print(f"Run URL: {run.url}")
    run.wait()
