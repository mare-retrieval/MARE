# MARE 0.4.6

MARE 0.4.6 is the Agentic Evidence Planning release.

The market is moving from single-shot RAG toward agentic, multi-step retrieval that can prove what it found, decide when evidence is insufficient, and keep an audit trail of follow-up searches. This release moves MARE in that direction while keeping the base package lightweight and deterministic.

## Highlights

- Added `research_plan` to Evidence Brief payloads.
- Research plans include:
  - a status such as `ready`, `needs_evidence`, `needs_stronger_support`, `needs_source_check`, or `needs_conflict_check`
  - a short rationale
  - concrete next retrieval steps with action names, queries, and reasons
- Added attempt-level audit trails to workflow evidence rescue.
- Evidence rescue now records each alternate query, support assessment, result count, top citation, top score, and whether that attempt improved support.
- Added top-level `agent_contract` payloads for Python, MCP query tools, and workflow JSON.
- Agent contracts include `may_answer`, `recommended_action`, `stop_reasons`, support/source/research statuses, and the research plan.
- Added `mare workflow --task contract` for a compact terminal action-contract view.
- Added `:contract` to `mare chat`.
- Surfaced research-plan status and steps in `mare workflow --task brief`.
- Surfaced agent actions and research-plan status in workflow review/answer views and `mare chat`.
- Surfaced research-plan status and steps in the Streamlit playground Evidence Brief panel.
- Added an Agent Contract panel to the Streamlit playground.

## Why It Matters

MARE already explains the trust shape of retrieved evidence. The next useful step is telling a human or agent what to do with that trust signal.

With research plans and audited rescue attempts, agent clients can now:

- answer when evidence is ready
- retrieve stronger support when evidence is weak
- compare sources when coverage is narrow
- resolve conflict signals before acting
- inspect exactly which rescue searches were attempted
- read one compact action contract before deciding whether to answer or continue retrieval

That keeps MARE focused on grounded document work rather than generic chat behavior.
