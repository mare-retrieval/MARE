## MARE v0.3.0

MARE is a Python library for evidence-first PDF retrieval.

This release is a meaningful upgrade over the initial PyPI baseline. It moves MARE from a simple page-retrieval package toward a more extensible retrieval foundation for documents and developer workflows.

### Highlights

- Added highlighted evidence images for retrieved results
- Added object-aware retrieval for procedures, sections, figures, and tables
- Improved manual-oriented procedure retrieval with heading-aware grouping
- Added stronger figure and table extraction foundations
- Added region-level fallback highlighting for non-text objects
- Added a more polished Streamlit demo experience
- Added developer extension points via `MAREConfig`
- Added pluggable parser, retriever, and reranker interfaces
- Added open-source integrations:
  - `DoclingParser`
  - `UnstructuredParser`
  - `FastEmbedReranker`
  - `QdrantHybridRetriever`
- Added an advanced-stack example in `examples/advanced_stack.py`

### Install

```bash
pip install mare-retrieval
```

Optional extras:

```bash
pip install "mare-retrieval[ui]"
pip install "mare-retrieval[docling]"
pip install "mare-retrieval[unstructured]"
pip install "mare-retrieval[fastembed]"
pip install "mare-retrieval[integrations]"
```

### Notes

- Python import remains `import mare`
- GitHub repo remains `MARE`
- PyPI distribution name remains `mare-retrieval`

### Docs

- GitHub: https://github.com/mare-retrieval/MARE
- PyPI: https://pypi.org/project/mare-retrieval/
