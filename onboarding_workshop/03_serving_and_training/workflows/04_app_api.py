"""
Chapter 4a — Serve the model as a REST API
==========================================
Put the trained `review-classifier` behind a always-reachable HTTP endpoint.

What this chapter shows:

- Flyte Apps:       a `FastAPIAppEnvironment` turns a plain FastAPI app into a
                    hosted, autoscaling service with its own URL.
- Artifact mount:   `Parameter(value=ArtifactValue(name="review-classifier"))`
                    pins the model Artifact from Chapter 2 and Union injects it
                    into the app as a local file — no bucket paths, no glue.
- Load once:        `@env.on_startup` loads the pickle once per replica before
                    the server accepts traffic; every request reuses it.
- Open access:      `requires_auth=False` so you can `curl` it directly.

Deploy it:
  uv run flyte serve 04_app_api.py app_env        # prints the app URL
Then:
  curl "<url>/health"
  curl "<url>/predict?text=this+product+is+amazing"
"""

import pickle

import flyte
import flyte.io
from fastapi import FastAPI
from flyte.app import ArtifactValue, Parameter
from flyte.app.extras import FastAPIAppEnvironment

image = flyte.Image.from_debian_base().with_pip_packages(
    "fastapi", "uvicorn", "scikit-learn"
)

app = FastAPI(title="Review Radar API", version="1.0.0")
_state: dict = {}


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "model_loaded": "model" in _state}


@app.get("/predict")
async def predict(text: str) -> dict:
    """Classify a single review's sentiment."""
    model = _state.get("model")
    if model is None:
        return {"error": "model not loaded yet"}
    label = str(model.predict([text])[0])
    confidence = float(model.predict_proba([text]).max())
    return {"text": text, "predicted": label, "confidence": confidence}


app_env = FastAPIAppEnvironment(
    name="review-radar-api",
    app=app,
    image=image,
    resources=flyte.Resources(cpu=1, memory="1Gi"),
    requires_auth=False,
    # Keep at least one warm replica so there's no cold start; scale to 3 under load.
    scaling=flyte.app.Scaling(replicas=(1, 3)),
    parameters=[
        # 'model' matches the argument name in on_startup below. Union resolves the
        # latest version of the Artifact, downloads it, and injects a flyte.io.File.
        Parameter(name="model", value=ArtifactValue(name="review-classifier", type="file"), download=True),
    ],
)


@app_env.on_startup
async def startup(model: flyte.io.File) -> None:
    with open(model.path, "rb") as f:
        _state["model"] = pickle.load(f)
    print(f"loaded review-classifier from {model.path}")


if __name__ == "__main__":
    flyte.init_from_config()
    served = flyte.serve(app_env)
    print(served.url)
