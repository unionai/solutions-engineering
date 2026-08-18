"""
Part 2: A durable agentic pipeline on Union
============================================
A research pipeline that plans sub-topics, fans out a durable **agent** per
topic in parallel, and synthesizes a final answer. It is self-contained: the
agent researches against a small in-memory knowledge base, so no external search
API (or key) is needed, only the `ANTHROPIC_API_KEY` secret.

What each Flyte 2.0 feature buys an agentic system (the story of the notebook):

- `@flyte.trace`:        every LLM call (`plan`, `synthesize`) is a durable,
                         observable span, inputs/outputs persisted, visible on
                         the run page. Crash after `plan`? The plan is not re-run.
- `flyte.ai.agents.Agent`: the batteries-included tool-use loop. Tools are plain
                         Python functions; the harness drives the reason→act→observe
                         loop for you (the notebook shows the hand-rolled version).
- Fan-out:               `asyncio.gather` inside `flyte.group` runs one agent per
                         sub-topic in parallel, each its own action on the run page.
- Reusable containers:   warm worker replicas skip pod cold-starts, which dominate
                         latency once every task is an LLM call.
- Reports & secrets:     the driver publishes an HTML report; the API key is
                         injected as an env var, never hard-coded.

Run remote:  flyte run 02_agentic_pipeline.py research --question "Should we expand into the EU market?"
"""

import asyncio
import json
from pathlib import Path

import flyte
import flyte.report
from flyte.ai.agents import Agent
from litellm import acompletion
from pydantic import BaseModel

MODEL = "claude-haiku-4-5"  # cheap, fast; litellm routes it to Anthropic

# The agent harness calls litellm; the driver's own LLM steps call litellm too,
# one path for the whole pipeline. Reuse needs unionai-reuse.
image = flyte.Image.from_debian_base().with_pip_packages("litellm", "unionai-reuse>=0.1.9")

# Secrets: the key arrives as an env var; litellm reads ANTHROPIC_API_KEY itself.
anthropic_secret = flyte.Secret(key="ANTHROPIC_API_KEY", as_env_var="ANTHROPIC_API_KEY")

# Workers run agents concurrently in warm containers: async tasks only.
worker_env = flyte.TaskEnvironment(
    name="research_worker",
    image=image,
    resources=flyte.Resources(cpu=1, memory="1Gi"),
    secrets=[anthropic_secret],
    reusable=flyte.ReusePolicy(replicas=(1, 2), idle_ttl=120, concurrency=4, scaledown_ttl=120),
)

# The driver plans, fans out to workers, and synthesizes, so it declares depends_on.
driver_env = flyte.TaskEnvironment(
    name="research_driver",
    image=image,
    resources=flyte.Resources(cpu=1, memory="1Gi"),
    secrets=[anthropic_secret],
    depends_on=[worker_env],
)


class ResearchResult(BaseModel):
    question: str
    topics: list[str]
    findings: list[str]
    answer: str


# --- The agent's tool + knowledge base (self-contained, no external API) -----
# A tiny "internal wiki". The agent decides which topics to look up, that
# decision is what makes it an agent rather than a fixed prompt chain.
KB = {
    "market size": "The EU SaaS market is ~$95B and growing ~12% YoY. Germany, France and the Nordics lead adoption.",
    "revenue": "FY24 revenue was $12.4M, up 38% YoY. 22% of inbound demo requests already come from EU domains.",
    "competition": "Two incumbents hold ~40% EU share; both lack a self-serve tier, which is our current wedge.",
    "compliance": "Selling into the EU requires GDPR data-residency and, for public-sector deals, EU-hosted infra.",
    "team": "45 employees, all US-based. No German/French speakers in sales; one engineer in Lisbon.",
    "pricing": "Current pricing is USD-only. EU buyers expect EUR invoicing and net-30 terms.",
}


async def lookup(topic: str) -> str:
    """Look up factual notes about a topic from the internal knowledge base.

    Args:
        topic: a short topic phrase such as 'market size', 'revenue',
            'competition', 'compliance', 'team', or 'pricing'.
    """
    # Fuzzy-match so the agent doesn't have to guess the exact key.
    topic_l = topic.lower()
    for key, note in KB.items():
        if key in topic_l or topic_l in key:
            return note
    return f"No internal notes on '{topic}'. Known topics: {', '.join(KB)}."


# The batteries-included agent: a reason→act→observe loop with tool calling.
# `tools=[lookup]`: the harness reads the signature + docstring to build the
# tool schema (see the notebook for the hand-rolled equivalent with @flyte.trace).
analyst = Agent(
    name="market-analyst",
    model=MODEL,
    instructions=(
        "You are a market analyst. Answer the user's focus area using ONLY the "
        "lookup tool for facts, call it for each thing you need, then give a "
        "concise, evidence-based finding. Do not invent numbers."
    ),
    tools=[lookup],
    max_turns=6,
)


# --- Durable LLM steps (no tools): traced, so each is a persisted span -------


@flyte.trace
async def plan(question: str, n: int) -> list[str]:
    """Split the question into sub-topics to research in parallel."""
    r = await acompletion(
        model=MODEL,
        messages=[{
            "role": "user",
            "content": (
                f"Break this question into exactly {n} distinct research sub-topics. "
                f"Return ONLY a JSON array of short strings.\n\nQuestion: {question}"
            ),
        }],
    )
    raw = r.choices[0].message.content.strip().removeprefix("```json").removeprefix("```").removesuffix("```")
    try:
        topics = json.loads(raw)
        if isinstance(topics, list) and topics:
            return [str(t) for t in topics[:n]]
    except json.JSONDecodeError:
        pass
    # Fallback: one topic per non-empty line.
    return [line.strip("-* ") for line in raw.splitlines() if line.strip()][:n]


@flyte.trace
async def synthesize(question: str, topics: list[str], findings: list[str]) -> str:
    """Combine the per-topic findings into one grounded answer."""
    sections = "\n\n".join(f"## {t}\n{f}" for t, f in zip(topics, findings))
    r = await acompletion(
        model=MODEL,
        messages=[{
            "role": "user",
            "content": (
                f"Question: {question}\n\nResearch findings:\n\n{sections}\n\n"
                "Write a concise recommendation (max 6 sentences) grounded in the findings above."
            ),
        }],
    )
    return r.choices[0].message.content


# --- Tasks ------------------------------------------------------------------


@worker_env.task
async def research_topic(topic: str, question: str) -> str:
    """Run the agent on one sub-topic. Each call is its own action on the run page.

    The agent's internal tool calls run inside this container; `agent.run.aio`
    drives the loop until the model stops asking for tools.
    """
    result = await analyst.run.aio(
        f"Question: {question}\nYour focus area: {topic}\n"
        "Look up what you need and report your finding."
    )
    return result.summary or result.error or f"(no finding for {topic})"


@driver_env.task(report=True)
async def research(question: str = "Should we expand into the EU market?", num_topics: int = 3) -> ResearchResult:
    # 1. Plan, a durable, traced LLM step.
    topics = await plan(question, num_topics)
    print(f"planned topics: {topics}")

    # 2. Fan-out, one agent per sub-topic, in parallel, each its own action.
    with flyte.group("research-fanout"):
        findings = list(await asyncio.gather(*[research_topic(t, question) for t in topics]))

    # 3. Synthesize, another durable, traced LLM step.
    answer = await synthesize(question, topics, findings)
    print(f"answer: {answer}")

    # 4. Report, publish the trail on the run page.
    body = "".join(f"<h3>{t}</h3><p>{f}</p>" for t, f in zip(topics, findings))
    await flyte.report.replace.aio(
        f"<h2>Research: {question}</h2>{body}<hr><h3>Recommendation</h3><p>{answer}</p>"
    )
    await flyte.report.flush.aio()

    return ResearchResult(question=question, topics=topics, findings=findings, answer=answer)


if __name__ == "__main__":
    flyte.init_from_config(
        root_dir=Path(__file__).parent,
        path_or_config=Path(__file__).parent / ".flyte" / "config.yaml",
    )
    run = flyte.run(research)
    print(f"Run URL: {run.url}")
    run.wait()
