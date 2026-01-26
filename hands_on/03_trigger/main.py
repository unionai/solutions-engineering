import pathlib

import flyte

env = flyte.TaskEnvironment(name="my_task_env")

custom_cron_trigger = flyte.Trigger(
    "custom_cron",
    flyte.Cron("0 0 * * *"),
    auto_activate=False,  # Dont create runs yet
)


@env.task(triggers=custom_cron_trigger)
def custom_task() -> str:
    return "Hello, world!"


if __name__ == "__main__":
    flyte.init_from_config(root_dir=pathlib.Path(__file__).parent)
    flyte.deploy(env)
