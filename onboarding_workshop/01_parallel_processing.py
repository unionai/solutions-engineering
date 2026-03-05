"""
Exercise 1: Parallel Processing
=================================
Pattern for entity resolution / batch ETL:
split work into chunks → process in parallel → aggregate.

Concepts: flyte.map(), resource allocation, error handling

Run locally:   flyte run --local 01_parallel_processing.py pipeline
Run on Union:  flyte run 01_parallel_processing.py pipeline
"""

import flyte

env = flyte.TaskEnvironment(
    name="parallel",
    resources=flyte.Resources(cpu="2", memory="2Gi"),
)


@env.task
def process_chunk(chunk_id: int) -> dict:
    """Each chunk runs in its own pod with 2 CPU / 2Gi RAM."""
    import random
    records = random.randint(1000, 5000)
    matches = random.randint(10, 100)
    print(f"Chunk {chunk_id}: {records} records, {matches} matches")
    return {"chunk_id": chunk_id, "records": records, "matches": matches}


@env.task
def aggregate(results: list[dict]) -> dict:
    return {
        "chunks": len(results),
        "total_records": sum(r["records"] for r in results),
        "total_matches": sum(r["matches"] for r in results),
    }


@env.task
def pipeline(num_chunks: int = 10) -> dict:
    """Fan-out → process → aggregate. All chunks run in parallel."""
    results = list(flyte.map(process_chunk, range(num_chunks)))
    return aggregate(results)


# --- Error handling with map ---
@env.task
def risky_task(x: int) -> int:
    if x == 7:
        raise ValueError(f"Bad input: {x}")
    return x * x


@env.task
def safe_pipeline(n: int = 10) -> list[int]:
    """return_exceptions=True: failed tasks return the exception instead of crashing."""
    results = []
    for result in flyte.map(risky_task, range(n), return_exceptions=True):
        if isinstance(result, Exception):
            print(f"Skipping failed task: {result}")
            results.append(-1)
        else:
            results.append(result)
    return results


if __name__ == "__main__":
    flyte.init_from_config()
    run = flyte.run(pipeline, num_chunks=10)
    print(f"Run URL: {run.url}")
    run.wait()
