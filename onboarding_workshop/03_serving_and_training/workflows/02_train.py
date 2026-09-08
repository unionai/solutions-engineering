"""
Chapter 2b — Train the winner and publish it as a model Artifact
================================================================
Fit the final review classifier with the hyperparameters HPO chose, then
publish it as a named, versioned Artifact that Chapters 3 and 4 consume.

What this chapter shows:

- Model Artifact:   the fitted pipeline is returned via `flyte.artifacts.new`
                    under the name `review-classifier`, giving you lineage from
                    dataset → model → predictions/serving in the UI.
- Clean hand-off:   `train` takes the winning `C` / `ngram` from `02_hpo.py`, so
                    the notebook threads optimize() → train() with no glue.

Scaling up (reference, not run here): to train a real model, swap `train_env`
for a GPU environment and the sklearn fit for a transformer fine-tune. For
multi-node distributed training, Flyte's `Elastic` plugin launches torchrun
across nodes — see the distributed-pretraining tutorial. The task interface and
the Artifact hand-off stay identical.

Run on Union:  uv run flyte run 02_train.py train
               uv run flyte run 02_train.py train --c 10.0 --ngram 2
"""

import pickle

import flyte
from flyte.io import File

image = flyte.Image.from_debian_base().with_pip_packages("scikit-learn")

train_env = flyte.TaskEnvironment(
    name="train_model",
    image=image,
    resources=flyte.Resources(cpu=2, memory="1Gi"),
)

_POS = ["love it", "works great", "excellent quality", "highly recommend",
        "fast and reliable", "best purchase ever", "so happy with this"]
_NEG = ["broke immediately", "terrible support", "waste of money", "very disappointed",
        "stopped working", "would not buy again", "cheap and flimsy"]


def _synth(n: int) -> tuple[list[str], list[str]]:
    texts, labels = [], []
    for i in range(n):
        if i % 2 == 0:
            texts.append(_POS[i % len(_POS)])
            labels.append("positive")
        else:
            texts.append(_NEG[i % len(_NEG)])
            labels.append("negative")
    return texts, labels


@train_env.task(produces_artifacts=True)
async def train(c: float = 1.0, ngram: int = 2, n_reviews: int = 300) -> File:
    """Fit the classifier on the full dataset and publish it as an Artifact.

    `c` is the LogisticRegression inverse-regularization strength (run-input
    names must be lowercase, so it is `c`, not `C`)."""
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline

    texts, labels = _synth(n_reviews)
    model = Pipeline([
        ("tfidf", TfidfVectorizer(ngram_range=(1, ngram))),
        ("clf", LogisticRegression(C=c, max_iter=1000)),
    ])
    model.fit(texts, labels)
    train_acc = float(model.score(texts, labels))
    print(f"trained review-classifier: C={c} ngram={ngram} train_accuracy={train_acc:.4f}")

    path = "/tmp/review_classifier.pkl"
    with open(path, "wb") as f:
        pickle.dump(model, f)
    model_file = await File.from_local(path)

    return flyte.artifacts.new(
        model_file,
        flyte.artifacts.Metadata(
            name="review-classifier",
            description="TF-IDF + LogisticRegression product-review sentiment classifier",
            attrs={"C": str(c), "ngram": str(ngram), "train_accuracy": f"{train_acc:.4f}"},
        ),
    )


if __name__ == "__main__":
    flyte.init_from_config()
    run = flyte.run(train)
    print(run.name)
    print(run.url)
