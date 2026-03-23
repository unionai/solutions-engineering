from pydantic import BaseModel


class QuoteRequest(BaseModel):
    customer_name: str
    industry: str
    requirements: str
    budget_range: str


class ResearchResult(BaseModel):
    industry_overview: str
    competitor_landscape: str
    recommendations: str


class PricingResult(BaseModel):
    base_price: float
    adjustments: str
    final_quote: float
    justification: str


class Proposal(BaseModel):
    customer_name: str
    research_summary: str
    pricing_summary: str
    proposal_text: str
    final_quote: float
