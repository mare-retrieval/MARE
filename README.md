# MARE

[![PyPI version](https://img.shields.io/pypi/v/mare-retrieval.svg)](https://pypi.org/project/mare-retrieval/)
[![Python versions](https://img.shields.io/pypi/pyversions/mare-retrieval.svg)](https://pypi.org/project/mare-retrieval/)
[![Publish to PyPI](https://github.com/SaiSandeepKantareddy/MARE/actions/workflows/publish.yml/badge.svg)](https://github.com/SaiSandeepKantareddy/MARE/actions/workflows/publish.yml)

MARE is an open-source Python library for evidence-first document retrieval.

It is inspired by the direction highlighted in the IRPAPERS paper, which shows that page-image retrieval and text retrieval have complementary failure modes on scientific documents. Instead of flattening everything into one retrieval path, MARE treats routing, retrieval, fusion, and observability as separate system concerns.

## What this repo is

- A lightweight Python package between a query and modality-specific indexes
- A baseline router that decides whether a query should hit text, image, layout, or a hybrid path
- A late-fusion layer that combines modality-specific scores
- An explainable debug surface that tells you why a modality was selected

## What this repo is not

- Not a chatbot wrapper
- Not a full PDF parsing stack yet
- Not a claim that heuristic routing is state of the art

## Why now

IRPAPERS asks a useful systems question: when should we retrieve over OCR text, page images, layout structure, or some combination? The paper reports that text-based and image-based retrieval each solve queries the other misses, and that fusion improves retrieval quality over either modality alone.

This repo turns that observation into an MVP developer layer.

Paper: https://arxiv.org/pdf/2602.17687

## Architecture

```text
query
  -> router
  -> modality-specific retrievers
     -> text index
     -> image index
     -> layout index
  -> fusion
  -> explainable results
```

Current implementation choices:

- Router: keyword heuristic baseline
- Text retrieval: token-overlap cosine baseline
- Image retrieval: caption and visual-tag overlap baseline
- Layout retrieval: layout-hint overlap baseline
- Fusion: weighted late fusion

The point of `v0.1` is not raw benchmark quality. It is to package the control plane cleanly enough that stronger models can drop in later.

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

Then use it as a library:

```python
from mare import MAREApp

app = MAREApp.from_pdf("manual.pdf", reuse=True)
best = app.best_match("partially reinstall the set screws if they fall out")

print(best.page)
print(best.snippet)
print(best.page_image_path)
```

Or try the sample corpus from the CLI:

```bash
mare-demo --query "show me the architecture diagram of transformer"
```

Or without installing the package yet:

```bash
PYTHONPATH=src python3 -m mare.demo --query "show me the architecture diagram of transformer"
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

Create an app from an existing JSON corpus:

```python
app = load_corpus("generated/manual.json")
results = app.retrieve("show me the comparison table", top_k=3)
```

Core methods:

- `MAREApp.from_pdf(...)`
- `MAREApp.from_corpus(...)`
- `MAREApp.from_documents(...)`
- `app.explain(query)`
- `app.retrieve(query)`
- `app.best_match(query)`

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
PYTHONPATH=src streamlit run src/mare/streamlit_app.py
```

The demo lets a user:

- upload a PDF
- ask a question
- see the best matching page
- read the exact evidence snippet
- view the rendered page image

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
- adds lightweight layout hints when terms like `Table` or `Figure` appear
- writes a JSON corpus that the retriever can search immediately

This is still a simple baseline. OCR, figure extraction, and true layout modeling are the next step.

## What you get back

The retriever now returns:

- the matching page number
- why that page matched
- a short exact snippet from the page text
- the rendered page image path

That makes it easier to validate whether retrieval found the right instruction and jump to the exact page image.

Example output:

```json
{
  "query": "show me the architecture diagram of transformer",
  "intent": "visual_lookup",
  "selected_modalities": ["image"],
  "discarded_modalities": ["text", "layout"],
  "confidence": 0.8,
  "rationale": "Detected modality cues in query tokens. Selected image based on keyword overlap with routing hints.",
  "results": [
    {
      "doc_id": "paper-transformer-p4",
      "title": "Attention Is All You Need",
      "page": 4,
      "score": 0.6,
      "reason": "image:Matched visual cues: architecture, diagram, transformer"
    }
  ]
}
```

## Why the explainability matters

The debug surface is a core feature, not an afterthought. For production retrieval systems, we need to answer:

- Which modality did the router choose?
- Which modalities were skipped?
- Why did a page rank highly?
- What tradeoff did fusion make?

That is the wedge for MARE: make multimodal retrieval inspectable before trying to make it magical.

## Local sample data

`examples/sample_corpus.json` contains a tiny IR-paper-style corpus so the routing and fusion path is runnable out of the box.

There is also a local PDF in this workspace:

- `MacBook Pro (14-inch, M5 Pro or M5 Max) MagSafe 3 Board - Apple Support.pdf`

That file can now be ingested into a JSON page corpus with `mare-ingest`.

## Roadmap

### v0.1

- text + image + layout routing
- weighted late fusion
- explainable retrieval output
- tests and runnable demo

### v0.2

- pluggable embedding backends
- PDF page ingestion
- OCR and caption extraction adapters
- score normalization per modality

### v0.3

- learned router
- benchmark harness for IRPAPERS-style evaluation
- cost-aware routing budgets
- reranking and cross-modal evidence aggregation

## Suggested next open-source moves

- Add adapters for FAISS, Qdrant, and Weaviate
- Add page extraction from PDFs
- Add a benchmark runner that computes Recall@k per modality
- Add a small web debug UI for route inspection

## License

MIT
