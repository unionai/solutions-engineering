import asyncio

import anthropic

import flyte

ANTHROPIC_MODEL = "claude-haiku-4-5-20251001"

worker_env = flyte.TaskEnvironment(
    name="doc-worker",
    resources=flyte.Resources(cpu=2, memory="4Gi"),
    image=flyte.Image.from_debian_base().with_pip_packages(
        "anthropic",
        "chromadb",
        "unionai-reuse>=0.1.9",
    ),
    secrets=[flyte.Secret(key="ANTHROPIC_API_KEY", as_env_var="ANTHROPIC_API_KEY")],
    reusable=flyte.ReusePolicy(
        replicas=(1, 3),
        idle_ttl=120,
        concurrency=5,
        scaledown_ttl=60,
    ),
)

driver_env = flyte.TaskEnvironment(
    name="doc-driver",
    resources=flyte.Resources(cpu=1, memory="2Gi"),
    image=flyte.Image.from_debian_base().with_pip_packages(
        "anthropic",
        "chromadb",
    ),
    depends_on=[worker_env],
)


@worker_env.task()
async def process_document(doc_text: str, doc_id: str) -> dict:
    """Extract structured information from a raw document using Anthropic."""

    @flyte.trace
    async def extract_with_anthropic(text: str) -> str:
        client = anthropic.AsyncAnthropic()
        message = await client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=1024,
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Extract structured information from this document. "
                        "Return JSON with fields: title, summary, key_topics (list), content (cleaned markdown).\n\n"
                        f"Document:\n{text}"
                    ),
                }
            ],
        )
        return message.content[0].text

    extracted = await extract_with_anthropic(doc_text)

    return {
        "id": doc_id,
        "title": f"Document {doc_id}",
        "summary": extracted[:200],
        "key_topics": ["extracted", "topics"],
        "content": doc_text,
    }


@worker_env.task()
async def store_in_vectordb(documents: list[dict]) -> str:
    """Store processed documents in ChromaDB with embeddings."""
    import chromadb

    client = chromadb.Client()
    collection = client.create_collection(name="documents")

    ids = [doc["id"] for doc in documents]
    contents = [doc["content"] for doc in documents]
    metadatas = [
        {
            "title": doc["title"],
            "summary": doc["summary"],
        }
        for doc in documents
    ]

    collection.add(
        ids=ids,
        documents=contents,
        metadatas=metadatas,
    )

    return f"Stored {len(documents)} documents in ChromaDB collection 'documents'"


@driver_env.task()
async def batch_pipeline(documents: list[str]) -> str:
    """Orchestrate batch document processing pipeline."""

    with flyte.group("process-docs"):
        tasks = [
            process_document(doc, f"doc_{idx}")
            for idx, doc in enumerate(documents, start=1)
        ]
        processed_docs = await asyncio.gather(*tasks)

    summary = await store_in_vectordb(processed_docs)
    return summary


if __name__ == "__main__":
    flyte.init_from_config()

    sample_docs = [
        "# Product A\nHigh-performance widget for enterprise use. Features include real-time sync and AI-powered insights.",
        "# Product B\nLightweight mobile solution. Optimized for on-the-go teams with offline mode and cloud backup.",
        "# Product C\nDeveloper platform with REST API, webhooks, and SDKs in Python, JavaScript, and Go.",
        "# Product D\nAnalytics dashboard with customizable reports, data visualization, and automated alerting.",
    ]

    run = flyte.run(batch_pipeline, sample_docs)
    print(f"Run URL: {run.url}")
