"""
Chapter 1 — Data prep at scale: micro-batching, Artifacts, and recover/fork
===========================================================================
The story: turn a firehose of raw product reviews into a clean, labeled
training set — the input every later chapter consumes.

What this chapter shows:

- Micro-batching:   the reviews are split into batches and labeled by a pool of
                    reusable workers (`process_batch`), each batch its own action.
- @flyte.trace:     the submit/poll calls to the (stub) labeling service are
                    durable checkpoints, so a retried batch resumes mid-flight
                    instead of re-submitting.
- Artifacts:        the validated dataset is published as a named, versioned
                    Artifact (`review-dataset`) — that's the hand-off to Ch. 2.
- recover / fork:   `main` ends with a `validate_dataset` quality gate. On the
                    first run the default threshold is deliberately too strict,
                    so the run fails *after* all the expensive labeling work
                    succeeded. You then rescue it without redoing that work:

    # reuse the succeeded batch actions, re-run only the gate, same code:
    flyte rerun <run-name> --recover --min-quality 0.7

    # same idea but with YOUR current working-tree code (see fork() at bottom):
    #   from flyteplugins.union import fork
    #   fork("<run-name>", task_template=main, min_quality=0.7)

Run on Union:  uv run flyte run 01_data_prep.py main
               uv run flyte run 01_data_prep.py main --n-reviews 200 --min-quality 0.7
"""

import asyncio
from dataclasses import asdict, dataclass

import flyte
import pandas as pd
from flyte.io import File

image = flyte.Image.from_debian_base().with_pip_packages(
    "pandas", "pyarrow", "unionai-reuse>=0.1.9"
)

# Reusable worker pool: batches skip pod startup and share warm replicas.
worker_env = flyte.TaskEnvironment(
    name="prep_worker",
    image=image,
    resources=flyte.Resources(cpu=1, memory="512Mi"),
    reusable=flyte.ReusePolicy(replicas=(1, 2), concurrency=8, idle_ttl=60),
)

# Driver orchestrates the workers, so it declares depends_on.
driver_env = flyte.TaskEnvironment(
    name="prep_driver",
    image=image,
    resources=flyte.Resources(cpu=1, memory="512Mi"),
    depends_on=[worker_env],
)


@dataclass
class Review:
    text: str
    sentiment: str  # ground-truth label (synthetic data has it; real data won't)


@dataclass
class LabeledReview:
    text: str
    sentiment: str
    predicted: str
    confidence: float


# --- synthetic corpus (deterministic, so recover/fork behave predictably) -----
_POS = ["love it", "works great", "excellent quality", "highly recommend", "fast and reliable"]
_NEG = ["broke immediately", "terrible support", "waste of money", "very disappointed", "stopped working"]
_AMBIG = ["it is okay", "does the job", "not sure yet", "average at best", "mixed feelings"]


def _synth_reviews(n: int) -> list[Review]:
    """A reproducible mix of clearly-positive, clearly-negative, and ambiguous
    reviews. The ambiguous ones are what keep dataset quality below a perfect
    1.0 — which is the whole point of the quality gate later."""
    out: list[Review] = []
    for i in range(n):
        bucket = i % 5
        if bucket in (0, 1):
            out.append(Review(text=_POS[i % len(_POS)], sentiment="positive"))
        elif bucket in (2, 3):
            out.append(Review(text=_NEG[i % len(_NEG)], sentiment="negative"))
        else:
            # ground truth alternates but text is genuinely ambiguous
            out.append(Review(text=_AMBIG[i % len(_AMBIG)], sentiment="positive" if i % 2 else "negative"))
    return out


# --- the "external labeling service", stubbed but with real submit/poll shape --
@flyte.trace
async def submit_labeling(texts: list[str]) -> str:
    """Submit a batch to the labeling service and get a job handle back.
    Traced → this is a durable checkpoint; a retry won't re-submit."""
    await asyncio.sleep(0)  # stands in for a network round-trip
    return f"job-{abs(hash(tuple(texts))) % 10_000}"


@flyte.trace
async def poll_labeling(job_id: str, texts: list[str]) -> list[tuple[str, float]]:
    """Poll the job to completion. Traced → resumes from here on retry."""
    results: list[tuple[str, float]] = []
    for t in texts:
        low = t.lower()
        if any(k in low for k in ("love", "great", "excellent", "recommend", "reliable")):
            results.append(("positive", 0.95))
        elif any(k in low for k in ("broke", "terrible", "waste", "disappointed", "stopped")):
            results.append(("negative", 0.95))
        else:
            results.append(("positive", 0.5))  # ambiguous → low-confidence guess
    return results


@worker_env.task
async def process_batch(batch: list[Review], batch_id: int) -> list[LabeledReview]:
    """Label one micro-batch. Submit → poll, both checkpointed."""
    texts = [r.text for r in batch]
    job_id = await submit_labeling(texts)
    labels = await poll_labeling(job_id, texts)
    print(f"batch {batch_id}: labeled {len(batch)} reviews (job {job_id})")
    return [
        LabeledReview(text=r.text, sentiment=r.sentiment, predicted=p, confidence=c)
        for r, (p, c) in zip(batch, labels)
    ]


@driver_env.task
async def assemble_dataset(results: list[list[LabeledReview]]) -> File:
    """Flatten every batch into one parquet dataset on blob storage."""
    rows = [asdict(r) for batch in results for r in batch]
    df = pd.DataFrame(rows)
    path = "/tmp/review_dataset.parquet"
    df.to_parquet(path, index=False)
    print(f"assembled dataset with {len(df)} rows")
    return await File.from_local(path)


@driver_env.task(produces_artifacts=True)
async def validate_dataset(dataset: File, min_quality: float) -> File:
    """Quality gate. Labeling 'quality' = fraction of reviews whose predicted
    label matches ground truth. Below the threshold we fail the run; at or above
    it we publish the dataset as an Artifact for Chapter 2 to consume."""
    local = await dataset.download()
    df = pd.read_parquet(local)
    quality = float((df["predicted"] == df["sentiment"]).mean())
    print(f"dataset quality = {quality:.3f} (threshold {min_quality})")
    if quality < min_quality:
        raise ValueError(
            f"dataset quality {quality:.3f} below threshold {min_quality}. "
            f"Rescue this run with:  flyte rerun <run> --recover --min-quality 0.7"
        )
    return flyte.artifacts.new(
        dataset,
        flyte.artifacts.Metadata(
            name="review-dataset",
            description="Labeled product-review training set",
            attrs={"rows": str(len(df)), "quality": f"{quality:.3f}"},
        ),
    )


@driver_env.task
async def main(n_reviews: int = 200, batch_size: int = 25, min_quality: float = 0.95) -> File:
    """Prepare the dataset. Fails at the quality gate on defaults — that failure
    is the recover/fork exercise, not a bug in the pipeline."""
    reviews = _synth_reviews(n_reviews)
    batches = [reviews[i : i + batch_size] for i in range(0, len(reviews), batch_size)]

    with flyte.group("label-batches"):
        results = await asyncio.gather(*(process_batch(b, i) for i, b in enumerate(batches)))

    dataset = await assemble_dataset(results)
    return await validate_dataset(dataset, min_quality)


if __name__ == "__main__":
    flyte.init_from_config()
    run = flyte.run(main)
    print(run.name)
    print(run.url)
