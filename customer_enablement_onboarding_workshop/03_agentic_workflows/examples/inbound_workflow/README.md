# Exercise 3: Multi-Agent Quote Workflow with Human-in-the-Loop

## What You'll Learn

- Orchestrating multiple AI agents in a single workflow
- Using `@flyte.trace` for fine-grained observability
- Human-in-the-loop (HITL) approval gates with `flyteplugins-hitl`
- Combining parallel and sequential execution patterns
- Structured I/O with dataclasses

## Scenario

A customer submits a quote request. Your system needs to:

1. **Research** the customer's industry and needs (research agent)
2. **Generate pricing** based on the research (pricing agent)
3. **Draft a proposal** combining research + pricing
4. **Pause for human review** — a sales team member approves or rejects
5. **Return the outcome**

Steps 1 and 2 run in parallel (they're independent). Step 3 depends on both. Step 4 is a human gate.

## Workflow Design

```
quote_workflow (driver)
│
├── research_agent(request)  ──┐
│                               ├── parallel (flyte.group)
├── pricing_agent(request)  ───┘
│
▼
draft_proposal(request, research, pricing)
│
▼
human_review(proposal)  ← HITL: pauses until human responds
│
▼
return final status
```

### Tasks

| Task | What it does |
|------|--------------|
| `research_agent` | Uses OpenAI Agent to research the customer's domain |
| `pricing_agent` | Uses OpenAI Agent to generate pricing recommendations |
| `draft_proposal` | Synthesizes research + pricing into a proposal document |
| `human_review` | Creates a HITL event, pauses workflow until human approves/rejects |
| `quote_workflow` | Orchestrates the full pipeline |

### Union Features Highlighted

| Feature | How it's used |
|---------|---------------|
| **HITL** | `flyteplugins-hitl` creates an approval gate with a web form |
| **`@flyte.trace`** | Traces LLM calls and tool invocations for observability |
| **Parallel agents** | Research + pricing agents run simultaneously |
| **`report=True`** | Renders rich HTML reports in the Union UI |
| **Structured I/O** | Dataclasses define clear contracts between tasks |

## How to Run

```bash
cd inbound_workflow
python workflow.py
```

Open the run URL. When the workflow reaches the `human_review` step, you'll see a link to a web form where you can approve or reject the proposal.

## Key Concepts

### Human-in-the-Loop

The HITL plugin deploys a lightweight FastAPI app that renders a form in the Union UI. The workflow pauses until someone submits a response:

```python
import flyteplugins.hitl as hitl

event = await hitl.new_event.aio(
    "approval",
    data_type=bool,
    prompt="Approve this proposal?",
)
approved = await event.wait.aio()  # workflow pauses here
```

Your task environment must declare `depends_on=[hitl.env]` to use HITL.

### @flyte.trace

Traces make inner function calls visible in the Union UI dashboard. Each traced call appears as a span with captured inputs and outputs:

```python
@flyte.trace
async def call_llm(prompt: str) -> str:
    # This call is now visible in the Union UI
    ...
```

### Parallel Agent Execution

Independent agents run in parallel using `asyncio.gather`:

```python
with flyte.group("agents"):
    research, pricing = await asyncio.gather(
        research_agent(request),
        pricing_agent(request),
    )
```
