"""
Core Pipeline — Sections 3-5 in one workflow
=============================================
- Setup & Access:      walkthrough of general project setup and config
- Tasks & Runs:        a workflow is a task (`main`) calling other tasks -> 01_hello_flyte.py

In this file: A small text-processing pipeline with fan out over chunks of lines, merge them,
summarize, archive:
- Fan-out & Parallelism: asyncio.gather inside flyte.group (main); flyte.map with
                       return_exceptions=True in a separate task (tally_words)
- Data & I/O:          typed values between tasks, a pydantic BaseModel result,
                       File.from_local() + download()
- Environments, Images & Resources: shared image with a pip dependency,
                       per-env resources, depends_on, a secret

03_production_pipeline.py is this exact pipeline with production task
configuration (the Best Practices section) layered on top — diff the two files to see it.

Run on Union:  flyte run 02_core_pipeline.py main
"""

import asyncio
import os
from pathlib import Path

import emoji  # installed locally AND declared in the image below
import flyte
from flyte.io import File
from pydantic import BaseModel

# Container images: declare the image once — with its pip dependencies — and share it
# across environments.
image = flyte.Image.from_debian_base().with_pip_packages("emoji")

# Resources: workers get more resources than the driver that coordinates them.
worker_env = flyte.TaskEnvironment(
    name="pipeline_worker",
    image=image,
    resources=flyte.Resources(cpu=2, memory="1Gi"),
)

# Multi-environment: the driver calls worker tasks, so it declares depends_on.
# Secrets: injected as env vars (create with: flyte create secret ANTHROPIC_API_KEY).
driver_env = flyte.TaskEnvironment(
    name="pipeline_driver",
    image=image,
    resources=flyte.Resources(cpu=1, memory="500Mi"),
    depends_on=[worker_env],
    secrets=[flyte.Secret(key="ANTHROPIC_API_KEY", as_env_var="ANTHROPIC_API_KEY")],
)


# Data I/O: a pydantic BaseModel gives the pipeline a typed, structured result.
class Summary(BaseModel):
    chunks: int
    lines: int
    words: int


# --- Plain business logic (no Flyte) — identical in 03_production_pipeline.py


def build_chunk_lines(chunk_id: int, lines: int) -> list[str]:
    sparkle = emoji.emojize(":sparkles:", language="alias")
    return [
        f"chunk {chunk_id}, line {i}: hello from flyte {sparkle}" for i in range(lines)
    ]


def count_words(text: str) -> int:
    return len(text.split())


# --- Tasks ------------------------------------------------------------------


@worker_env.task
async def process_chunk(chunk_id: int, lines: int = 10) -> list[str]:
    """Data I/O: plain typed values (list[str]) pass between tasks automatically."""
    result = [line.upper() for line in build_chunk_lines(chunk_id, lines)]
    print(f"chunk {chunk_id}: {len(result)} lines")
    return result


@worker_env.task
async def count_chunk_words(chunk: list[str]) -> int:
    if not chunk:
        raise ValueError("empty chunk")
    return count_words(" ".join(chunk))


@driver_env.task
def tally_words(chunks: list[list[str]]) -> list[int]:
    """Mapping over inputs: flyte.map — one parallel action per input item.

    An empty chunk is appended on purpose: it raises a ValueError inside
    count_chunk_words. With tolerate_failures=True the error comes back as a
    value we can skip instead of failing the whole run.
    """
    # tolerate_failures = False
    tolerate_failures = True  # <- comment out to fail the run and show the ValueError

    counts = []
    for result in flyte.map(
        count_chunk_words, [*chunks, []], return_exceptions=tolerate_failures
    ):
        if isinstance(result, Exception):
            print(f"skipping failed chunk: {result}")
        else:
            counts.append(result)
    return counts


@worker_env.task
async def summarize_and_archive(chunks: list[list[str]]) -> tuple[Summary, File]:
    """Files: merge the chunks, summarize, and archive the text as a File."""
    text = "\n".join(line for chunk in chunks for line in chunk)

    local_path = "/tmp/report.txt"
    Path(local_path).write_text(text)

    summary = Summary(
        chunks=len(chunks),
        lines=text.count("\n") + 1,
        words=count_words(text),
    )
    return summary, await File.from_local(local_path)


@driver_env.task
async def main(num_chunks: int = 4) -> Summary:
    # Secrets: the secret arrives as a plain environment variable.
    print(f"Secret injected: {'ANTHROPIC_API_KEY' in os.environ}")

    # Fan-out: fan out over chunks — grouped on the run page, executed in parallel.
    with flyte.group("chunk-fanout"):
        chunks = await asyncio.gather(*[process_chunk(i) for i in range(num_chunks)])

    # Mapping: count the chunks, this time fanned out with flyte.map.
    word_counts = tally_words(chunks)
    print(f"words per chunk: {word_counts}")

    # Tasks calling tasks: just another task call — its own action on the run page.
    summary, report_file = await summarize_and_archive(chunks)

    # Files: download the archived File before reading it like a local file.
    local_path = await report_file.download()
    first_line = Path(local_path).read_text().splitlines()[0]
    print(f"Archived {summary.lines} lines; first line: {first_line}")

    return summary


if __name__ == "__main__":
    flyte.init_from_config(
        root_dir=Path(__file__).parent,
        path_or_config=Path(__file__).parent / ".flyte" / "config.yaml",
    )
    run = flyte.run(main)
    print(f"Run URL: {run.url}")
    run.wait()
