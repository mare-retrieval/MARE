## MARE v0.4.2

MARE `v0.4.2` turns the project into a more cohesive product surface.

This release is about making MARE easier to understand, easier to try, and easier to treat like one system instead of a set of disconnected entrypoints.

### Highlights

- Added a unified product CLI:
  - `mare --help`
  - `mare ui`
  - `mare chat`
  - `mare ask`
  - `mare workflow`
  - `mare ingest`
  - `mare eval`
  - `mare mcp`
- Added a simple document-agent experience:
  - `mare chat --folder ./docs`
  - ask questions over a folder of PDFs
  - get source file, page, snippet, highlight path, and retrieval reason
- Made the visual playground easier to launch:
  - `mare ui`
  - no need to remember the raw Streamlit command
- Improved first-run onboarding and landing-page clarity:
  - one-product README structure
  - visual-first quickstart
  - clearer “which interface should I use?” guidance
  - clearer generated evidence file locations
- Improved MCP/Create App readiness:
  - remote MCP transport support
  - compatibility with older FastMCP SDK signatures
  - host/origin allowlist support for tunneled testing
  - URL-based PDF MCP tools:
    - `ingest_pdf_url`
    - `query_pdf_url`

### Why this release matters

Earlier releases made MARE technically stronger.

`v0.4.2` makes MARE feel more like a product:

- one front door
- one mental model
- multiple usage modes on top of the same evidence-first engine

The intended shape is now much clearer:

```text
mare
  -> ui
  -> chat
  -> workflow
  -> mcp
```

That means new users can understand MARE faster, while developers and agent builders still get the deeper integration layers underneath.

### Install

```bash
pip install mare-retrieval
```

Visual playground:

```bash
pip install "mare-retrieval[ui]"
mare ui
```

Simple document-agent loop:

```bash
mare chat --folder ./docs
```

### Notes

- Python import remains `import mare`
- GitHub repo remains `MARE`
- PyPI distribution name remains `mare-retrieval`
- `mare ui` and `mare chat` are now the clearest first-use entrypoints
- `mare mcp` remains the protocol-facing integration path for agent platforms and remote app workflows

### Docs

- GitHub: https://github.com/mare-retrieval/MARE
- PyPI: https://pypi.org/project/mare-retrieval/
