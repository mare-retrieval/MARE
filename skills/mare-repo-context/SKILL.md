---
name: "mare-repo-context"
description: "Use when working in the MARE repository to preserve the current product direction, entrypoints, mixed-document architecture, grounded task flows, MCP/app proof delivery, release state, and repo-specific guardrails. Best for product shaping, release work, onboarding/docs, MCP/app integrations, and evidence-first retrieval improvements."
---

# MARE Repo Context

Use this skill whenever the task is inside the MARE repo and benefits from preserving the current product direction.

## Core product framing

MARE is a **grounded document evidence engine** with a **document-first local product surface** for humans, developers, and agents.

The near-term reality and long-term ambition should both be preserved:

- today: evidence-first retrieval over mixed local documents and document folders
- next: a simple document evidence agent that helps users complete lightweight work from documents
- later: a broader grounded workspace across more document types, integrations, and app surfaces

The product promise is:

- point MARE at a document or folder of documents
- ask questions and get grounded answers with proof
- return file, page/line citation, snippet, highlight when available, and rationale
- help with real document work such as finding, reviewing, comparing, summarizing, and extracting actions, requirements, risks, deadlines, or steps
- keep outputs useful for both humans and agents

Do not frame MARE primarily as:

- a generic chat-with-PDF app
- a vector wrapper
- a full agent framework

Better framing when thinking bigger:

- a grounded document evidence engine
- a document evidence agent
- a system that helps users work with documents, with proof

Important nuance:

- do not oversell unsupported breadth as if MARE already fully handles every document type or modality equally well
- do not lose the evidence-first core while broadening the product story
- keep the current implementation grounded in mixed local documents, with PDFs still providing the strongest visual proof path

## What is completed right now

Treat these as real completed product capabilities, not just aspirations:

- document-first ingestion path for `pdf`, `md`, `markdown`, `txt`, and first-pass `docx`
- mixed-document folder discovery in `mare chat` and `mare workflow`
- built-in evidence retrieval that already does:
  - page and object retrieval
  - lexical and phrase-aware scoring
  - structure and object boosts
  - modality routing plus score fusion
  - highlight rendering and object-region proof fallback
- optional advanced retrieval paths that already exist:
  - hybrid semantic + lexical retrieval
  - sentence-transformers retrieval
  - FAISS retrieval
  - Qdrant hybrid retrieval
  - optional reranking such as FastEmbed
- stronger non-PDF citations using line, heading, and section-aware metadata when available
- guided first-run entrypoint with:
  - `mare start`
  - path-aware onboarding for a folder, a PDF, a non-PDF document, or the bundled mixed-doc example
- task-oriented chat commands:
  - `:review`
  - `:steps`
  - `:compare`
  - `:summary`
  - `:actions`
  - `:requirements`
  - `:risks`
  - `:deadlines`
- structured workflow payloads with:
  - `results`
  - `comparison`
  - `summary`
  - `findings`
  - `review`
- richer MCP proof payloads with:
  - `best_evidence`
  - `proof_assets`
  - `primary_proof_asset`
  - `proof_links`
  - public page/highlight asset URLs when configured
- continuity features:
  - chat session history
  - workflow run history
  - UI recent runs
- MCP query payloads on the richer evidence model
- additive evidence-tool helpers for:
  - LangGraph
  - LangChain
  - LlamaIndex

When talking about current product state, preserve that this repo is no longer only “single PDF retrieval.” It is already a usable mixed-document local product with a real agent-facing evidence layer.

Important correction to preserve:

- do not describe MARE as if it only "shows an evidence image"
- the page image or highlight is the proof presentation layer
- the repo already has a real evidence retrieval pipeline behind that proof layer

## Current product surfaces

Treat these as one product with multiple modes:

- `mare ui`
  - visual playground
  - best first-run path
  - now includes onboarding guidance, review snapshot, grounded summary, grounded findings, and recent runs
- `mare chat`
  - simple folder-based document agent
  - includes review, compare, steps, summary, findings extraction, and saved session history
- `mare ask`
  - fastest single-shot CLI
- `mare workflow`
  - structured terminal workflow
  - includes review view, comparison view, grounded summary, findings extraction, and saved run history
- `mare mcp`
  - integration surface for MCP-capable clients and app platforms
- `mare`
  - canonical front door CLI that dispatches to the modes above
  - includes `mare start` as the guided first-run path

## Priorities

Optimize for:

1. clearer first-run experience
2. grounded retrieval quality
3. evidence visibility
4. product cohesion across modes
5. multi-document and folder-first usefulness
6. task-oriented workflows built on top of retrieval trust
7. agent/platform integration without losing the evidence-first core

When in doubt:

- make the product easier to understand in seconds
- prefer `mare ui` and `mare chat` as the user-facing story
- prefer "point at a folder and ask questions with proof" over narrower internal framing
- keep lower-level builder/integration surfaces below the first-run path
- expand the product vision outward, but keep the implementation story honest

## Jobs to be done

Keep these user jobs in mind when shaping the product:

- ask questions across one PDF or a folder of documents
- find the exact page, snippet, and source proof
- assemble a grounded document review for a narrow question
- compare documents or versions
- extract steps, procedures, or checklists from manuals and SOPs
- extract actions, requirements, risks, and deadlines from operational or policy documents
- produce grounded summaries or briefs for a narrow task
- support small operational work without forcing users to read everything manually

For enterprise-facing thinking, favor:

- document collections over single-file demos
- repeatable trust over flashy answer generation
- integration and governance without adding hero-path complexity

## Repo guardrails

- Do not commit local PDFs such as `116441.pdf` or the Apple support PDF.
- Do not commit the private `notes/` directory unless explicitly requested.
- Do not commit `skills/` or `TESTING.md` unless explicitly requested.
- Respect that the built-in lexical/object-aware path is the recommended default.
- Prefer improving readability and first-run usability before adding more option sprawl.
- Prefer additive integration helpers over breaking native adapter behavior.

## Release state

Read these files before release work:

- `pyproject.toml`
- `setup.py`
- `PUBLISHING.md`
- latest `releases/RELEASE_NOTES_*.md`

Current release train has recently included:

- `v0.4.0`
- `v0.4.1`
- `v0.4.2`
- `v0.4.3`
- `v0.4.4`

Check the current version directly from `pyproject.toml` instead of assuming.

## MCP / Create App direction

MARE supports:

- stdio MCP for local MCP clients
- remote HTTP/streamable HTTP MCP for tunneled or deployed use
- URL-based PDF MCP tools for app platforms where the server must fetch the PDF itself

When discussing platform direction, position MCP as:

- the integration layer for agents and apps
- complementary to the core user-facing experience, not the primary first-run story
- powered by the same retrieval and proof-selection engine as the local UI and CLI surfaces, but returned as machine-readable evidence payloads instead of only human-facing visuals

For remote app flows, prefer:

- `query_document`
- `query_pdf_url`
- `ingest_document`
- `ingest_pdf_url`
- `query_corpus`
- `query_corpora`

Be careful with host/origin allowlists and transport security when discussing ngrok or remote testing.

## Retrieval architecture now

Preserve that the current implementation is already an evidence pipeline, not only a display layer.

Useful shorthand:

- query
- modality routing
- page/object retrieval
- scoring and fusion
- optional reranking
- snippet/evidence selection
- proof rendering
- structured payload delivery

Important current implementation truths:

- `src/mare/router.py` does lightweight heuristic modality routing
- `src/mare/retrievers/text.py` does lexical retrieval, phrase matching, structure boosts, and object boosts
- `src/mare/fusion.py` fuses modality hits into ranked evidence
- `src/mare/extensions.py` provides optional hybrid semantic and advanced retriever paths
- `src/mare/highlight.py` and retrieval flows provide text-span highlighting when possible
- object-region highlighting is used as a fallback for things like tables, figures, and sections

When talking about "RAG" in relation to MARE, prefer this framing:

- MARE already has an evidence-first retrieval architecture
- the important question is how far to push hybrid semantic, OCR/layout, and visual grounding
- not whether retrieval is absent today

## Integration structure now

Preserve this distinction:

- native retriever adapters stay ecosystem-native:
  - `as_langchain_retriever(...)`
  - `as_llamaindex_retriever(...)`
- evidence-tool adapters return rich MARE payloads:
  - `as_langgraph_tool(...)`
  - `as_langchain_tool(...)`
  - `as_llamaindex_tool(...)`

That split is intentional and currently the right product structure.

## Testing status

The main repo regression command currently used to validate the active product surface is:

```bash
pytest tests/test_workflow.py tests/test_chat.py tests/test_streamlit_app.py tests/test_ui.py tests/test_api.py tests/test_extensibility.py tests/test_integrations.py tests/test_objects.py tests/test_mcp_server.py
```

The targeted release-prep validation from this chat reached:

- `76 passed` on the main workflow/chat/UI/integrations/MCP slice
- `python -m build --no-isolation` passed
- `python -m twine check dist/mare-retrieval-0.4.3.tar.gz dist/mare_retrieval-0.4.3-py3-none-any.whl` passed

## Read next

For the fuller current-state snapshot, read:

- `references/current-state.md`
- `references/roadmap.md`
