def join_names(first_name: str, last_name: str) -> str:
    return first_name + last_name


def get_name_length(name: str) -> int:
    return len(name)


async def main():
    print("Starting demo workflow...")

    full_name = join_names("Leon", "Menkreo")
    name_length = get_name_length(full_name)
    print(f"Lenght of name {full_name} is {name_length}")


if __name__ == "__main__":
    main()
