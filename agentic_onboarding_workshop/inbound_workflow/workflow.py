"""
Multi-Agent Quote Workflow with Human-in-the-Loop

A workshop exercise demonstrating:
- Parallel AI agent execution
- @flyte.trace for observability
- Human-in-the-loop approval gates
- Structured I/O with Pydantic models
"""

import asyncio

import flyte
import flyteplugins.hitl as hitl

from models import QuoteRequest, Proposal
from agents import run_research, run_pricing, run_proposal

env = flyte.TaskEnvironment(
    name="quote-workflow",
    resources=flyte.Resources(cpu=2, memory="4Gi"),
    image=flyte.Image.from_debian_base().with_pip_packages(
        "openai-agents>=0.2.4",
        "flyteplugins-hitl>=2.0.0",
        "fastapi",
        "uvicorn",
        "python-multipart",
        "unionai-reuse>=0.1.9",
    ),
    secrets=[flyte.Secret(key="openai-api-key", as_env_var="OPENAI_API_KEY")],
    depends_on=[hitl.env],
    reusable=flyte.ReusePolicy(
        replicas=(1, 2),
        idle_ttl=60,
        concurrency=5,
        scaledown_ttl=60,
    ),
)


@env.task()
async def research_agent(request: QuoteRequest) -> dict:
    """Research the customer's industry and needs using OpenAI Agent."""
    result = await run_research(request)
    return result.model_dump()


@env.task()
async def pricing_agent(request: QuoteRequest) -> dict:
    """Generate pricing recommendations using OpenAI Agent."""
    result = await run_pricing(request)
    return result.model_dump()


@env.task()
async def draft_proposal(request: QuoteRequest, research: dict, pricing: dict) -> dict:
    """Draft a complete proposal document using OpenAI Agent."""
    from models import ResearchResult, PricingResult

    result = await run_proposal(
        request,
        ResearchResult(**research),
        PricingResult(**pricing),
    )
    return result.model_dump()


@env.task(report=True)
async def human_review(proposal: dict) -> bool:
    """Human-in-the-loop approval gate. Pauses workflow for review."""
    p = Proposal(**proposal)

    prompt = f"""
    # Proposal Review

    **Customer:** {p.customer_name}
    **Final Quote:** ${p.final_quote:,.2f}

    ## Proposal Summary
    {p.proposal_text[:500]}...

    **Do you approve this proposal?**
    """

    event = await hitl.new_event.aio(
        "approval",
        data_type=bool,
        prompt=prompt,
    )

    approved = await event.wait.aio()
    return approved


@env.task()
async def quote_workflow(request: QuoteRequest) -> str:
    """
    Main workflow orchestrating the quote generation process.

    Flow:
    1. Run research and pricing agents in parallel
    2. Draft proposal combining both results
    3. Pause for human review
    4. Return final status
    """
    with flyte.group("agents"):
        research, pricing = await asyncio.gather(
            research_agent(request),
            pricing_agent(request),
        )

    proposal = await draft_proposal(request, research, pricing)

    approved = await human_review(proposal)

    p = Proposal(**proposal)
    if approved:
        return f"Proposal approved for {p.customer_name}. Quote: ${p.final_quote:,.2f}"
    else:
        return f"Proposal rejected for {p.customer_name}. Requires revision."


if __name__ == "__main__":
    flyte.init_from_config()

    sample_request = QuoteRequest(
        customer_name="Acme Corporation",
        industry="Manufacturing",
        requirements="Cloud-native data orchestration platform for 50 data scientists",
        budget_range="$50,000-$100,000",
    )

    run = flyte.run(quote_workflow, sample_request)
    print(f"Run URL: {run.url}")
