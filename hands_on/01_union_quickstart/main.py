from pathlib import Path

import flyte

demo_env = flyte.TaskEnvironment(
    name="demo_env",
    resources=flyte.Resources(cpu=1, memory="200Mi"),
)


@demo_env.task()
def join_names(first_name: str, last_name: str) -> str:
    return first_name + last_name


@demo_env.task()
def get_name_length(name: str) -> int:
    return len(name)


@demo_env.task()
async def demo_workflow():
    print("Starting demo workflow...")

    full_name = join_names("Leon", "Menkreo")
    name_length = get_name_length(full_name)
    print(f"Lenght of name {full_name} is {name_length}")


if __name__ == "__main__":
    flyte.init_from_config(
        root_dir=Path(__file__).parent, path_or_config=".flyte/config.yaml"
    )

    result = flyte.run(demo_workflow)
    print(result.url)
