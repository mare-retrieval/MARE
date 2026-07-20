# Agent Integrations

MARE can act as the document evidence layer for OpenClaw, Hermes Agent, and other tool-using agents.

The goal is simple:

```text
agent question -> MARE -> cited evidence + support strength + gaps -> agent decides what to do next
```

Use MARE when an agent needs to read manuals, SOPs, policies, onboarding packets, contracts, support docs, or local knowledge folders without guessing.

## Why This Fits OpenClaw and Hermes

OpenClaw and Hermes-style agents are popular because they can run tools, keep context, and complete multi-step work. That also means they need better evidence boundaries before they act.

MARE gives those agents:

- exact citations
- snippets
- PDF page/highlight proof when available
- source coverage
- support strength
- conflict hints
- evidence gaps
- next evidence-seeking questions
- research plans for the next retrieval move
- an `agent_contract` with the recommended action and stop reasons
- JSON payloads that are easy for agents to inspect

## Option 1: Shell Tool

Use this when your agent can run commands.

```bash
mare workflow --folder ./docs --query "what should I do before onboarding is complete?" --task brief --format json
```

For a compact human-readable action contract:

```bash
mare workflow --folder ./docs --query "what should I do before onboarding is complete?" --task contract
```

Recommended agent tool description:

```text
Use MARE when you need grounded evidence from local documents. Pass a concise question and the document folder. Read agent_contract before acting. If may_answer is false, follow recommended_action or show the user the citations instead of acting autonomously. Use evidence_brief for detailed support, source coverage, conflict hints, gaps, and proof assets.
```

Recommended policy:

```text
Never treat a MARE result as sufficient if support.status is "weak" or "none".
Never act on operational, legal, safety, financial, or account-changing instructions unless the Evidence Brief has relevant citations and no unresolved conflict hints.
Prefer quoting citation + snippet back to the user before taking external action.
```

## Option 2: MCP Tool

Use this when your agent platform supports MCP.

Start MARE:

```bash
mare mcp
```

Typical MCP-style tools include:

- `ingest_document`
- `query_document`
- `ingest_pdf_url`
- `query_pdf_url`
- `query_corpus`
- `query_corpora`

Prefer MCP when you want structured tool calls instead of shell parsing.

## Option 3: Python Tool Wrapper

Use this when building a custom agent runtime.

```python
from mare import load_document
from mare.integrations import hits_to_evidence_payload

app = load_document("docs/policy.md", reuse=True)
query = "what does onboarding require before completion?"
hits = app.retrieve(query, top_k=3)
payload = hits_to_evidence_payload(query, hits)

brief = payload["evidence_brief"]
contract = payload["agent_contract"]
print(contract["recommended_action"])
print(brief["support"]["status"])
print(brief["source_diversity"]["label"])
print(brief["evidence_gaps"])
```

## OpenClaw Recipe

Use MARE as a local command skill/tool.

Suggested tool name:

```text
mare_document_evidence
```

Command template:

```bash
mare workflow --folder "{{folder}}" --query "{{query}}" --task brief --format json --no-history
```

Suggested skill instructions:

```text
When a task depends on a local document, manual, policy, SOP, contract, or support note, call mare_document_evidence before answering. Use the returned agent_contract first. If may_answer is false, follow recommended_action or ask the user. Use evidence_brief for citations, gaps, source coverage, and conflict details. If conflict_hints are present, summarize the conflict and ask the user before taking action. If source coverage is single-source, mention that the answer is based on one source.
```

Good OpenClaw use cases:

- read SOPs before performing an automation
- inspect support docs before replying to a customer
- check local policy before scheduling or account changes
- cite manuals before giving setup instructions

## Hermes Agent Recipe

Use MARE as a persistent evidence skill for document work.

Suggested skill name:

```text
DocumentEvidenceBrief
```

Skill behavior:

```text
Input: folder path and user question.
Run MARE with --task brief --format json.
Return the agent_contract, evidence_brief, top citation, top snippet, and research_plan.
If agent_contract.recommended_action is retrieve_stronger_support, run the first research_plan step before finalizing.
If conflict_hints exist, present the conflict to the user and avoid autonomous action.
```

Command template:

```bash
mare workflow --folder "{{folder}}" --query "{{question}}" --task brief --format json --no-history
```

Good Hermes use cases:

- self-improving workflows that learn which document folders answer which tasks
- policy-aware operations assistant
- local research assistant with source traceability
- agent memory audits backed by citations

## Safety Guidance

Agents that can act on external systems need evidence boundaries.

Recommended rules:

- Treat citations and snippets as required for document-grounded claims.
- Read `agent_contract` before acting.
- Treat `agent_contract.may_answer == false` as a stop-and-check condition.
- Treat `support.status == "weak"` as a stop-and-ask condition.
- Treat `conflict_hints` as a stop-and-compare condition.
- Treat `source_diversity.status == "single_source"` as a disclosure condition.
- Do not let an agent use raw document text as authority when MARE can provide a cited evidence payload.

## Public Positioning

Best line:

```text
MARE gives OpenClaw, Hermes, and other agents a local document evidence layer: exact citations, snippets, source coverage, support strength, conflict hints, gaps, research plans, and an action contract.
```

Avoid saying MARE is a native OpenClaw or Hermes plugin unless that plugin has actually been packaged and tested.

## Useful Links

- OpenClaw: https://openclaw.ai/
- Hermes Agent: https://github.com/NousResearch/hermes-agent
- MARE MCP example config: `examples/mcp_stdio_config.json`
