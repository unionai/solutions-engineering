"""
Exercise 4: Production Features
=================================
Scheduling, BigQuery, and taking workflows to production.

Concepts: triggers (cron), flyte.deploy(), BigQuery connector, domains

Deploy:   flyte deploy 04_production.py
"""

from datetime import datetime

import flyte

env = flyte.TaskEnvironment(
    name="production",
    resources=flyte.Resources(cpu="1", memory="1Gi"),
)


# --- Scheduled trigger: monthly cron ---
@env.task(
    triggers=flyte.Trigger(
        "monthly_forecast",
        flyte.Cron("0 6 1 * *"),  # 6 AM on the 1st of every month
        inputs={"run_date": flyte.TriggerTime},
    ),
    cache="auto",
)
async def monthly_forecast(run_date: datetime) -> str:
    """Runs automatically every month. run_date is injected by the trigger."""
    month = run_date.strftime("%Y-%m")
    print(f"Running forecast for {month}")
    return f"Forecast done for {month}"


# --- BigQuery connector (template) ---
# Uncomment once connector is configured:
#
# from flyteplugins.connectors.bigquery import BigQueryConfig, BigQueryTask
# from flyte.io import DataFrame
#
# load_prices = BigQueryTask(
#     name="load_prices",
#     inputs={"month": str},
#     output_dataframe_type=DataFrame,
#     plugin_config=BigQueryConfig(ProjectID="my-gcp-project"),
#     query_template="""
#         SELECT * FROM `my-gcp-project.forecasting.prices`
#         WHERE FORMAT_DATE('%Y-%m', date) = '{{ .Inputs.month }}'
#     """,
# )


# --- Deploy: registers tasks + activates triggers ---
if __name__ == "__main__":
    flyte.init_from_config()
    flyte.deploy(env)
    print("Deployed. Monthly trigger active.")
