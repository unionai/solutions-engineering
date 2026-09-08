"""
Chapter 3 — Batch inference at scale with a shared DynamicBatcher
=================================================================
Score a large corpus of reviews with the trained `review-classifier`. The twist
over a plain fan-out: a **`DynamicBatcher`** shared per replica aggregates records
from many concurrent callers into cost-budgeted batches, so the model runs on
full batches instead of one record at a time.

The pattern (straight from the batch-inference tutorial):

- **Load once per replica.** `@alru_cache` builds the model + batcher a single
  time per container; every concurrent `infer_batch` on that replica reuses them.
- **Shared batcher.** `infer_batch` just submits its records and awaits the
  results; the batcher's aggregation loop assembles batches across *all* callers
  (respecting `target_batch_cost` / `max_batch_size` / `batch_timeout_s`) and runs
  `process_fn` once per batch. This is what keeps a GPU full; here it's CPU
  sklearn, but the shape is identical.
- **Fan-out driver.** The driver chunks the corpus and launches `infer_batch`
  concurrently on the reusable pool, so the batcher always has a full queue.

Consumes the `review-classifier` model File (from `02_train.py`) and publishes a
`review-predictions` Artifact, completing dataset -> model -> predictions lineage.

  uv run flyte run 03_batch_inference.py score --model s3://.../review_classifier.pkl
"""

import asyncio
import pickle

import flyte
import pandas as pd
from async_lru import alru_cache
from flyte.extras import DynamicBatcher
from flyte.io import File

image = flyte.Image.from_debian_base().with_pip_packages(
    "scikit-learn", "pandas", "pyarrow", "async-lru", "unionai-reuse>=0.1.9"
)

# Reusable pool with concurrency: several infer_batch calls share one replica —
# and therefore one batcher — feeding it from multiple producers at once.
worker_env = flyte.TaskEnvironment(
    name="infer_worker",
    image=image,
    resources=flyte.Resources(cpu=2, memory="1Gi"),
    reusable=flyte.ReusePolicy(replicas=(1, 2), concurrency=8, idle_ttl=120),
)

driver_env = flyte.TaskEnvironment(
    name="infer_driver",
    image=image,
    resources=flyte.Resources(cpu=1, memory="512Mi"),
    depends_on=[worker_env],
)

_UNLABELED = [
    "the battery lasts forever", "arrived broken and useless", "does exactly what it says",
    "customer service ignored me", "beautiful design and fast", "fell apart after a week",
    "worth every penny", "never buying this brand again",
]


@alru_cache(maxsize=1)
async def get_batcher(model_path: str) -> DynamicBatcher:
    """Process-level singleton: load the model and start the batcher once per
    replica. Every concurrent infer_batch on this replica reuses both."""
    local = await File.from_existing_remote(model_path).download()
    with open(local, "rb") as f:
        model = pickle.load(f)

    async def predict_batch(texts: list[str]) -> list[str]:
        # One model call for the whole aggregated batch, results in input order.
        return [str(p) for p in model.predict(texts)]

    batcher = DynamicBatcher(
        process_fn=predict_batch,
        target_batch_cost=64,   # ~64 records per batch (default cost 1/record)
        max_batch_size=64,
        batch_timeout_s=0.05,
    )
    await batcher.start()
    print(f"loaded model + started batcher (once per replica) from {model_path}")
    return batcher


@worker_env.task
async def infer_batch(texts: list[str], model: File, chunk_id: int) -> list[str]:
    """Submit this chunk's records into the shared batcher and await the results."""
    batcher = await get_batcher(model.path)
    futures = await batcher.submit_batch(texts)
    results = await asyncio.gather(*futures)
    s = batcher.stats
    print(
        f"chunk {chunk_id}: scored {len(texts)} reviews "
        f"(batcher: {s.total_batches} batches, avg_size={s.avg_batch_size:.1f}, util={s.utilization:.2f})"
    )
    return [str(r) for r in results]


@driver_env.task(produces_artifacts=True)
async def score(model: File, n_reviews: int = 400, chunk_size: int = 50) -> File:
    """Fan out scoring across the corpus; the batcher aggregates across callers."""
    corpus = [_UNLABELED[i % len(_UNLABELED)] for i in range(n_reviews)]
    chunks = [corpus[i : i + chunk_size] for i in range(0, len(corpus), chunk_size)]

    with flyte.group("score-chunks"):
        results = await asyncio.gather(
            *(infer_batch(c, model, i) for i, c in enumerate(chunks))
        )

    rows = [p for chunk in results for p in chunk]
    df = pd.DataFrame({"text": corpus, "predicted": rows})
    pos = float((df["predicted"] == "positive").mean())
    print(f"scored {len(df)} reviews — {pos:.1%} positive")

    path = "/tmp/review_predictions.parquet"
    df.to_parquet(path, index=False)
    preds_file = await File.from_local(path)

    return flyte.artifacts.new(
        preds_file,
        flyte.artifacts.Metadata(
            name="review-predictions",
            description="Batch predictions from the review-classifier",
            attrs={"rows": str(len(df)), "pct_positive": f"{pos:.3f}"},
        ),
    )


if __name__ == "__main__":
    import sys

    flyte.init_from_config()
    if len(sys.argv) < 2:
        raise SystemExit("usage: python 03_batch_inference.py <model_s3_uri>")
    run = flyte.run(score, model=File.from_existing_remote(sys.argv[1]))
    print(run.name)
    print(run.url)
