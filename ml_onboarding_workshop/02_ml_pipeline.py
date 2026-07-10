"""
Exercise 2: ML Pipeline Concepts
==================================
Demonstrates the building blocks for a forecasting workflow.
Focus is on Union concepts, not model complexity.

Concepts: caching, flyte.io.File, flyte.report, image building, resource override

Run locally:   flyte run --local 02_ml_pipeline.py pipeline
Run on Union:  flyte run 02_ml_pipeline.py pipeline
"""

import json

import flyte
import flyte.report
from flyte.io import File

# Image builder: list pip packages, Union builds the container for you.
# No Dockerfile, no registry, no local docker build.
img = flyte.Image.from_debian_base().with_pip_packages(
    "pandas", "pyarrow", "scikit-learn", "lightgbm"
)

env = flyte.TaskEnvironment(
    name="ml_pipeline",
    image=img,
    resources=flyte.Resources(cpu="1", memory="1Gi"),
)


# --- cache="auto": only runs once, reuses output on subsequent runs ---
@env.task(cache="auto")
async def load_data() -> File:
    """
    Cached data loading. On rerun (e.g., tweaking hyperparameters),
    Union skips this entirely and reuses the cached output.
    """
    import numpy as np
    import pandas as pd

    np.random.seed(42)
    df = pd.DataFrame({
        "price": 100 + np.cumsum(np.random.randn(5000) * 0.5),
        "volume": np.random.exponential(1000, 5000),
        "hour": np.tile(range(24), 5000 // 24 + 1)[:5000],
        "day_of_week": np.tile(range(7), 5000 // 7 + 1)[:5000],
    })
    path = "data.parquet"
    df.to_parquet(path, index=False)
    print(f"Loaded {len(df)} rows")
    return await File.from_local(path)


# --- flyte.io.File: pass artifacts between tasks ---
@env.task
async def train(data_file: File) -> tuple[File, str]:
    """
    Train a simple model. File artifacts are automatically
    uploaded/downloaded between tasks.
    """
    import lightgbm as lgb
    import pandas as pd
    from sklearn.metrics import mean_absolute_error
    from sklearn.model_selection import train_test_split

    data_path = await data_file.download()
    df = pd.read_parquet(data_path)

    X = df.drop(columns=["price"])
    y = df["price"]
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, shuffle=False)

    model = lgb.LGBMRegressor(n_estimators=50, verbose=-1)
    model.fit(X_train, y_train)

    mae = mean_absolute_error(y_test, model.predict(X_test))
    print(f"MAE: {mae:.4f}")

    import joblib
    joblib.dump(model, "model.joblib")

    metrics = {"mae": round(mae, 4), "features": list(X.columns),
               "importances": model.feature_importances_.tolist()}
    return await File.from_local("model.joblib"), json.dumps(metrics)


# --- report=True: rich HTML reports visible in the Union UI ---
@env.task(report=True)
async def report(metrics_json: str) -> str:
    """Generate a report with model metrics. Visible as a tab in the Union UI."""
    m = json.loads(metrics_json)

    # Build a simple feature importance table
    rows = sorted(zip(m["features"], m["importances"]), key=lambda x: -x[1])
    table_rows = "".join(f"<tr><td>{f}</td><td>{i}</td></tr>" for f, i in rows)

    html = f"""
    <h2>Forecast Model Report</h2>
    <p><b>MAE:</b> {m['mae']}</p>
    <h3>Feature Importance</h3>
    <table border='1' cellpadding='6' style='border-collapse:collapse;'>
        <tr style='background:#eee;'><td><b>Feature</b></td><td><b>Importance</b></td></tr>
        {table_rows}
    </table>
    """
    await flyte.report.replace.aio(html)
    await flyte.report.flush.aio()
    return f"MAE: {m['mae']}"


# --- Orchestrator ---
@env.task
async def pipeline() -> str:
    data_file = await load_data()           # cached after first run
    model_file, metrics = await train(data_file)
    summary = await report(metrics)
    return summary


# --- OOM retry: catch out-of-memory and retry with more resources ---
@env.task
async def memory_hungry(size_mb: int) -> str:
    """Allocate a chunk of memory. Will OOM if size exceeds the pod limit."""
    data = bytearray(size_mb * 1024 * 1024)
    print(f"Allocated {size_mb}MB successfully")
    return f"Processed {size_mb}MB"


@env.task
async def pipeline_with_oom_retry() -> str:
    """
    Try with small memory, catch OOM, retry with more.
    Union detects when a pod is killed for exceeding its memory limit
    and raises flyte.errors.OOMError.
    """
    import flyte.errors

    mem_levels = ["256Mi", "512Mi", "1Gi"]
    for mem in mem_levels:
        try:
            result = await memory_hungry.override(
                resources=flyte.Resources(cpu="1", memory=mem)
            )(400)  # try to allocate 400MB
            return result
        except flyte.errors.OOMError:
            print(f"OOM with {mem}, retrying with more memory...")
    raise RuntimeError("Failed even with max memory")


if __name__ == "__main__":
    flyte.init_from_config()
    run = flyte.run(pipeline)
    print(f"Run URL: {run.url}")
    run.wait()
