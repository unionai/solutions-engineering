"""
Product Chat App - Flyte 2.0 Workshop Exercise

A minimal RAG-based chat app using FastAPI, ChromaDB, and Anthropic Claude.
Demonstrates deploying always-on services with Flyte Apps.
"""

from contextlib import asynccontextmanager

import anthropic
import flyte
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from flyte.app.extras import FastAPIAppEnvironment
from mock_data import SAMPLE_DOCS
from pydantic import BaseModel
from tools import TOOL_FUNCTIONS, TOOLS
from ui import CHAT_HTML

ANTHROPIC_MODEL = "claude-haiku-4-5-20251001"


chroma_collection = None


# --- FastAPI App ---


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize ChromaDB with sample documents on startup."""
    global chroma_collection

    import chromadb

    client = chromadb.Client()
    chroma_collection = client.create_collection(name="product_docs")
    chroma_collection.add(
        documents=SAMPLE_DOCS,
        ids=[f"doc-{i}" for i in range(len(SAMPLE_DOCS))],
    )

    yield


app = FastAPI(
    title="Product Chat",
    description="RAG-based product question answering",
    version="1.0.0",
    lifespan=lifespan,
)


# --- Flyte App Environment ---

app_env = FastAPIAppEnvironment(
    name="product-chat",
    app=app,
    description="RAG-based product chat assistant for industrial equipment",
    image=flyte.Image.from_debian_base(python_version=(3, 12)).with_pip_packages(
        "fastapi",
        "uvicorn",
        "anthropic",
        "chromadb",
    ),
    resources=flyte.Resources(cpu=1, memory="1Gi"),
    secrets=[flyte.Secret(key="ANTHROPIC_API_KEY", as_env_var="ANTHROPIC_API_KEY")],
    requires_auth=False,
    include=["ui.py", "tools.py", "mock_data.py"],
)


class ChatRequest(BaseModel):
    question: str


class ChatResponse(BaseModel):
    answer: str


@app.get("/")
async def root():
    """Simple HTML chat interface."""
    return HTMLResponse(CHAT_HTML)


@app.post("/chat")
async def chat(request: ChatRequest) -> ChatResponse:
    """Process a question using Anthropic Claude with tool use."""
    client = anthropic.AsyncAnthropic()

    messages = [{"role": "user", "content": request.question}]
    system_prompt = (
        "You are a helpful product specialist for industrial manufacturing equipment. "
        "Use the search_catalog tool to find specific products and the retrieve_docs tool "
        "to find technical information. Provide clear, concise answers based on the retrieved information."
    )

    response = await client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=1024,
        system=system_prompt,
        tools=TOOLS,
        messages=messages,
    )

    # Handle tool use loop
    while response.stop_reason == "tool_use":
        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                tool_fn = TOOL_FUNCTIONS[block.name]
                result = tool_fn(**block.input)
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    }
                )

        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": tool_results})

        response = await client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=1024,
            system=system_prompt,
            tools=TOOLS,
            messages=messages,
        )

    # Extract final text response
    answer = ""
    for block in response.content:
        if hasattr(block, "text"):
            answer += block.text

    return ChatResponse(answer=answer or "I couldn't generate a response.")


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok"}


if __name__ == "__main__":
    flyte.init_from_config()
    deployments = flyte.deploy(app_env)
    print("\nDeployed Product Chat App successfully.")
    for d in deployments:
        print(d)
