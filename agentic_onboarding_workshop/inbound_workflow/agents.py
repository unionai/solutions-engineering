"""
Agent definitions for the quote workflow.

Each agent wraps an OpenAI Agent call behind @flyte.trace for observability.
"""

from agents import Agent, Runner

import flyte

from models import QuoteRequest, ResearchResult, PricingResult, Proposal


@flyte.trace
async def call_openai_agent(instructions: str, input_prompt: str) -> str:
    """Helper to call OpenAI Agent. Traced for observability."""
    result = await Runner.run(
        Agent(
            name="assistant",
            instructions=instructions,
        ),
        input=input_prompt,
    )
    return result.final_output


async def run_research(request: QuoteRequest) -> ResearchResult:
    """Research the customer's industry and needs."""
    instructions = (
        "You are a research analyst. Provide industry insights, "
        "competitor landscape analysis, and recommendations based on customer requirements."
    )

    input_prompt = f"""
    Customer: {request.customer_name}
    Industry: {request.industry}
    Requirements: {request.requirements}
    Budget Range: {request.budget_range}

    Provide a structured research report covering:
    1. Industry overview
    2. Competitor landscape
    3. Recommendations for this customer
    """

    report = await call_openai_agent(instructions, input_prompt)

    return ResearchResult(
        industry_overview=f"Industry analysis for {request.industry}",
        competitor_landscape="Competitive landscape summary",
        recommendations=report,
    )


async def run_pricing(request: QuoteRequest) -> PricingResult:
    """Generate pricing recommendations."""
    instructions = (
        "You are a pricing specialist. Generate a fair quote "
        "based on customer budget, requirements, and industry standards."
    )

    input_prompt = f"""
    Customer: {request.customer_name}
    Industry: {request.industry}
    Requirements: {request.requirements}
    Budget Range: {request.budget_range}

    Provide:
    1. Base price recommendation
    2. Any adjustments (discounts, add-ons)
    3. Final quote amount
    4. Justification for the pricing
    """

    pricing_text = await call_openai_agent(instructions, input_prompt)

    budget_parts = request.budget_range.replace("$", "").replace(",", "").split("-")
    if len(budget_parts) == 2:
        base_price = (float(budget_parts[0]) + float(budget_parts[1])) / 2
    else:
        base_price = 50000.0

    final_quote = base_price * 0.95

    return PricingResult(
        base_price=base_price,
        adjustments="5% early commitment discount",
        final_quote=final_quote,
        justification=pricing_text,
    )


async def run_proposal(
    request: QuoteRequest,
    research: ResearchResult,
    pricing: PricingResult,
) -> Proposal:
    """Draft a complete proposal document."""
    instructions = (
        "You are a proposal writer. Create a compelling business "
        "proposal that combines research insights and pricing into a cohesive document."
    )

    input_prompt = f"""
    Customer: {request.customer_name}
    Industry: {request.industry}

    Research Summary:
    {research.recommendations}

    Pricing Summary:
    - Base Price: ${pricing.base_price:,.2f}
    - Adjustments: {pricing.adjustments}
    - Final Quote: ${pricing.final_quote:,.2f}
    - Justification: {pricing.justification}

    Draft a professional proposal document (2-3 paragraphs).
    """

    proposal_text = await call_openai_agent(instructions, input_prompt)

    return Proposal(
        customer_name=request.customer_name,
        research_summary=research.recommendations,
        pricing_summary=f"${pricing.final_quote:,.2f} ({pricing.adjustments})",
        proposal_text=proposal_text,
        final_quote=pricing.final_quote,
    )
