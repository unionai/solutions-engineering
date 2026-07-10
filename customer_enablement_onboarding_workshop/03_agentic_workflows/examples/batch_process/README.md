# Exercise 1: Batch Document Processing Pipeline

## What You'll Learn

- Defining `TaskEnvironment` with images, resources, and reusable containers
- Writing async tasks with `@env.task`
- Parallel fanout using `asyncio.gather` and `flyte.group`
- Using multiple environments with `depends_on`
- Running and monitoring workflows on Union

## Scenario

You have a collection of raw product documents (text/markdown) that need to be processed by an LLM to extract structured information, then stored in a vector database for downstream search.

This is a common batch ETL pattern: **fan out** document processing across parallel workers, then **collect** and store the results.

## Workflow Design

```
batch_pipeline (driver)
├── process_document(doc_1)  ─┐
├── process_document(doc_2)   ├── parallel fanout (flyte.group)
├── process_document(doc_3)   │
└── process_document(doc_N)  ─┘
         │
         ▼
   store_in_vectordb(processed_docs)
         │
         ▼
   return summary
```

### Tasks

| Task | Environment | What it does |
|------|-------------|--------------|
| `process_document` | `worker_env` | Uses OpenAI Agent to extract structured info from a raw document |
| `store_in_vectordb` | `worker_env` | Stores processed documents + embeddings in ChromaDB |
| `batch_pipeline` | `driver_env` | Orchestrates: fans out processing, collects results, stores in vector DB |

### Union Features Highlighted

| Feature | How it's used |
|---------|---------------|
| **Reusable containers** | `ReusePolicy` keeps warm replicas for fast successive runs |
| **Parallel fanout** | `asyncio.gather` + `flyte.group` processes documents concurrently |
| **Multiple environments** | `driver_env` orchestrates, `worker_env` does heavy lifting |
| **`depends_on`** | Driver declares dependency on worker environment |
| **Image declaration** | `Image.from_debian_base().with_pip_packages(...)` for reproducible environments |

## How to Run

```bash
cd batch_process
python workflow.py
```

This will print a run URL. Open it in your browser to watch the workflow execute on Union.

## Key Concepts

### Reusable Containers

Instead of spinning up a new container for every task invocation, reusable containers keep warm replicas alive. This dramatically reduces cold-start latency for successive calls:

```python
reusable=flyte.ReusePolicy(
    replicas=(1, 3),   # min 1, max 3 replicas
    idle_ttl=120,       # keep alive 2 min after last use
    concurrency=5,      # each replica handles 5 concurrent tasks
)
```

### Parallel Fanout

Fan out work across multiple containers using standard Python async:

```python
with flyte.group("process-docs"):
    tasks = [process_document(doc) for doc in documents]
    results = await asyncio.gather(*tasks)
```

Each `process_document` call runs in its own container. `flyte.group` groups them visually in the Union UI.
