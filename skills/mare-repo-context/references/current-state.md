# Current State

Use this file when deeper repo context is needed than what belongs in `SKILL.md`.

## Product identity now

MARE should be understood as:

**a grounded document evidence engine with a document-first local product surface**

That wording matters because it preserves both truth and ambition:

- PDFs are still the strongest proof surface
- the repo is no longer only a PDF-only story
- mixed-document local workflows are already real
- agent and app integrations now have richer evidence payloads
- the public repo and release packaging now reflect that mixed-document story more honestly

The most useful product ladder is:

- core: evidence-first retrieval and proof
- product: ask questions over documents and folders with proof
- direction: help users complete lightweight document work and grounded document reviews

## What is completed

These are not speculative anymore.

### Document support

Current local document-first path supports:

- `pdf`
- `md`
- `markdown`
- `txt`
- first-pass `docx`

Important nuance:

- PDF still has the strongest visual proof story
- non-PDF docs rely more on snippet + citation proof
- line/heading-aware citations now exist for markdown/text-style flows

### Main product surfaces

The repo now has a much more coherent multi-surface product:

- `mare ui`
  - visual playground
  - mixed-document uploads
  - onboarding-first start state
  - document review snapshot
  - grounded summary section
  - grounded findings section
  - recent runs sidebar persistence
- `mare chat`
  - mixed-document folder chat
  - `:review`
  - `:steps`
  - `:compare`
  - `:summary`
  - `:actions`
  - `:requirements`
  - `:risks`
  - `:deadlines`
  - saved session history
- `mare workflow`
  - mixed-document folder workflow
  - `--task review`
  - structured comparison view
  - structured summary payload
  - structured findings payload
  - saved run history
- `mare ask`
  - still the fastest single-shot path
  - still simpler than the richer chat/workflow surfaces
- `mare mcp`
  - document-first MCP tools
  - richer evidence payloads for query flows
  - remote-friendly proof URLs when configured
- `mare start`
  - guided first-run entrypoint
  - path-aware recommendations for folders, PDFs, non-PDF docs, and the bundled mixed-doc example

### Grounded task flows

MARE now supports meaningful lightweight document work:

- ask grounded questions
- assemble grounded reviews
- compare evidence across hits/docs
- summarize grounded evidence
- extract steps/procedure-like content
- extract actions, requirements, risks, and deadlines from the retrieved evidence

This is important because the product is no longer just retrieval plus pretty output. It has the beginning of real document-work task flows.

## Retrieval architecture now

The repo should not be described as if it only finds an answer and then slaps an image beside it. The current implementation already has a real evidence pipeline.

Current query path, at a high level:

- query
- modality routing
- page and object retrieval
- lexical and phrase-aware scoring
- structure and object boosts
- late fusion across selected modalities
- optional reranking
- snippet selection
- page highlight or object-region proof rendering
- explainable result payloads

Important code-level truths:

- `src/mare/router.py`
  - heuristic modality router for text, image, and layout cues
- `src/mare/engine.py`
  - coordinates selected retrievers and reranking
- `src/mare/retrievers/text.py`
  - built-in lexical retrieval with BM25-like scoring, phrase bonuses, structure boosts, object boosts, snippets, and highlight generation
- `src/mare/fusion.py`
  - weighted fusion across modality hits
- `src/mare/extensions.py`
  - hybrid semantic retriever
  - sentence-transformers retriever
  - FAISS retriever
  - Qdrant hybrid retriever
  - optional rerankers such as FastEmbed

The practical implication:

- the page image/highlight is the proof presentation layer
- retrieval and evidence selection already exist underneath it
- future work should strengthen this pipeline, not describe it as missing

### Continuity and persistence

Continuity now exists across the main user-facing surfaces:

- chat session history
  - `generated/chat_sessions/`
- workflow run history
  - `generated/workflow_runs/`
- UI recent runs
  - `generated/ui_sessions/playground-history.json`

This is part of the product structure now and should be preserved in future shaping.

## Evidence payload structure now

The shared evidence serializer is now a key architectural seam.

Shared payloads can include:

- `results`
- `comparison`
- `summary`
- `findings`
- `review`
- `best_evidence`
- `proof_assets`
- `primary_proof_asset`
- `proof_links`

That richer shape is now used across:

- workflow payloads
- MCP query tools
- LangGraph tool output
- LangChain tool output
- LlamaIndex tool output
- UI grounded summary display

The summary model currently includes:

- `overview`
- `highlight_count`
- `highlights`

The comparison model currently includes:

- source document
- citation
- object type
- page
- score
- snippet
- reason

The MCP proof model now also supports:

- public `page_image_url`
- public `highlight_image_url`
- a shallow `proof_links` block for simpler client consumption

Important product distinction:

- local UI/chat/workflow surfaces present proof primarily for humans
- MCP returns the same grounded retrieval outcome as structured evidence objects for agents and apps
- the engine is shared; the presentation and payload surface differ

The findings model currently includes:

- `actions`
- `requirements`
- `risks`
- `deadlines`

Each finding bucket can include:

- `overview`
- `item_count`
- `items`

The review model currently includes:

- `overview`
- `best_evidence`
- `support`
- `summary_overview`
- `comparison_count`
- `finding_counts`
- `highlights`

## Integration structure now

This distinction is important and intentional:

### Native adapters remain native

These should stay ecosystem-native unless there is a very good reason to break that expectation:

- `as_langchain_retriever(...)`
- `as_llamaindex_retriever(...)`

They return native framework objects.

### Rich evidence-tool adapters

These are the additive path for richer MARE-shaped payloads:

- `as_langgraph_tool(...)`
- `as_langchain_tool(...)`
- `as_llamaindex_tool(...)`

They return structured MARE payloads with:

- `results`
- `comparison`
- `summary`

This split is currently the right product design.

## Current repo structure to remember

Key areas that changed meaningfully in this chat:

- `src/mare/chat.py`
  - mixed-folder support
  - review + task commands
  - chat history
- `src/mare/workflow.py`
  - document-first workflow loading
  - review + comparison + summary + findings payload structure
  - workflow history
- `src/mare/streamlit_app.py`
  - mixed uploads
  - onboarding guidance
  - review snapshot
  - recent runs
  - grounded summary + findings UI
- `src/mare/integrations.py`
  - shared evidence payload structure
  - comparison + summary + findings + review helpers
  - new LangChain/LlamaIndex tool adapters
- `src/mare/mcp_server.py`
  - document-first MCP tools
  - richer shared payload usage
  - public proof asset serving and URL attachment
- `src/mare/api.py`
  - document-first loading
  - tool/retriever adapter methods
- `examples/mixed_docs/`
  - runnable mixed-document workspace
- `examples/mixed_docs_workflow.py`
  - mixed-doc workflow demo
- `releases/`
  - versioned release notes moved out of the repo root for a cleaner public layout

## How the product should be described now

Good description:

- point MARE at a document or folder
- ask questions and get grounded evidence
- review, compare, summarize, and extract actions, requirements, risks, deadlines, or steps
- keep outputs inspectable for humans and usable for agents

Descriptions to avoid:

- “just a chat-with-PDF app”
- “already supports every document type equally well”
- “general AI assistant”

Best honest phrasing:

- grounded document evidence engine
- document evidence layer
- document-first local product with strongest proof on PDFs

Important phrasing to avoid in future chats:

- "MARE is only showing evidence images"
- "MARE still needs retrieval from scratch"

Better correction:

- MARE already retrieves, ranks, and packages evidence
- visual proof is one delivery surface of that evidence system

## What still matters most

The next work should still bias toward:

- better first-run clarity
- stronger retrieval quality
- stronger evidence quality
- more useful document-work tasks
- additive integrations, not breaking ones
- keeping the product coherent across chat, workflow, UI, MCP, and adapters

## What is still intentionally not “fully generalized”

This repo is in a much better state now, but preserve these truths:

- PDF remains the strongest proof surface
- `mare ask` is still simpler than the richer workflow/chat/tool paths
- LangChain and LlamaIndex retrievers remain native adapter surfaces
- not every surface should be forced into the same UX if that breaks ecosystem fit

## Suggested current user journey

1. `mare ui`
2. upload mixed documents and inspect grounded summary + evidence
3. `mare chat --folder ./examples/mixed_docs`
4. try `:summary`, `:compare`, and `:steps`
5. `mare workflow --folder ./examples/mixed_docs --format json --query "..."`
6. then go deeper with MCP or framework adapters

## Release checkpoint

Current shipped public version from this chat:

- `v0.4.3`

Important release-level truths captured in that version:

- mixed-document support is part of the public story
- public examples now include `examples/mixed_docs/`
- release notes live under `releases/`
- MCP proof delivery is stronger and more explicit for agent/app clients

## Testing status

The active regression command used for the current product surface is:

```bash
pytest tests/test_workflow.py tests/test_chat.py tests/test_streamlit_app.py tests/test_ui.py tests/test_api.py tests/test_extensibility.py tests/test_integrations.py tests/test_objects.py tests/test_mcp_server.py
```

Latest targeted release-prep status from this repo chat:

- `61 passed`
- `python -m build --no-isolation` passed
- `python -m twine check dist/mare-retrieval-0.4.3.tar.gz dist/mare_retrieval-0.4.3-py3-none-any.whl` passed

## Local artifacts to keep out of commits

- `116441.pdf`
- Apple support PDFs in the repo root
- `notes/`
- `skills/`
- `TESTING.md`
- `MacBook Pro (14-inch, M5 Pro or M5 Max) MagSafe 3 Board - Apple Support.pdf`
- `notes/`
- 'skills/mare-repo-context'
- 'TESTING.md'
