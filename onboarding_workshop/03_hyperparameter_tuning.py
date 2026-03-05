"""
Exercise 3: Parallel Hyperparameter Tuning
============================================
Run multiple HPO trials concurrently — each in its own pod.

Concepts: asyncio.gather, cache="auto" at env level, Optuna integration

Run locally:   flyte run --local 03_hyperparameter_tuning.py optimize
Run on Union:  flyte run 03_hyperparameter_tuning.py optimize -- --n_trials 20 --concurrency 5
"""

import asyncio
from typing import Union

import flyte

img = flyte.Image.from_debian_base().with_pip_packages(
    "pandas", "pyarrow", "scikit-learn", "lightgbm", "optuna"
)

env = flyte.TaskEnvironment(
    name="hpo",
    image=img,
    resources=flyte.Resources(cpu="1", memory="1Gi"),
    cache="auto",  # all tasks in this env are cached
)


@env.task
async def run_trial(params: dict[str, Union[int, float]]) -> float:
    """
    Single trial. Cached: identical params won't re-run.
    Each trial gets its own pod.
    """
    import lightgbm as lgb
    import numpy as np
    import pandas as pd
    from sklearn.model_selection import cross_val_score

    np.random.seed(42)
    n = 2000
    df = pd.DataFrame({
        "target": 100 + np.cumsum(np.random.randn(n) * 0.5),
        "f1": np.random.randn(n),
        "f2": np.random.exponential(1, n),
        "f3": np.tile(range(24), n // 24 + 1)[:n],
    })

    model = lgb.LGBMRegressor(
        num_leaves=int(params["num_leaves"]),
        n_estimators=int(params["n_estimators"]),
        learning_rate=params["learning_rate"],
        verbose=-1,
    )
    scores = cross_val_score(model, df.drop(columns=["target"]), df["target"],
                            cv=3, scoring="neg_mean_absolute_error")
    mae = float(-scores.mean())
    print(f"Trial: {params} -> MAE: {mae:.4f}")
    return mae


@env.task
async def optimize(n_trials: int = 10, concurrency: int = 3) -> dict:
    """
    Parallel HPO: n_trials total, concurrency running at once.
    Semaphore controls how many pods run simultaneously.
    """
    import optuna

    study = optuna.create_study(direction="minimize",
                                sampler=optuna.samplers.TPESampler(seed=42))
    sem = asyncio.Semaphore(concurrency)

    async def one_trial():
        async with sem:
            t = study.ask()
            params = {
                "num_leaves": t.suggest_int("num_leaves", 10, 60),
                "n_estimators": t.suggest_int("n_estimators", 30, 150),
                "learning_rate": t.suggest_float("learning_rate", 0.01, 0.3, log=True),
            }
            try:
                score = await run_trial(params)
                study.tell(t, score)
            except Exception as e:
                print(f"Trial failed: {e}")
                study.tell(t, state=optuna.trial.TrialState.FAIL)

    await asyncio.gather(*[one_trial() for _ in range(n_trials)])

    best = study.best_trial
    print(f"Best MAE: {best.value:.4f}, Params: {best.params}")
    return best.params


if __name__ == "__main__":
    flyte.init_from_config()
    run = flyte.run(optimize, n_trials=10, concurrency=3)
    print(f"Run URL: {run.url}")
    run.wait()
