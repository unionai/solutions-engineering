import asyncio
import random
import time
from pathlib import Path

import flyte

image = flyte.Image.from_debian_base().with_pip_packages("httpx")

worker = flyte.TaskEnvironment(
    name="doc_worker",
    description="Worker for document processing",
    image=image,
    resources=flyte.Resources(cpu=2, memory="2Gi"),
)

orchestrator = flyte.TaskEnvironment(
    name="orchestrator",
    description="Coordinates parallel work",
    image=image,
    resources=flyte.Resources(cpu=1, memory="1Gi"),
    depends_on=[worker],
)


@worker.task
async def process_single_document(doc_id: int) -> dict[str, int | str]:
    import httpx

    print(f"Processing document {doc_id}...")

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"https://jsonplaceholder.typicode.com/posts/{doc_id % 100 + 1}"
        )
        data = resp.json()

    time.sleep(random.randint(10, 15))
    print(f"Document {doc_id} complete!!!")

    return {
        "doc_id": doc_id,
        "title": data.get("title", "")[:50],
        "status": "processed",
    }


@orchestrator.task
async def process_documents(doc_ids: list[int]) -> list[dict[str, int | str]]:
    print(f"Processing {len(doc_ids)} documents in parallel...")

    tasks = [process_single_document(doc_id) for doc_id in doc_ids]

    results = await asyncio.gather(*tasks)

    print(f"All {len(results)} documents processed!")
    return results


if __name__ == "__main__":
    flyte.init_from_config(
        root_dir=Path(__file__).parent, path_or_config=".flyte/config.yaml"
    )

    result = flyte.run(process_documents, doc_ids=[1, 2, 3])
    print(result.url)
