"""
Production Pipeline — the Core Pipeline hardened with Best Practices
=====================================================================
Structurally identical to 02_core_pipeline.py — same environments, same
tasks, same flow — so you can diff the two files and see exactly what
production hardening adds:

- Reusable containers:      workers share warm containers (skip pod startup)
- Caching, retries & timeouts:  on the worker tasks
- Overrides (.override()):  one heavy chunk gets its own right-sized pod
- Traces (@flyte.trace):    durable helper call, visible on the run page
- Reports (report=True):    the driver publishes an HTML report

Run it twice — on the second run every process_chunk call is a cache hit.

Run on Union:  flyte run 03_production_pipeline.py main
"""

import asyncio
import os
from datetime import timedelta
from pathlib import Path

import emoji  # installed locally AND declared in the image below
import flyte
import flyte.report
from flyte.io import File
from pydantic import BaseModel

# Container images: declare the image once — with its pip dependencies — and
# share it across environments. Reuse requires the unionai-reuse package.
image = flyte.Image.from_debian_base().with_pip_packages(
    "emoji", "unionai-reuse>=0.1.9"
)

# Resources: workers get more resources than the driver that coordinates them.
# Reusable containers: ReusePolicy keeps replicas warm, so successive tasks
# skip pod startup.
worker_env = flyte.TaskEnvironment(
    name="prod_pipeline_worker",
    image=image,
    resources=flyte.Resources(cpu=2, memory="1Gi"),
    reusable=flyte.ReusePolicy(
        replicas=(1, 2),
        idle_ttl=60,
        concurrency=10,
        scaledown_ttl=60,
    ),
)

# Multi-environment: the driver calls worker tasks, so it declares depends_on.
# Secrets: injected as env vars (create with: flyte create secret ANTHROPIC_API_KEY).
driver_env = flyte.TaskEnvironment(
    name="prod_pipeline_driver",
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


# --- Plain business logic (no Flyte) — identical to 02_core_pipeline.py -----


def build_chunk_lines(chunk_id: int, lines: int) -> list[str]:
    sparkle = emoji.emojize(":sparkles:", language="alias")
    return [
        f"chunk {chunk_id}, line {i}: hello from flyte {sparkle}" for i in range(lines)
    ]


def count_words(text: str) -> int:
    return len(text.split())


# --- Tasks ------------------------------------------------------------------


# Caching, retries & timeouts: cached on inputs, retried on failure, and
# killed if it hangs past 5 minutes.
@worker_env.task(cache="auto", retries=2, timeout=timedelta(minutes=5))
async def process_chunk(chunk_id: int, lines: int = 10) -> list[str]:
    """Data I/O: plain typed values (list[str]) pass between tasks automatically."""
    result = [line.upper() for line in build_chunk_lines(chunk_id, lines)]
    print(f"chunk {chunk_id}: {len(result)} lines (only on cache miss)")
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
    tolerate_failures = False
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


# Caching: the merge step is cached and retried too.
@worker_env.task(cache="auto", retries=2)
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


# Traces: @flyte.trace (no parentheses) — a durable, observable call that runs
# inside the driver's container instead of its own pod.
@flyte.trace
async def annotate(summary: Summary) -> str:
    return f"{summary.chunks} chunks, {summary.lines} lines, {summary.words} words"


@driver_env.task(report=True)
async def main(num_chunks: int = 4, heavy_lines: int = 1000) -> Summary:
    # Secrets: the secret arrives as a plain environment variable.
    print(f"Secret injected: {'ANTHROPIC_API_KEY' in os.environ}")

    # Fan-out: fan out over chunks — grouped on the run page, executed in parallel.
    with flyte.group("chunk-fanout"):
        coros = [process_chunk(i) for i in range(num_chunks)]
        # Overrides: the last chunk is known to be big — give that one call more
        # memory with .override() instead of oversizing the whole environment.
        # Reusable containers have fixed resources, so this call opts out of
        # reuse (reusable="off") to get its own right-sized pod.
        heavy = process_chunk.override(
            reusable="off", resources=flyte.Resources(cpu=2, memory="2Gi")
        )
        coros.append(heavy(num_chunks, lines=heavy_lines))
        chunks = await asyncio.gather(*coros)

    # Mapping: the same chunks again, this time fanned out with flyte.map.
    word_counts = tally_words(chunks)
    print(f"words per chunk: {word_counts}")

    # Tasks calling tasks: just another task call — its own action on the run page.
    summary, report_file = await summarize_and_archive(chunks)

    # Files: download the archived File before reading it like a local file.
    local_path = await report_file.download()
    first_line = Path(local_path).read_text().splitlines()[0]
    print(f"Archived {summary.lines} lines; first line: {first_line}")

    # Reports: publish an HTML report on the run page.
    note = await annotate(summary)
    await flyte.report.replace.aio(
        "<h2>Production Pipeline Report</h2>"
        f"<p>{note}</p>"
        f"<p>Archive: {report_file.path}</p>"
    )
    await flyte.report.flush.aio()

    return summary


if __name__ == "__main__":
    flyte.init_from_config(
        root_dir=Path(__file__).parent,
        path_or_config=Path(__file__).parent / ".flyte" / "config.yaml",
    )
    run = flyte.run(main)
    print(f"Run URL: {run.url}")
    run.wait()
