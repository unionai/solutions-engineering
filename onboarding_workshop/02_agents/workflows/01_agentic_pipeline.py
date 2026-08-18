"""
Part 1: A durable, parallel research pipeline on Union
======================================================
The standalone version of the notebook's Step 4 pipeline. A driver task plans
sub-topics with an LLM, fans out one warm worker per topic in parallel, and
synthesizes a grounded recommendation, publishing an HTML report.

What each Flyte 2.0 feature buys the pipeline:

- @flyte.trace:        `llm`, `plan`, and `synthesize` become durable, observable
                       spans; inputs and outputs are persisted and shown on the run page.
- Fan-out:             `asyncio.gather` inside `flyte.group` runs one worker per
                       sub-topic in parallel, each its own action.
- Reusable containers: warm worker replicas skip pod cold-starts, which dominate
                       latency once every task is an LLM call.
- Reports & secrets:   the driver publishes an HTML report; the API key is injected
                       as an env var (litellm reads `ANTHROPIC_API_KEY` itself).

The model picks the topics at run time, so the fan-out width is dynamic.

Run remote:  flyte run 01_agentic_pipeline.py research --question "Should we expand into the EU market?"
"""

import asyncio
import json
from pathlib import Path

import flyte
import flyte.report
from litellm import acompletion
from pydantic import BaseModel

MODEL = "claude-haiku-4-5"  # litellm alias -> Anthropic

# One image for the whole pipeline: litellm for the LLM calls, unionai-reuse for
# the warm worker containers.
image = flyte.Image.from_debian_base().with_pip_packages("litellm", "unionai-reuse>=0.1.9")

# Secrets: the key arrives as an env var; litellm reads ANTHROPIC_API_KEY itself.
anthropic_secret = flyte.Secret(key="ANTHROPIC_API_KEY", as_env_var="ANTHROPIC_API_KEY")

# Reusable workers: warm replicas skip pod cold-starts on every fan-out call.
worker_env = flyte.TaskEnvironment(
    name="researcher",
    image=image,
    secrets=[anthropic_secret],
    resources=flyte.Resources(cpu=1, memory="1Gi"),
    reusable=flyte.ReusePolicy(replicas=(1, 2), idle_ttl=120, concurrency=4, scaledown_ttl=120),
)

# The driver fans out to workers, so it depends on them.
driver_env = flyte.TaskEnvironment(
    name="research_driver",
    image=image,
    secrets=[anthropic_secret],
    resources=flyte.Resources(cpu=1, memory="500Mi"),
    depends_on=[worker_env],
)


class ResearchResult(BaseModel):
    question: str
    topics: list[str]
    answer: str


# A single traced LLM helper. `@flyte.trace` (no parentheses) makes each call a
# durable, observable span that runs in-container, not its own pod.
@flyte.trace
async def llm(prompt: str) -> str:
    r = await acompletion(model=MODEL, messages=[{"role": "user", "content": prompt}])
    return r.choices[0].message.content


@flyte.trace
async def plan(question: str, n: int) -> list[str]:
    reply = await llm(
        f"List exactly {n} short research sub-topics for: {question}. "
        "Reply as a JSON array of strings, nothing else."
    )
    return json.loads(reply[reply.index("["): reply.rindex("]") + 1])[:n]


@flyte.trace
async def synthesize(question: str, topics: list[str], findings: list[str]) -> str:
    notes = "\n".join(f"- {t}: {f}" for t, f in zip(topics, findings))
    return await llm(
        f"Question: {question}\nFindings:\n{notes}\n\n"
        "Write a 4-sentence recommendation grounded in the findings."
    )


@worker_env.task
async def research_topic(topic: str) -> str:
    return await llm(f"In 3 sentences, give the key facts a decision-maker needs on: {topic}")


@driver_env.task(report=True)
async def research(question: str = "Should we expand into the EU market?", n: int = 3) -> ResearchResult:
    topics = await plan(question, n)                    # dynamic: the model picks the topics
    print("planned topics:", topics)

    with flyte.group("fan-out"):                        # one warm worker per topic, in parallel
        findings = await asyncio.gather(*[research_topic(t) for t in topics])

    answer = await synthesize(question, topics, findings)
    await flyte.report.replace.aio(
        f"<h2>{question}</h2>"
        + "".join(f"<h3>{t}</h3><p>{f}</p>" for t, f in zip(topics, findings))
        + f"<hr><h3>Recommendation</h3><p>{answer}</p>"
    )
    await flyte.report.flush.aio()
    return ResearchResult(question=question, topics=topics, answer=answer)


if __name__ == "__main__":
    flyte.init_from_config(
        root_dir=Path(__file__).parent,
        path_or_config=Path(__file__).parent / ".flyte" / "config.yaml",
    )
    run = flyte.run(research, question="Should we expand into the EU market?", n=3)
    print(f"Run URL: {run.url}")
    run.wait()
    print(run.outputs())
