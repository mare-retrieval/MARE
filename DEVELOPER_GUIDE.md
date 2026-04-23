# Developer Guide

This guide is the fastest way for a developer to get productive in the MARE repository.

## What MARE Is

MARE is an evidence-first PDF retrieval library for developers and agents.

Given a PDF and a question, the core product shape is:

- best matching page
- evidence snippet
- page image
- highlighted evidence image when possible
- structured metadata and retrieval rationale

The main goal is not answer generation. It is grounded evidence retrieval that another app, workflow, or agent can trust and inspect.

## Install Paths

Different install paths are useful for different goals.

- `git clone` gives you the source tree only. It does not install dependencies.
- `pip install mare-retrieval` installs the lightweight core package from PyPI.
- `pip install "git+https://github.com/SaiSandeepKantareddy/MARE.git"` installs the same core package directly from GitHub.
- `pip install -e ".[dev]"` from a local clone installs the repo in editable mode plus test dependencies.

The core install is enough for:

- built-in PDF ingestion
- built-in lexical and object-aware retrieval
- page image rendering
- evidence highlighting
- Python API usage
- CLI usage

Optional extras are for advanced workflows such as OCR-heavy parsing, semantic retrieval, vector backends, framework adapters, and UI tooling.

## Quick Setup From a Clone

```bash
git clone https://github.com/SaiSandeepKantareddy/MARE.git
cd MARE
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest -q
```

If you want notebook-based exploration:

```bash
pip install notebook
jupyter notebook examples/developer_playground.ipynb
```

Important:

- the notebook is part of the GitHub repository, not the installed PyPI package
- it is for developers working from a local clone
- if you only install `mare-retrieval`, use the library and CLI examples from `README.md`

The repository also includes a few tiny bundled example PDFs in `examples/sample_pdfs/` for quick smoke tests.

## First Files To Read

If you are new to the repo, read these first:

1. `README.md`
2. `src/mare/api.py`
3. `src/mare/engine.py`
4. `src/mare/retrievers/text.py`
5. `src/mare/objects.py`
6. `src/mare/highlight.py`
7. `tests/test_engine.py`
8. `tests/test_objects.py`

This path will give you the best understanding of how retrieval quality is produced end-to-end.

## Core Architecture

The repo is organized around this flow:

`PDF -> corpus JSON + page images -> extracted page objects -> query routing -> retrieval -> fusion/rerank -> evidence payload`

The most important modules are:

- `src/mare/api.py`
  - `MAREApp` is the main entrypoint for Python usage.
- `src/mare/engine.py`
  - Runs routing, per-modality retrieval, fusion, and optional reranking.
- `src/mare/types.py`
  - Defines core dataclasses such as `Document`, `DocumentObject`, and `RetrievalHit`.
- `src/mare/ingest.py`
  - Built-in PDF ingestion using `pypdf` and `pypdfium2`.
- `src/mare/objects.py`
  - Extracts procedures, sections, figures, and tables from page text.
- `src/mare/retrievers/text.py`
  - The most important retrieval code in the repo.
- `src/mare/highlight.py`
  - Converts evidence matches back into visible page highlights.

## Public Surfaces

The same retrieval contract is exposed through several surfaces:

- Python API via `MAREApp`
- CLI tools such as `mare-ingest`, `mare-demo`, `mare-ask`, and `mare-eval`
- Streamlit playground in `src/mare/streamlit_app.py`
- MCP server in `src/mare/mcp_server.py`
- framework adapters in `src/mare/integrations.py`

## Commands Worth Knowing

Ingest a PDF:

```bash
mare-ingest "manual.pdf"
```

Ask a PDF a question:

```bash
python3 ask.py "manual.pdf" "how do I connect the AC adapter"
```

Run a demo over a generated corpus:

```bash
mare-demo --corpus generated/manual.json --query "show me the comparison table"
```

Run tests:

```bash
pytest -q
```

Run the UI:

```bash
mare-ui
```

Run the MCP server:

```bash
mare-mcp
```

## Developer Notebook

For hands-on exploration, use:

- `examples/developer_playground.ipynb`

It is intended to help developers:

- ingest a local PDF
- run realistic queries
- inspect the winning evidence
- inspect extracted objects
- understand the core stack before installing optional extras

It assumes you are working from a local clone of the repository.
By default, it can point at the bundled PDFs in `examples/sample_pdfs/`.

## Retrieval Quality Priorities

The built-in stack is the recommended default and currently the strongest general path in the repo.

Current strengths:

- lexical and phrase-aware scoring
- procedure-aware matching
- grouped procedure extraction when headings are found
- object-aware scoring for tables, figures, procedures, and sections
- evidence highlighting as part of the returned result shape

When debugging retrieval quality, inspect:

- extracted page text
- extracted page objects
- `layout_hints`
- `metadata["signals"]`
- the snippet that was chosen
- the reason string on the final hit

## Advanced Extension Points

The main extension surface is `MAREConfig` in `src/mare/extensions.py`.

Important extension categories:

- parsers:
  - `BuiltinPDFParser`
  - `DoclingParser`
  - `UnstructuredParser`
  - `PaddleOCRParser`
  - `SuryaParser`
- retrievers:
  - `SentenceTransformersRetriever`
  - `HybridSemanticRetriever`
  - `FAISSRetriever`
  - `QdrantHybridRetriever`
- rerankers:
  - `IdentityReranker`
  - `KeywordBoostReranker`
  - `FastEmbedReranker`

Guideline:

- stay on the built-in stack by default
- add extras only when you need OCR, semantic lift, vector infrastructure, or framework-specific adapters

## Benchmarking Notes

The eval case JSON files in `examples/` are part of the repo.

The generated corpora in `generated/` should be treated as local artifacts, not something a new user can rely on being present after clone or package install.

Before running eval commands, generate the corpus locally from the source PDF.

Example:

```bash
mare-ingest 116441.pdf
PYTHONPATH=src python3 -m mare.eval \
  --corpus generated/116441.json \
  --eval examples/manual_116441_eval_cases.json
```

If you benchmark advanced stacks like `hybrid-semantic`, install the matching extras first.

## Tests To Trust

The highest-signal tests are:

- `tests/test_engine.py`
- `tests/test_objects.py`
- `tests/test_ingest.py`
- `tests/test_extensibility.py`
- `tests/test_mcp_server.py`
- `tests/test_integrations.py`

These tests reflect the project’s intended behavior more clearly than a casual read of the code alone.

## Release and Packaging

Important packaging files:

- `pyproject.toml`
- `setup.py`
- `PUBLISHING.md`
- `.github/workflows/publish.yml`

Current package naming:

- PyPI package: `mare-retrieval`
- Python import: `mare`

If you bump a release, update both:

- `pyproject.toml`
- `setup.py`
