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
        "anthropic",
        "flyteplugins-hitl>=2.0.0",
        "fastapi",
        "uvicorn",
        "python-multipart",
        "unionai-reuse>=0.1.9",
    ),
    secrets=[flyte.Secret(key="ANTHROPIC_API_KEY", as_env_var="ANTHROPIC_API_KEY")],
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
    """Research the customer's industry and needs using Anthropic Claude."""
    result = await run_research(request)
    return result.model_dump()


@env.task()
async def pricing_agent(request: QuoteRequest) -> dict:
    """Generate pricing recommendations using Anthropic Claude."""
    result = await run_pricing(request)
    return result.model_dump()


@env.task(report=True)
async def draft_proposal(request: QuoteRequest, research: dict, pricing: dict) -> dict:
    """Draft a complete proposal document using Anthropic Claude."""
    from models import ResearchResult, PricingResult

    result = await run_proposal(
        request,
        ResearchResult(**research),
        PricingResult(**pricing),
    )

    proposal_html = result.proposal_text.replace("\n", "<br>")
    research_html = result.research_summary.replace("\n", "<br>")
    pricing_html = result.pricing_summary.replace("\n", "<br>")
    report = (
        '<div style="font-family: -apple-system, BlinkMacSystemFont, sans-serif; '
        'max-width: 800px; margin: 0 auto; padding: 24px; color: #1a1a1a;">'
        # Header
        '<div style="background: linear-gradient(135deg, #1e3a5f, #2d6a9f); '
        'border-radius: 12px; padding: 32px; margin-bottom: 24px; color: white;">'
        f'<h1 style="margin: 0 0 8px 0; font-size: 28px;">Proposal for {result.customer_name}</h1>'
        f'<div style="font-size: 36px; font-weight: 700; margin-top: 12px;">${result.final_quote:,.2f}</div>'
        '<div style="opacity: 0.8; margin-top: 4px;">Estimated Quote</div>'
        '</div>'
        # Research card
        '<div style="background: #f8f9fa; border-radius: 10px; padding: 24px; margin-bottom: 16px; '
        'border-left: 4px solid #2d6a9f;">'
        '<h3 style="margin: 0 0 12px 0; color: #2d6a9f;">Research Summary</h3>'
        f'<div style="line-height: 1.6;">{research_html}</div>'
        '</div>'
        # Pricing card
        '<div style="background: #f8f9fa; border-radius: 10px; padding: 24px; margin-bottom: 16px; '
        'border-left: 4px solid #28a745;">'
        '<h3 style="margin: 0 0 12px 0; color: #28a745;">Pricing Summary</h3>'
        f'<div style="line-height: 1.6;">{pricing_html}</div>'
        '</div>'
        # Full proposal
        '<div style="background: white; border: 1px solid #e0e0e0; border-radius: 10px; '
        'padding: 24px; margin-bottom: 16px;">'
        '<h3 style="margin: 0 0 12px 0; color: #1a1a1a;">Full Proposal</h3>'
        f'<div style="line-height: 1.8;">{proposal_html}</div>'
        '</div>'
        '</div>'
    )
    await flyte.report.replace.aio(report)
    await flyte.report.flush.aio()

    return result.model_dump()


@env.task(report=True)
async def human_review(proposal: dict) -> bool:
    """Human-in-the-loop approval gate. Pauses workflow for review."""
    p = Proposal(**proposal)

    summary = p.proposal_text[:500].replace("\n", "<br>")
    prompt = (
        f"<h2>Proposal Review</h2>"
        f"<b>Customer:</b> {p.customer_name}<br>"
        f"<b>Final Quote:</b> ${p.final_quote:,.2f}<br><br>"
        f"<b>Proposal Summary</b><br>{summary}...<br><br>"
        f"<b>Do you approve this proposal?</b>"
    )

    # hitl.new_event.aio() internally calls Event.create.aio() which has a
    # syncify + classmethod bug (cls not bound). Call the raw async fn directly.
    raw_create = hitl.Event.create.__func__.fn
    event = await raw_create(
        hitl.Event,
        name="approval",
        data_type=bool,
        scope="run",
        prompt=prompt,
    )

    # event.wait.aio() runs in syncify's background loop which interferes
    # with Flyte's async runtime. Call the raw async fn directly instead.
    approved = await event.wait.fn()
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
