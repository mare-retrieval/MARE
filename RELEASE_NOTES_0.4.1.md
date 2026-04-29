## MARE v0.4.1

MARE `v0.4.1` is a focused follow-up release that tightens the agent and app integration story introduced in `v0.4.0`.

The goal of this release is simple:

- make MCP usage clearer for developers
- make remote MCP deployment more practical
- make ChatGPT/Create App style integrations less brittle
- keep the human-facing and agent-facing entrypoints easier to evaluate

### Highlights

- Added a human-friendly workflow CLI:
  - `mare-workflow`
  - supports single-PDF, corpus, and multi-PDF evaluation
  - supports pretty terminal output and structured JSON payloads
- Improved `mare-mcp` usability:
  - clearer guidance when run interactively
  - safer stdio messaging
  - remote MCP transport support
- Added compatibility fixes for older `FastMCP` SDK versions:
  - older `run()` signatures
  - older streamable HTTP transport behavior
- Added remote host/origin allowlist support for tunneling and remote MCP testing
  - useful for `ngrok` and similar workflows
- Added URL-based MCP PDF tools for remote app platforms:
  - `ingest_pdf_url`
  - `query_pdf_url`
  - lets the MARE server fetch PDFs over HTTP(S) instead of depending on local file paths from another runtime
- Improved MCP and publishing docs:
  - clearer interface guidance for `mare-ui`, `mare-workflow`, and `mare-mcp`
  - clearer PyPI trusted publisher setup guidance

### Why this release matters

`v0.4.0` established MARE as a stronger PDF evidence layer for developers and agents.

`v0.4.1` makes that layer easier to:

- test locally
- expose remotely
- connect to app platforms
- evaluate in a more enterprise-friendly way

The core idea stays the same:

```text
user question -> agent/app -> MARE -> page + snippet + highlight + proof
```

This release improves the operational path around that architecture.

### Install

```bash
pip install mare-retrieval
```

Useful extras:

```bash
pip install "mare-retrieval[ui]"
pip install "mare-retrieval[mcp]"
```

### Notes

- Python import remains `import mare`
- GitHub repo remains `MARE`
- PyPI distribution name remains `mare-retrieval`
- `mare-workflow` is now the recommended terminal entrypoint for human and enterprise evaluation
- `mare-mcp` remains the protocol-facing entrypoint for MCP-capable clients and remote app integrations

### Docs

- GitHub: https://github.com/mare-retrieval/MARE
- PyPI: https://pypi.org/project/mare-retrieval/
