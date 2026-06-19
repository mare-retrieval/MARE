# MARE 0.4.5

MARE 0.4.5 is the Evidence Brief release.

This release sharpens MARE's public position as a grounded document evidence layer for agents and developers. Instead of only returning a best match, MARE can now explain the trust shape of a retrieval result: source coverage, support strength, conflict hints, proof assets, evidence gaps, and next questions.

## Highlights

- Added Evidence Brief payloads with:
  - support status and message
  - source coverage status and message
  - source count and source documents
  - available proof assets such as snippet, citation, page image, and highlight
  - deterministic conflict hints for obvious language mismatches such as required vs optional
  - evidence gaps
  - next evidence-seeking questions
- Added `mare workflow --task brief`.
- Added evidence rescue in workflow and chat: weak or missing initial support now triggers deterministic alternate evidence-seeking queries, and the payload/history records whether stronger proof was found.
- Added optional FastEmbed semantic retrieval as a lighter ONNX-based first-stage retriever, with smart defaults and the Streamlit selector able to use it when `mare-retrieval[fastembed]` is installed.
- Added `fastembed` to `mare-eval --stack` so teams can compare built-in, FastEmbed, hybrid, and sentence-transformers retrieval on their own cases.
- Added eval comparison recommendations that rank stacks and name the best retrieval choice for the current eval set.
- Added experimental ColPali/ColQwen visual page retrieval behind `mare-retrieval[colpali]`, with Streamlit and eval-stack selection for rendered PDF page images.
- Added `--retriever` selection to `mare workflow` and `mare chat` for smart, built-in, FastEmbed, hybrid, sentence-transformers, and experimental ColPali visual retrieval stacks.
- Added a clear ColPali visual-retrieval setup message when a corpus has no rendered PDF page images.
- Added `:brief` to `mare chat`.
- Added an Evidence Brief section to the Streamlit playground.
- Added `examples/evidence_brief_demo.py`.
- Added `AGENT_INTEGRATIONS.md` with OpenClaw, Hermes Agent, shell-tool, MCP, and Python wrapper recipes.
- Updated `mare start` to lead with the trust-first Evidence Brief flow.
- Updated README and package metadata around the document evidence layer positioning.
- Added `LAUNCH_PLAN.md` for public launch messaging and channel planning.

## Trust-First Demo

From a repo checkout:

```bash
mare workflow --folder ./examples/mixed_docs --query "show me the onboarding steps" --task brief
```

Or:

```bash
PYTHONPATH=src python3 examples/evidence_brief_demo.py
```

## Why It Matters

Agentic document workflows need more than confident answers. They need inspectable evidence before an agent, developer, or user trusts the result.

Evidence Briefs make that explicit:

- What supports this answer?
- How strong is the support?
- Is the evidence concentrated in one source or spread across sources?
- Are there obvious conflict-language signals?
- Which proof assets exist?
- What is missing?
- What should I ask next?

That keeps MARE centered on grounded usefulness rather than generic document chat.
