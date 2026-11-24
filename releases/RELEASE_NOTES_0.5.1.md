# MARE 0.5.1

MARE 0.5.1 is a packaging fix for 0.5.0. Everyone should upgrade.

```bash
pip install -U "mare-retrieval[mcp]"
```

## Fixes

- **PDFs no longer crash on a clean install.** PDF ingestion renders page images and highlights with Pillow, but Pillow was only in the `dev` extra, so `pip install mare-retrieval` failed on the first PDF with `No module named 'PIL'`. Pillow is now a core dependency. This affected every release since at least 0.4.0.
- **Agents can read MCP tool errors on SDK 2.x.** MCP Python SDK 2.x hides an exception's message unless the tool raises the SDK's `ToolError`, so agents saw only "Error executing tool query_folder". Errors caused by input or setup, such as a missing folder, a path outside the allowed root, or a missing optional dependency, now reach the agent verbatim on both SDK 1.x and 2.x. Unexpected internal errors stay generic.

## Reliability

- CI now installs the built wheel into a clean environment with only its runtime dependencies and runs `mare ask` on a sample PDF, an Evidence Brief over a mixed-format folder, and `mare connect`. A missing runtime dependency now fails CI instead of a user's first run.
