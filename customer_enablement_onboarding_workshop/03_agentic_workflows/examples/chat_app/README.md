# Exercise 2: Real-Time RAG Chat App

## What You'll Learn

- Deploying always-on services with Flyte Apps (`FastAPIAppEnvironment`)
- Building a RAG (Retrieval-Augmented Generation) chat endpoint
- Using OpenAI Agents SDK with custom tools for structured retrieval
- The difference between `flyte.run` (workflows) and `flyte.deploy` (apps)

## Scenario

Your sales team needs a chat interface that can answer product questions in real time. The app:

1. Receives a question via API
2. Searches a product catalog for relevant items
3. Retrieves related documentation from a vector store
4. Uses an AI agent to synthesize a grounded answer

This exercise builds a FastAPI service deployed as a Flyte App on Union.

## Architecture

```
User question
     │
     ▼
FastAPI endpoint (/chat)
     │
     ├── search_catalog(query)     ─┐
     │                               ├── OpenAI Agent tool calls
     ├── retrieve_docs(query)      ─┘
     │
     ▼
Agent synthesizes answer from retrieved context
     │
     ▼
Response returned to user
```

### Components

| Component | What it does |
|-----------|--------------|
| `FastAPIAppEnvironment` | Defines the deployable app with image, resources, secrets |
| `/chat` endpoint | Accepts a question, runs the agent, returns an answer |
| `search_catalog` tool | Searches a mock product catalog (simulates constructor.io or similar) |
| `retrieve_docs` tool | Queries ChromaDB for relevant document chunks |
| OpenAI Agent | Orchestrates tool calls and synthesizes a final answer |

### Union Features Highlighted

| Feature | How it's used |
|---------|---------------|
| **Flyte Apps** | `FastAPIAppEnvironment` deploys a persistent service |
| **`flyte.deploy`** | Deploys the app (vs `flyte.run` for workflows) |
| **`requires_auth=False`** | Makes the endpoint publicly accessible |
| **Secrets** | OpenAI API key injected as environment variable |
| **Auto-scaling** | App scales based on request load |

## How to Run

```bash
cd chat_app
python app.py
```

This deploys the app and prints its URL. You can then:

```bash
# Query the chat endpoint
curl -X POST https://<app-url>/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "What products do you have for industrial automation?"}'
```

Or open `https://<app-url>/` in a browser for a simple chat UI.

## Key Concepts

### Flyte Apps vs Workflows

| | Workflows (`flyte.run`) | Apps (`flyte.deploy`) |
|---|---|---|
| **Lifecycle** | Runs once, produces outputs | Always-on, serves requests |
| **Use case** | Batch processing, pipelines | APIs, chat, dashboards |
| **Scaling** | Per-task containers | Auto-scaling replicas |
| **Entry point** | `@env.task` | FastAPI/Streamlit/etc |

### FastAPIAppEnvironment

```python
app_env = FastAPIAppEnvironment(
    name="my-chat-app",
    app=app,                    # Your FastAPI instance
    image=image,
    resources=flyte.Resources(cpu=1, memory="1Gi"),
    secrets=[flyte.Secret(key="openai-api-key", as_env_var="OPENAI_API_KEY")],
    requires_auth=False,        # Public endpoint
)
```

### Agent Tools for RAG

The OpenAI Agents SDK lets you define tools that the agent can call. In a RAG pattern, these tools handle retrieval:

```python
@function_tool
async def retrieve_docs(query: str) -> str:
    """Search the knowledge base for relevant documents."""
    results = collection.query(query_texts=[query], n_results=3)
    return "\n".join(results["documents"][0])
```
