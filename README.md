# MARE

[![PyPI version](https://img.shields.io/pypi/v/mare-retrieval.svg)](https://pypi.org/project/mare-retrieval/)
[![Python versions](https://img.shields.io/pypi/pyversions/mare-retrieval.svg)](https://pypi.org/project/mare-retrieval/)
[![Publish to PyPI](https://github.com/SaiSandeepKantareddy/MARE/actions/workflows/publish.yml/badge.svg)](https://github.com/SaiSandeepKantareddy/MARE/actions/workflows/publish.yml)

MARE is an open-source Python library for evidence-first PDF retrieval for developers and agents.

Given a PDF and a question, MARE is built to return:

- the best matching page
- the exact evidence snippet
- the rendered page image
- a highlighted evidence image when the match can be localized
- retrieval rationale for debugging and trust

The bigger goal is simple:

- let agents and applications ask questions over PDFs
- return grounded evidence instead of vague document answers
- make the answer inspectable as page, snippet, highlight, and visual proof

MARE is meant to sit underneath agent logic and application logic as the PDF evidence layer.

It started from the broader multimodal retrieval direction highlighted by the IRPAPERS paper, but the current package is intentionally focused on a more concrete and reliable use case: local PDF retrieval with visible evidence that agents and developers can build on.

Paper inspiration: https://arxiv.org/pdf/2602.17687

## What MARE does today

- Ingests PDFs locally into page-level corpora
- Extracts page text and renders page images
- Retrieves relevant pages for natural-language questions
- Returns exact snippets instead of only broad page matches
- Generates highlighted page images for matched evidence
- Extracts document objects such as procedures, sections, figures, and tables
- Supports object-aware retrieval, with the strongest behavior today on procedures and sections
- Exposes a Python API, CLI tools, and a Streamlit demo
- Includes an evaluation harness for page/object/no-result benchmarking

## The bigger picture

MARE is not trying to be a full agent framework, vector database, or parser platform.

MARE is trying to solve one hard layer well:

```text
question about a PDF -> grounded evidence -> agent/app uses that evidence
```

That means MARE should be the layer that returns:

- the best page
- the best snippet
- the best retrieved object when possible
- the highlight or visual proof
- a structured result that code, agents, and workflows can consume

The built-in stack is the recommended default today. The advanced parsers, retrievers, rerankers, and framework adapters exist so teams can plug MARE into bigger systems without losing the evidence-first output shape.

## What is still early or experimental

- Table retrieval
- Figure retrieval
- Layout-aware retrieval beyond lightweight heuristics
- Modality-aware routing as a fully learned system

## Why this exists

Most "chat with your PDF" systems optimize for a polished answer. MARE is optimized for evidence.

For manuals, support docs, procedures, and technical documentation, users usually want:

- where is this in the document?
- what exact instruction supports it?
- can I inspect the page myself?

That is the core product shape of MARE:

```text
PDF -> retrieval -> exact snippet -> page image -> highlighted evidence
```

For agents, the shape becomes:

```text
user question -> agent -> MARE -> page + snippet + highlight + proof
```

## Current architecture

```text
query
  -> page and object retrieval
  -> scoring and lightweight routing
  -> best page + best object
  -> snippet extraction
  -> page image / highlighted evidence
  -> explainable results
```

Current implementation choices:

- Ingestion: `pypdf` + `pypdfium2`
- Retrieval: lexical and phrase-aware scoring with object boosts
- Object extraction: procedure, section, figure, and table-like objects
- Highlighting: render matched text back onto the page image when possible
- Explainability: reasons, selected object type, and score context

## Repo layout

```text
src/mare/
  engine.py
  router.py
  fusion.py
  types.py
  retrievers/
examples/
tests/
```

## Quickstart

Clone and install:

```bash
git clone https://github.com/SaiSandeepKantareddy/MARE.git
cd MARE
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Or install directly from GitHub:

```bash
pip install "git+https://github.com/SaiSandeepKantareddy/MARE.git"
```

The intended package install after PyPI release is:

```bash
pip install mare-retrieval
```

That base install is intentionally lightweight. Optional stacks such as Streamlit, sentence-transformers, FAISS, LangChain, OCR parsers, and other advanced integrations are installed through extras.

For most users, the best starting point is still MARE's built-in stack. The optional integrations are there to support experimentation, scaling, OCR-heavy documents, or agent/framework integration without changing the evidence-first contract.

Then use it as a library:

```python
from mare import MAREApp

app = MAREApp.from_pdf("manual.pdf", reuse=True)
best = app.best_match("partially reinstall the set screws if they fall out")

print(best.page)
print(best.snippet)
print(best.page_image_path)
```

Or try it from the CLI after ingesting a real PDF:

```bash
mare-ingest "manual.pdf"
mare-demo --corpus "generated/manual.json" --query "how do I connect the AC adapter"
```

## Simplest way to use it

Use one command:

```bash
python3 ask.py "MacBook Pro (14-inch, M5 Pro or M5 Max) MagSafe 3 Board - Apple Support.pdf" "partially reinstall the set screws if they fall out"
```

That will:

- ingest the PDF if needed
- retrieve the best matching page
- print the page number
- print the exact snippet
- print the rendered page image path

If you want to reuse a previously generated corpus:

```bash
python3 ask.py --reuse "MacBook Pro (14-inch, M5 Pro or M5 Max) MagSafe 3 Board - Apple Support.pdf" "partially reinstall the set screws if they fall out"
```

If the PDF filename is awkward, rename it first:

```bash
mv ./*.pdf ./manual.pdf
PYTHONPATH=src python3 ask.py ./manual.pdf "partially reinstall the set screws if they fall out"
```

## Public Python API

The package is meant to be importable, not just runnable from scripts.

```python
from mare import MAREApp, load_corpus, load_pdf
```

Create an app from a PDF:

```python
app = load_pdf("manual.pdf", reuse=True)
hit = app.best_match("what does MagSafe 3 refer to")
```

This is the core library shape MARE is optimizing around: something an agent or application can call to get grounded PDF evidence, not just an answer-shaped blob.

Create an app from an existing JSON corpus:

```python
app = load_corpus("generated/manual.json")
results = app.retrieve("how do I configure wake on lan", top_k=3)
```

Core methods:

- `MAREApp.from_pdf(...)`
- `MAREApp.from_corpus(...)`
- `MAREApp.from_documents(...)`
- `app.explain(query)`
- `app.retrieve(query)`
- `app.best_match(query)`

## Developer-friendly extension points

MARE is designed to be usable out of the box, but it should also be easy to improve on a bigger machine or inside an existing AI stack.

Today you can plug in:

- a custom PDF parser
- custom retriever factories per modality
- a second-stage reranker

That means developers can keep MARE's API and UI while swapping in stronger components.

```python
from pathlib import Path

from mare import MAREApp, MAREConfig, Modality


class MyParser:
    def ingest(self, pdf_path: Path, output_path: Path) -> Path:
        # Build a MARE-compatible corpus here using your preferred parser.
        ...
        return output_path


class MyReranker:
    def rerank(self, query, hits, top_k=5):
        # Reorder fused hits using your favorite cross-encoder or API.
        return hits[:top_k]


class MyTextRetriever:
    def __init__(self, documents):
        self.documents = documents

    def retrieve(self, query, top_k=5):
        ...


config = MAREConfig(
    reranker=MyReranker(),
    retriever_factories={
        Modality.TEXT: lambda documents: MyTextRetriever(documents),
    },
)

app = MAREApp.from_pdf("manual.pdf", parser=MyParser(), config=config)
best = app.best_match("how do I configure wake on lan")
```

Built-in extension helpers:

- `BuiltinPDFParser` for the default local pipeline
- `DoclingParser` and `UnstructuredParser` for richer parsing stacks
- `LangChain`, `LangGraph`, and `LlamaIndex` adapters for ecosystem-friendly retrieval
- `PaddleOCRParser` and `SuryaParser` for OCR-first parsing on scanned or image-heavy PDFs
- `FAISSIndexer` and `FAISSRetriever` for local vector retrieval without a running service
- `SentenceTransformersRetriever` for drop-in semantic retrieval with Hugging Face models
- `HybridSemanticRetriever` for the recommended advanced path that preserves MARE's lexical/object-aware evidence behavior and adds semantic lift
- `FastEmbedReranker` for open-source cross-encoder reranking
- `QdrantIndexer` for indexing MARE documents into a local or remote Qdrant collection
- `QdrantHybridRetriever` for vector-backed retrieval on local or remote Qdrant collections
- `IdentityReranker` as a no-op baseline
- `KeywordBoostReranker` as a simple built-in reranker example

Recommended upgrade paths for developers:

- `Docling` for richer local document parsing, layout, OCR, and table structure
- `Unstructured` for document partitioning and element extraction
- `PaddleOCR` for lightweight OCR-first extraction on scanned pages
- `Surya` for OCR plus layout-aware document parsing on harder scanned documents
- `FastEmbed` for local dense and sparse embeddings
- `FAISS` for fast local vector search with minimal setup
- `Qdrant` for hybrid dense/sparse/multivector retrieval and reranking pipelines
- `BGE-M3` for flexible dense + sparse retrieval setups
- `ColPali` for page-image retrieval when visual structure matters

MARE's job is to provide the retrieval framework and evidence-first UX. Better models and external systems should be able to plug into that foundation, not replace it.

Install optional integrations when you need them:

```bash
pip install "mare-retrieval[docling]"
pip install "mare-retrieval[faiss]"
pip install "mare-retrieval[langchain]"
pip install "mare-retrieval[langgraph]"
pip install "mare-retrieval[llamaindex]"
pip install "mare-retrieval[paddleocr]"
pip install "mare-retrieval[sentence-transformers]"
pip install "mare-retrieval[surya]"
pip install "mare-retrieval[unstructured]"
pip install "mare-retrieval[fastembed]"
pip install "mare-retrieval[integrations]"
```

### New-user install advice

If you want the smoothest first experience, install in layers instead of trying to pull every optional dependency at once.

Good path:

1. Core visual playground

```bash
pip install -e ".[ui]"
```

2. Advanced retrieval stack

```bash
pip install -e ".[sentence-transformers,faiss,langchain,langgraph,llamaindex,fastembed]"
```

3. Heavier parsing / OCR stacks only when you need them

```bash
pip install -e ".[unstructured]"
pip install -e ".[docling]"
pip install -e ".[paddleocr]"
pip install -e ".[surya]"
```

This is more reliable than trying to install every heavy optional dependency in one shot.

### Sentence-transformers note

If you use the `Sentence Transformers` retriever in the Streamlit Playground, keep the environment healthy:

- `numpy<2` is often the safer choice for mixed compiled dependencies
- on some Macs, newer `torch` wheels may not be available, so a working combo can look like:
  - `torch==2.2.2`
  - `transformers==4.49.0`
  - `sentence-transformers==3.4.1`
- if you install heavier extras later, especially `docling`, they may upgrade `numpy` again; if the semantic retriever starts failing after that, re-pin:
  - `pip install "numpy<2"`
  - then reinstall the compatible torch stack if needed

If Streamlit becomes noisy while inspecting `transformers`, run it with file watching disabled:

```bash
STREAMLIT_SERVER_FILE_WATCHER_TYPE=none PYTHONPATH=src python -m streamlit run src/mare/streamlit_app.py
```

### What this means in practice

On a small local machine, you can use MARE with the built-in parser and retrievers.

On a bigger machine or inside a production stack, you can upgrade pieces independently:

- swap the parser for `Docling` or `Unstructured`
- swap the parser for OCR-first stacks like `PaddleOCRParser` or `SuryaParser` when PDFs are scanned
- swap the text retriever for an embedding-backed retriever such as `SentenceTransformersRetriever`
- add a local vector backend like `FAISS` when you want a stronger local stack
- add a cross-encoder reranker
- later plug in a vector backend like `Qdrant` and use `QdrantIndexer` to populate it

That is the intended habit MARE should create:

start simple, then improve the stack without changing the application-facing API.

Example: use Unstructured for parsing and FastEmbed for reranking.

```python
from mare import FastEmbedReranker, MAREApp, MAREConfig, UnstructuredParser

config = MAREConfig(
    reranker=FastEmbedReranker(),
)

app = MAREApp.from_pdf(
    "manual.pdf",
    parser=UnstructuredParser(strategy="hi_res"),
    config=config,
)

best = app.best_match("show me the comparison table")
```

This keeps the same MARE API while letting developers improve parsing and ranking with open-source components.

Example: use a sentence-transformers semantic retriever without changing the app API.

```python
from mare import MAREApp, MAREConfig, Modality, SentenceTransformersRetriever

config = MAREConfig(
    retriever_factories={
        Modality.TEXT: lambda documents: SentenceTransformersRetriever(
            documents,
            model_name="sentence-transformers/all-MiniLM-L6-v2",
        )
    }
)

app = MAREApp.from_corpus("generated/manual.json", config=config)
best = app.best_match("how do I connect the AC adapter")
```

This is a good default upgrade path when you want stronger semantic matching with widely used open-source models from the Hugging Face ecosystem.

Example: index locally with FAISS, then retrieve through MARE.

```python
from mare import FAISSIndexer, FAISSRetriever, MAREApp, MAREConfig, Modality, load_corpus

app = load_corpus("generated/manual.json")

indexer = FAISSIndexer("generated/manual.faiss")
indexer.index_documents(app.documents, recreate=True)

config = MAREConfig(
    retriever_factories={
        Modality.TEXT: lambda documents: FAISSRetriever(
            documents,
            index_path="generated/manual.faiss",
        )
    }
)

faiss_app = MAREApp.from_corpus("generated/manual.json", config=config)
best = faiss_app.best_match("how do I connect the AC adapter")
```

This is the easiest local “next step” after the built-in retriever when you want a stronger vector setup without running an external service.

Example: plug MARE into LangChain or LangGraph as a retriever.

```python
from mare import MAREApp

app = MAREApp.from_corpus("generated/manual.json")
retriever = app.as_langchain_retriever(top_k=3)

docs = retriever.invoke("how do I configure wake on lan")
```

Each returned LangChain document includes the usual page content plus MARE metadata like `page`, `score`, `object_type`, `page_image_path`, and `highlight_image_path`.

Example: use MARE as a LangGraph-ready evidence tool.

```python
from mare import MAREApp

app = MAREApp.from_corpus("generated/manual.json")
tool = app.as_langgraph_tool(top_k=3)

result = tool.invoke({"query": "how do I configure wake on lan"})
```

The tool returns structured evidence with page, snippet, highlight path, and metadata, which fits naturally into agent/tool workflows where the LLM needs grounded retrieval output instead of a plain text blob.

## MCP server for agents

If you want agents outside Python to call MARE as a reusable tool layer, MARE now includes a first MCP server surface.

Install:

```bash
pip install "mare-retrieval[mcp]"
```

Run:

```bash
mare-mcp
```

The MCP server exposes focused tools for the evidence layer:

- `ingest_pdf`
- `query_pdf`
- `query_corpus`
- `page_objects`

These tools return structured MARE-shaped payloads with grounded evidence such as:

- `page`
- `snippet`
- `highlight_image_path`
- `object_type`
- `reason`

This is the intended agent architecture:

```text
user -> agent -> MARE MCP tool -> page + snippet + highlight + proof
```

So MARE stays the PDF evidence layer, while the agent keeps responsibility for planning, orchestration, and final response generation.

Example: plug MARE into LlamaIndex as a retriever.

```python
from llama_index.core.schema import QueryBundle
from mare import MAREApp

app = MAREApp.from_corpus("generated/manual.json")
retriever = app.as_llamaindex_retriever(top_k=3)

nodes = retriever.retrieve(QueryBundle("how do I connect the AC adapter"))
```

This gives you `NodeWithScore` results built from MARE evidence hits, so the surrounding LlamaIndex workflow can keep using its native abstractions.

Example: use Docling for richer document parsing.

```python
from mare import DoclingParser, MAREApp

app = MAREApp.from_pdf(
    "manual.pdf",
    parser=DoclingParser(),
)

best = app.best_match("how do I configure wake on lan")
```

Docling is especially promising when you want stronger OCR, layout, and table/figure extraction while still keeping the MARE API unchanged.

Example: use PaddleOCR for scanned PDFs where text extraction is weak.

```python
from mare import MAREApp, PaddleOCRParser

app = MAREApp.from_pdf(
    "scanned-manual.pdf",
    parser=PaddleOCRParser(lang="en"),
)

best = app.best_match("what does this warning label say")
```

This is a good fit when the document is primarily scan-based and you want a lightweight OCR-first path.

Example: use Surya for OCR plus layout-aware extraction on harder scanned documents.

```python
from mare import MAREApp, SuryaParser

app = MAREApp.from_pdf(
    "scanned-manual.pdf",
    parser=SuryaParser(),
)

best = app.best_match("show me the table with configuration settings")
```

Surya is especially promising when you want OCR plus layout signals like section headers, figures, and tables from scanned or camera-captured pages.

Example: keep MARE's app surface, but swap retrieval to Qdrant.

```python
from mare import MAREApp, MAREConfig, Modality, QdrantHybridRetriever

config = MAREConfig(
    retriever_factories={
        Modality.TEXT: lambda documents: QdrantHybridRetriever(
            documents,
            collection_name="mare-docs",
            url="http://localhost:6333",
            vector_name="text",
        )
    }
)

app = MAREApp.from_corpus("generated/manual.json", config=config)
best = app.best_match("how do I connect the AC adapter")
```

Expected Qdrant payload fields:

- `doc_id`
- `title`
- `page`
- `text` or `snippet`
- optional: `page_image_path`, `highlight_image_path`, `object_id`, `object_type`, `metadata`

Example: index a MARE corpus into Qdrant before using the hybrid retriever.

```python
from mare import QdrantIndexer, load_corpus

documents = load_corpus("generated/manual.json")

indexer = QdrantIndexer(
    collection_name="mare-docs",
    url="http://localhost:6333",
    vector_name="text",
)
indexer.index_documents(documents, recreate=True)
```

By default, `QdrantIndexer` uses a sentence-transformers embedder. Developers can swap in their own embedder callable if they already have a preferred model or service.

A complete advanced-stack example is available in:

- `examples/advanced_stack.py`

It supports combinations like:

- built-in / Docling / Unstructured parsing
- sentence-transformers semantic retrieval
- Qdrant indexing plus Qdrant-backed retrieval
- FastEmbed reranking
- LangChain document output
- LangGraph-ready tool output
- LlamaIndex node output

Example:

```bash
PYTHONPATH=src python3 examples/advanced_stack.py \
  --corpus generated/manual.json \
  --query "how do I configure wake on lan" \
  --semantic \
  --reranker fastembed
```

Or, if you want a more production-like path:

```bash
PYTHONPATH=src python3 examples/advanced_stack.py \
  --pdf manual.pdf \
  --parser docling \
  --query "show me the comparison table" \
  --qdrant-url http://localhost:6333 \
  --qdrant-collection mare-docs \
  --index-qdrant \
  --use-qdrant
```

## Packaging and release

MARE is now structured as a regular Python package with:

- `pyproject.toml` metadata
- legacy-friendly `setup.py`
- console entry points
- a PyPI publishing workflow

Release notes and PyPI steps live in `PUBLISHING.md`.

## Visual demo

If you want to show this to users visually, run the Streamlit demo:

```bash
pip install -e ".[ui]"
PYTHONPATH=src python -m streamlit run src/mare/streamlit_app.py
```

If you use the `Sentence Transformers` option in Advanced mode and Streamlit starts emitting transformer watcher noise, prefer:

```bash
STREAMLIT_SERVER_FILE_WATCHER_TYPE=none PYTHONPATH=src python -m streamlit run src/mare/streamlit_app.py
```

The demo lets a user:

- upload a PDF
- ask a question
- see the best matching page and object type
- read the exact evidence snippet
- view the rendered page image
- view the highlighted evidence image when available
- inspect extracted objects on the best page

The Streamlit app is the easiest way to explore MARE visually.
The Python package is where developers get full control over:

- custom parsers
- custom retrievers
- vector backends
- rerankers
- framework integrations
- evaluation harnesses

For non-text objects such as tables and figures, MARE now falls back to region-level page highlighting when exact text-span highlighting is not available yet.

The technical retrieval plan is hidden under a `Debug details` expander so the default experience stays user-facing.

## Ingest a real PDF

You can convert a PDF into a page-level JSON corpus and then run retrieval on it.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
mare-ingest "MacBook Pro (14-inch, M5 Pro or M5 Max) MagSafe 3 Board - Apple Support.pdf"
mare-demo --corpus "generated/MacBook Pro (14-inch, M5 Pro or M5 Max) MagSafe 3 Board - Apple Support.json" --query "what does MagSafe 3 refer to"
```

Without installing the package first:

```bash
PYTHONPATH=src python3 -m mare.ingest "MacBook Pro (14-inch, M5 Pro or M5 Max) MagSafe 3 Board - Apple Support.pdf"
PYTHONPATH=src python3 -m mare.demo --corpus "generated/MacBook Pro (14-inch, M5 Pro or M5 Max) MagSafe 3 Board - Apple Support.json" --query "what does MagSafe 3 refer to"
```

What the ingest step does right now:

- reads each PDF page with `pypdf`
- renders each PDF page to `generated/<pdf-name>/page-N.png`
- extracts page text
- creates one retrieval document per page
- extracts lightweight document objects such as procedures and sections
- writes a JSON corpus that the retriever can search immediately

This is still a practical baseline, not a full parsing stack. OCR-heavy documents, richer figure extraction, and stronger layout modeling are next steps.

## What you get back

The retriever now returns:

- the matching page number
- why that page matched
- a short exact snippet from the page text
- the rendered page image path
- a highlighted evidence image when text spans can be located on the page
- the best matching object type when object-aware retrieval is used

That makes it easier to validate whether retrieval found the right instruction and jump to the exact page image.

Example output:

```json
{
  "query": "how do I connect the AC adapter",
  "intent": "semantic_lookup",
  "selected_modalities": ["text"],
  "discarded_modalities": ["image", "layout"],
  "confidence": 0.7,
  "rationale": "Detected modality cues in query tokens. Selected text based on keyword overlap with routing hints.",
  "results": [
    {
      "doc_id": "manual-p13",
      "title": "Manual",
      "page": 13,
      "score": 1.0,
      "object_type": "procedure",
      "reason": "Best object: procedure | phrase match x2",
      "snippet": "2 Connect the AC adapter to the DC jack of the computer."
    }
  ]
}
```

## Why the explainability matters

The debug surface is a core feature, not an afterthought. For retrieval systems that support real work, we need to answer:

- Why did this page rank highly?
- Which object matched best?
- Why was a result returned instead of another nearby page?
- When should the system return no result?

That is the wedge for MARE: make retrieval inspectable before trying to make it magical.

## Evaluation Harness

MARE now includes a lightweight evaluation harness so we can measure retrieval quality instead of guessing.

It supports:

- page hit rate
- document hit rate
- object hit rate
- no-result correctness

Run it with:

```bash
mare-eval --corpus examples/sample_corpus.json --eval examples/eval_cases.json
```

Or from source:

```bash
PYTHONPATH=src python3 -m mare.eval --corpus examples/sample_corpus.json --eval examples/eval_cases.json
```

The evaluation file is simple JSON:

```json
{
  "cases": [
    {
      "query": "show me the architecture diagram",
      "expected_doc_id": "paper-hyde-p3",
      "expected_page": 3,
      "expected_object_type": "figure",
      "top_k": 3
    },
    {
      "query": "show me a nonexistent appendix table",
      "expect_no_result": true,
      "top_k": 3
    }
  ]
}
```

This is useful both for library developers and for teams evaluating their own parser/retriever/reranker combinations on top of MARE.

## Local sample data

`examples/sample_corpus.json` contains a tiny corpus so the retrieval flow is runnable out of the box.

There is also a local PDF in this workspace:

- `MacBook Pro (14-inch, M5 Pro or M5 Max) MagSafe 3 Board - Apple Support.pdf`

That file can now be ingested into a JSON page corpus with `mare-ingest`.

## Roadmap

Near term:

- better figure extraction
- stronger table extraction
- cleaner object segmentation on large manuals
- better highlighted evidence localization

Next layer:

- hybrid retrieval backends
- embedding and reranking adapters
- LangChain and LlamaIndex integrations
- agent-friendly interfaces

Longer term:

- richer layout-aware retrieval
- benchmark harness for evidence-first document retrieval
- more robust modality-aware routing

## License

MIT
