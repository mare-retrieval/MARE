# MARE

[![PyPI version](https://img.shields.io/pypi/v/mare-retrieval.svg)](https://pypi.org/project/mare-retrieval/)
[![Python versions](https://img.shields.io/pypi/pyversions/mare-retrieval.svg)](https://pypi.org/project/mare-retrieval/)
[![Publish to PyPI](https://github.com/mare-retrieval/MARE/actions/workflows/publish.yml/badge.svg)](https://github.com/mare-retrieval/MARE/actions/workflows/publish.yml)

MARE is an open-source grounded document evidence engine for agents and developers.

Point MARE at a document or folder, ask a question, and get inspectable proof:

```text
documents -> exact evidence -> source coverage -> support strength -> gaps -> next questions
```

MARE is not another generic chat-with-PDF app. It is the document evidence layer underneath products, RAG systems, MCP tools, OpenClaw/Hermes-style agents, and local document workflows.

Optional modern retrieval stacks include FastEmbed semantic retrieval and reranking for lighter ONNX-based embeddings, experimental ColPali/ColQwen visual page retrieval for layout-heavy PDFs, plus sentence-transformers, FAISS, and Qdrant for deeper vector workflows.

## Trust-First Demo

From a repo checkout:

```bash
mare workflow --folder ./examples/mixed_docs --query "show me the onboarding steps" --task brief
```

Or:

```bash
PYTHONPATH=src python3 examples/evidence_brief_demo.py
```

Example output shape:

```text
Evidence brief query: show me the onboarding steps
Weak support from 1 retrieved result across 1 source.
Support note: Evidence is weak or ambiguous. Inspect the proof carefully or refine the question.
Sources: employee-onboarding.docx
Source coverage: Single-source coverage
Proof assets: snippet, citation
Evidence gap 1: Support is weak; ask a narrower question or increase top-k.
Next question 1: Find stronger evidence for: show me the onboarding steps
```

That is the core MARE difference: it shows proof, source coverage, support level, conflict signals when detected, gaps, and the next evidence-seeking move.

## Install

Install from PyPI:

```bash
pip install mare-retrieval
```

Install the visual playground:

```bash
pip install "mare-retrieval[ui]"
```

Install from a repo checkout for examples and development:

```bash
git clone https://github.com/mare-retrieval/MARE.git
cd MARE
pip install -e ".[dev]"
```

## First Run

Use the guided entrypoint:

```bash
mare start
mare start ./examples/mixed_docs
mare start ./docs
```

Run an Evidence Brief over your own folder:

```bash
mare workflow --folder ./docs --query "what does this document set require?" --task brief
```

Ask for the compact agent action contract:

```bash
mare workflow --folder ./docs --query "what does this document set require?" --task contract
```

Choose a retrieval stack explicitly when you want to test an optional path:

```bash
mare workflow --folder ./docs --query "show me the diagram" --task brief --retriever colpali-visual
mare chat --folder ./docs --retriever fastembed
```

Ask one document a question:

```bash
mare ask manual.pdf "how do I connect the AC adapter"
```

Open the visual playground:

```bash
mare ui
```

Then open:

```text
http://localhost:8501
```

Compare retrieval stacks before choosing one:

```bash
mare-eval --corpus generated/manual.json --eval examples/eval_cases.json --stack builtin --stack fastembed --stack hybrid-semantic
```

The comparison output includes a recommendation block with the best stack and ranked page/doc/object, evidence-quality, and no-result metrics.
If you install `mare-retrieval[colpali]`, you can also compare `--stack colpali-visual` on corpora with rendered PDF page images.
If the corpus has no rendered page images, MARE will explain that the visual retriever needs PDF page images and suggest a text retriever instead.

## What You Get

MARE can return:

- best matching page, section, procedure, table-like object, or figure-like object
- exact snippet
- file, page, line, heading, or section-aware citation when available
- rendered PDF page image when available
- highlighted PDF proof image when localization is possible
- retrieval rationale and score
- optional visual page retrieval for image-, chart-, table-, and layout-heavy PDFs through `mare-retrieval[colpali]`
- Evidence Brief with source coverage, support strength, conflict hints, proof assets, gaps, and next questions
- deterministic research plans that tell agents when to answer, retrieve stronger support, compare sources, or resolve conflicts
- agent contracts with a recommended action, answer/stop signal, and stop reasons for tool-using agents
- evidence rescue in `mare workflow` and `mare chat`: when initial support is weak or missing, MARE tries alternate evidence-seeking queries and records whether stronger proof was found
- structured payloads for agents, tools, and applications

## Supported Documents

Current local document-first workflows support:

- `pdf`
- `md` / `markdown`
- `txt`
- first-pass `docx`

PDFs currently have the strongest visual proof because MARE can render pages and highlight evidence. Markdown, text, and DOCX usually rely on snippet and citation proof first.

## Product Surfaces

| Interface | Best for | What you get |
| --- | --- | --- |
| `mare start` | guided onboarding | path-aware next commands |
| `mare ask` | fastest single-document test | best page, snippet, citation, image paths |
| `mare workflow` | terminal evaluation and agent-style output | corpus summary, object search, Evidence Brief, JSON payloads |
| `mare chat` | simple local document-agent loop | `:brief`, `:contract`, `:review`, `:compare`, `:summary`, findings, session history |
| `mare ui` | visual exploration | uploads, Evidence Briefs, summaries, findings, highlights |
| `mare mcp` | agent/app integrations | MCP tools returning structured evidence payloads |

## Agent Integrations

MARE is useful for OpenClaw, Hermes Agent, and other tool-using agents because it gives them a grounded document-evidence tool instead of asking the model to guess from raw files.

Use CLI mode when an agent can run shell commands:

```bash
mare workflow --folder ./docs --query "what should I do before onboarding is complete?" --task brief --format json
```

Use MCP mode when an agent platform supports MCP tools:

```bash
mare mcp
```

See [AGENT_INTEGRATIONS.md](./AGENT_INTEGRATIONS.md) for OpenClaw/Hermes recipes, tool prompts, and safety guidance.

## Python API

```python
from mare import load_document

app = load_document("guide.md", reuse=True)
best = app.best_match("how do I connect the AC adapter")

print(best.page)
print(best.snippet)
print(best.metadata.get("source"))
```

For richer agent payloads, use:

```python
from mare.integrations import hits_to_evidence_payload

hits = app.retrieve("show me the onboarding steps", top_k=3)
payload = hits_to_evidence_payload("show me the onboarding steps", hits)
print(payload["evidence_brief"])
print(payload["evidence_brief"]["research_plan"])
print(payload["agent_contract"])
```

## Optional Integrations

The base install stays lightweight. Add extras as needed:

```bash
pip install "mare-retrieval[ui]"
pip install "mare-retrieval[fastembed]"
pip install "mare-retrieval[colpali]"
pip install "mare-retrieval[sentence-transformers]"
pip install "mare-retrieval[faiss]"
pip install "mare-retrieval[langchain]"
pip install "mare-retrieval[llamaindex]"
pip install "mare-retrieval[mcp]"
pip install "mare-retrieval[integrations]"
```

Advanced optional paths include FastEmbed semantic retrieval and reranking, experimental ColPali/ColQwen visual page retrieval, hybrid semantic retrieval, sentence-transformers, FAISS, Qdrant, LangChain, LangGraph, LlamaIndex, Docling, Unstructured, PaddleOCR, and Surya.

## Generated Files

MARE writes local artifacts under `generated/` by default:

- corpus JSON: `generated/<document-name>.json`
- rendered PDF pages: `generated/<document-name>/page-*.png`
- highlighted proof images: `generated/<document-name>/highlights/*.png`
- chat session history: `generated/chat_sessions/`
- workflow run history: `generated/workflow_runs/`
- UI recent runs: `generated/ui_sessions/playground-history.json`

Use `--no-history` on `mare chat` or `mare workflow` when you want ephemeral runs.

## Development

```bash
git clone https://github.com/mare-retrieval/MARE.git
cd MARE
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

Useful developer entrypoints:

- [DEVELOPER_GUIDE.md](./DEVELOPER_GUIDE.md)
- [examples/evidence_brief_demo.py](./examples/evidence_brief_demo.py)
- [examples/mixed_docs_workflow.py](./examples/mixed_docs_workflow.py)
- `examples/developer_playground.ipynb`

## Architecture

```text
query
  -> modality routing
  -> page/object retrieval
  -> lexical, phrase, structure, and object-aware scoring
  -> optional semantic retrieval and reranking
  -> score fusion
  -> snippet and evidence selection
  -> proof rendering when available
  -> Evidence Brief and structured payloads
```

Core modules:

- `src/mare/engine.py`
- `src/mare/router.py`
- `src/mare/fusion.py`
- `src/mare/retrievers/text.py`
- `src/mare/integrations.py`
- `src/mare/workflow.py`
- `src/mare/mcp_server.py`

## Current Limits

MARE is strongest today on text-bearing PDFs and local mixed-document folders. These areas are still early:

- scanned or camera-captured documents without OCR extras
- table and figure reasoning beyond lightweight object extraction
- deep contradiction analysis beyond deterministic conflict-language hints
- learned multimodal routing

## Roadmap

Near-term priorities:

- stronger hybrid retrieval defaults
- tighter snippets and highlights
- better source diversity and contradiction analysis
- weak-support query rewriting
- evidence evaluation for retrieval quality
- stronger table/layout proof
- clearer agent integration recipes

## License

MIT
