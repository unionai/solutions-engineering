# Session 3 — Agentic AI on Union

**Format:** live session (~90 min), recorded; recording + slides + this repo handed over for
self-paced use.  
**Audience:** users building LLM/agent applications. Assumes session 1 (core concepts).

This stream covers **agentic workflows and integrating Union workflows with apps to host agents**
on the platform.

## Agenda

| # | Section | Contents |
|---|---------|----------|
| 1 | Why run agents on Union | durable execution, observability (`@flyte.trace`), retries, secrets for API keys, resource isolation on shared clusters, agent harness, sandboxing |
| 2 | Batch LLM processing | fan-out document processing with an LLM, structured I/O with dataclasses |
| 3 | Multi-agent orchestration | parallel + sequential agent steps, human-in-the-loop approval gates |
| 4 | Hosting agents as apps | real-time RAG chat app with `FastAPIAppEnvironment`; `flyte.run` vs `flyte.deploy`; workflow + app integration |
| 5 | Agent Frameworks on Union | Running LangGraph agents with full Union support |
| 6 | (Optional) MCP | building/hosting an MCP server on Union |
| 7 | Q&A | |

## Code examples (in `examples/`)

The three `agentic_onboarding_workshop` exercises are a ready-made arc for this session:

| Example | Source | Covers |
|---------|--------|--------|
| `batch_process/` | solutions-engineering/agentic_onboarding_workshop (Exercise 1) | batch LLM document pipeline: fan-out with `flyte.group`, multiple envs with `depends_on` |
| `chat_app/` | solutions-engineering/agentic_onboarding_workshop (Exercise 2) | real-time RAG chat app: `FastAPIAppEnvironment`, OpenAI Agents SDK with tools, run vs deploy |
| `inbound_workflow/` | solutions-engineering/agentic_onboarding_workshop (Exercise 3) | multi-agent quote workflow: `@flyte.trace`, human-in-the-loop (`flyteplugins-hitl`), parallel + sequential agents |
| `langgraph-react-agent/` | workshops/tutorials/starter-examples | LangGraph `create_react_agent`, `@flyte.trace`, tools |
| `mcp/` | workshops/tutorials | MCP server hosted on Union (optional deep dive) |

Further material to reference in the handout (not copied):
`workshops/tutorials/multi-agent-workflows` (six agent-pattern notebooks: ReAct, reflection,
planner, manager, sequential, debate), `claude_agent_research`, `langgraph_agent_research`,
`autoresearch`.

## Slides

- [Reserach AI Agents](https://docs.google.com/presentation/d/1nrqtsgEcIXB58GbnLf2SMijsSYRFwGaMXwuyfcDm8WM/edit?usp=sharing)
- [Planner AI Agents](https://docs.google.com/presentation/d/1pj6PvRHEL-N32_uEK4SJ93jB0HJv3GT6-jdWYYYwaOg/edit?usp=sharing)
