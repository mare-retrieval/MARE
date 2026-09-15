# MARE 0.4.7

> Superseded by [MARE 0.4.8](https://github.com/mare-retrieval/MARE/releases/tag/v0.4.8). Use 0.4.8 or newer. The follow-up release includes everything in 0.4.7 plus remote MCP hardening, CI, and expanded evaluation.

MARE 0.4.7 is the Evidence Quality and Provenance release.

This release makes MARE's agent-facing evidence easier to evaluate, reference, and audit. Evidence Briefs now expose explicit quality checks, and retrieved evidence carries stable identifiers and provenance metadata that survive structured workflow and agent handoffs.

## Highlights

- Added structured `evidence_quality` signals to Evidence Briefs.
- Added checks for support strength, source diversity, proof availability, citation completeness, and table-grounding precision.
- Added compact evidence-quality output to `mare workflow`, `mare chat`, `mare ui`, and evaluation reports.
- Added quality-aware rescue behavior so alternate retrieval attempts are accepted only when they improve the evidence assessment.
- Added stable `evidence_id` values derived from source and evidence provenance rather than result rank.
- Added structured provenance metadata to serialized evidence results.
- Added `top_provenance` to Evidence Briefs for fast agent inspection.
- Propagated provenance through workflow payloads, reviews, MCP tools, and integration adapters.
- Expanded regression coverage for evidence quality, provenance stability, and cross-surface payload consistency.

## Why It Matters

Agentic retrieval needs more than a relevance score. An agent must know whether evidence is sufficiently supported, whether proof is inspectable, and whether the same evidence can be referenced reliably across retries and downstream actions.

With evidence-quality checks and stable provenance IDs, MARE clients can:

- inspect why an evidence set is considered strong or weak
- decide whether to answer, retrieve again, or request another source
- preserve evidence references when result ordering changes
- attach audit-friendly provenance to agent decisions
- evaluate retrieval improvements using the same trust signals exposed to users

This keeps MARE focused on its core role: the inspectable document-evidence layer beneath agents and grounded document workflows.
