"""
Chapter 2a — Hyperparameter optimization by fan-out
===================================================
Find the best settings for the review classifier by evaluating many
configurations *in parallel*, each on its own worker.

What this chapter shows:

- Fan-out HPO:      one `evaluate_config` action per hyperparameter combination,
                    launched together with `asyncio.gather` inside `flyte.group`.
- Reusable workers: the trial pool stays warm, so the trials skip pod startup.
- Best-model pick:  the driver collects every trial's cross-val score and
                    returns the winner, which Chapter 2b (`02_train.py`) trains.

The model is a TF-IDF + LogisticRegression text classifier (CPU, trains in
milliseconds) so the whole sweep finishes inside a workshop slot. Swap in a GPU
env + a transformer fine-tune to scale this up unchanged.

Run on Union:  uv run flyte run 02_hpo.py optimize
               uv run flyte run 02_hpo.py optimize --n_reviews 500
"""

import asyncio
from dataclasses import dataclass

import flyte

image = flyte.Image.from_debian_base().with_pip_packages(
    "scikit-learn", "unionai-reuse>=0.1.9"
)

trial_env = flyte.TaskEnvironment(
    name="hpo_trial",
    image=image,
    resources=flyte.Resources(cpu=1, memory="512Mi"),
    reusable=flyte.ReusePolicy(replicas=(1, 3), concurrency=4, idle_ttl=90),
)

driver_env = flyte.TaskEnvironment(
    name="hpo_driver",
    image=image,
    resources=flyte.Resources(cpu=1, memory="512Mi"),
    depends_on=[trial_env],
)


@dataclass
class TrialResult:
    C: float
    ngram: int
    score: float


_POS = ["love it", "works great", "excellent quality", "highly recommend",
        "fast and reliable", "best purchase ever", "so happy with this"]
_NEG = ["broke immediately", "terrible support", "waste of money", "very disappointed",
        "stopped working", "would not buy again", "cheap and flimsy"]


def _synth(n: int) -> tuple[list[str], list[str]]:
    texts, labels = [], []
    for i in range(n):
        if i % 2 == 0:
            texts.append(_POS[i % len(_POS)] + (" " + _NEG[i % len(_NEG)] if i % 7 == 0 else ""))
            labels.append("positive")
        else:
            texts.append(_NEG[i % len(_NEG)] + (" " + _POS[i % len(_POS)] if i % 7 == 0 else ""))
            labels.append("negative")
    return texts, labels


@trial_env.task
async def evaluate_config(C: float, ngram: int, n_reviews: int) -> TrialResult:
    """Train+score one hyperparameter combination with 3-fold cross-validation."""
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import cross_val_score
    from sklearn.pipeline import Pipeline

    texts, labels = _synth(n_reviews)
    pipe = Pipeline([
        ("tfidf", TfidfVectorizer(ngram_range=(1, ngram))),
        ("clf", LogisticRegression(C=C, max_iter=1000)),
    ])
    score = float(cross_val_score(pipe, texts, labels, cv=3).mean())
    print(f"trial C={C} ngram={ngram} -> cv_accuracy={score:.4f}")
    return TrialResult(C=C, ngram=ngram, score=score)


@driver_env.task
async def optimize(n_reviews: int = 300) -> TrialResult:
    """Fan out the whole grid, then return the best-scoring config."""
    grid = [(C, ng) for C in (0.1, 1.0, 10.0) for ng in (1, 2)]
    with flyte.group("hpo-sweep"):
        results = await asyncio.gather(*(evaluate_config(C, ng, n_reviews) for C, ng in grid))
    best = max(results, key=lambda r: r.score)
    print(f"WINNER: C={best.C} ngram={best.ngram} cv_accuracy={best.score:.4f}")
    return best


if __name__ == "__main__":
    flyte.init_from_config()
    run = flyte.run(optimize)
    print(run.name)
    print(run.url)
