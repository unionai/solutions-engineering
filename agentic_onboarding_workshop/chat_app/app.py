"""
Product Chat App - Flyte 2.0 Workshop Exercise

A minimal RAG-based chat app using FastAPI, ChromaDB, and OpenAI Agents SDK.
Demonstrates deploying always-on services with Flyte Apps.
"""

from contextlib import asynccontextmanager

from agents import Agent, Runner, function_tool
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

import flyte
from flyte.app.extras import FastAPIAppEnvironment

from ui import CHAT_HTML

# --- Mock Data ---

PRODUCTS = [
    {"id": "P-1001", "name": "Industrial Servo Motor", "category": "Motors", "specs": "5HP, 3-phase"},
    {"id": "P-1002", "name": "Hydraulic Press", "category": "Presses", "specs": "100-ton capacity"},
    {"id": "P-1003", "name": "PLC Controller", "category": "Controls", "specs": "32 I/O, Ethernet"},
    {"id": "P-1004", "name": "Conveyor Belt System", "category": "Material Handling", "specs": "10m length"},
    {"id": "P-1005", "name": "Safety Light Curtain", "category": "Safety", "specs": "Type 4, 1800mm"},
]

SAMPLE_DOCS = [
    "Industrial servo motors provide precise positioning control for automated manufacturing. They offer high torque at low speeds and are ideal for CNC machines and robotic arms.",
    "Hydraulic presses use fluid pressure to generate force for forming, stamping, and assembly operations. 100-ton models are commonly used in metal fabrication.",
    "PLC (Programmable Logic Controller) systems control industrial automation processes. They support ladder logic programming and can interface with sensors, motors, and HMI displays.",
    "Conveyor belt systems transport materials across production lines. Belt speed and load capacity must be matched to application requirements.",
    "Safety light curtains create invisible protective barriers. When breached, they trigger emergency stops to protect operators from hazardous machinery.",
]

chroma_collection = None


# --- Agent Tools ---


@function_tool
async def search_catalog(query: str) -> str:
    """Search the product catalog for items matching the query."""
    query_lower = query.lower()
    matches = [p for p in PRODUCTS if query_lower in p["name"].lower() or query_lower in p["category"].lower()]

    if not matches:
        return "No products found matching your query."

    results = []
    for p in matches[:3]:
        results.append(f"{p['id']}: {p['name']} ({p['category']}) - {p['specs']}")

    return "\n".join(results)


@function_tool
async def retrieve_docs(query: str) -> str:
    """Retrieve relevant documentation from the knowledge base."""
    global chroma_collection

    if chroma_collection is None:
        return "Knowledge base not initialized."

    results = chroma_collection.query(query_texts=[query], n_results=3)

    if not results["documents"] or not results["documents"][0]:
        return "No relevant documentation found."

    return "\n\n".join(results["documents"][0])


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
    """Process a question using the AI agent with RAG tools."""
    result = await Runner.run(
        Agent(
            name="product_assistant",
            instructions=(
                "You are a helpful product specialist for industrial manufacturing equipment. "
                "Use the search_catalog tool to find specific products and the retrieve_docs tool "
                "to find technical information. Provide clear, concise answers based on the retrieved information."
            ),
            tools=[search_catalog, retrieve_docs],
        ),
        input=request.question,
    )

    return ChatResponse(answer=result.final_output)


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok"}


# --- Flyte App Environment ---

app_env = FastAPIAppEnvironment(
    name="product-chat",
    app=app,
    description="RAG-based product chat assistant for industrial equipment",
    image=flyte.Image.from_debian_base(python_version=(3, 12)).with_pip_packages(
        "fastapi",
        "uvicorn",
        "openai-agents",
        "chromadb",
    ),
    resources=flyte.Resources(cpu=1, memory="1Gi"),
    secrets=[flyte.Secret(key="openai-api-key", as_env_var="OPENAI_API_KEY")],
    requires_auth=False,
    include=["ui.py"],
)


if __name__ == "__main__":
    flyte.init_from_config()
    deployments = flyte.deploy(app_env)
    d = deployments[0]
    print(f"\nDeployed Product Chat App:")
    print(f"URL: {d.url}")
    print(f"\nTry it:")
    print(f"  Browser: {d.url}/")
    print(f'  API:     curl -X POST {d.url}/chat -H "Content-Type: application/json" -d \'{{"question": "What motors do you have?"}}\'')
