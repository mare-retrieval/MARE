# MARE 0.5.0

MARE 0.5.0 is the Connect Your Agent release.

It makes MARE something you can plug into a coding agent in one command. It fixes several trust problems in the evidence output and makes repeat queries fast without ever answering from a stale index. Search quality is better too.

```bash
pip install -U "mare-retrieval[mcp]"
mare connect claude-code
```

## Highlights

- **`mare connect`** prints ready-to-paste MCP config for Claude Code, Claude Desktop, Cursor, VS Code, OpenAI Codex CLI, and Gemini CLI. `--write` merges MARE into the project's config file (`.mcp.json`, `.cursor/mcp.json`, `.vscode/mcp.json`, `.gemini/settings.json`) without removing other servers. The config uses the absolute path of the `mare` executable, because desktop apps do not inherit a virtualenv's `PATH`.
- **`query_folder` MCP tool.** Agents can now ask a whole folder of PDF, Markdown, text, and DOCX files in one call, with include and exclude glob patterns. It uses the same discovery and collision-safe indexing as `mare workflow --folder`.
- **MCP Python SDK 2.x support.** The 2.x SDK renamed `FastMCP` to `MCPServer`, which made `mare mcp` fail on fresh installs. MARE now works with both 1.x and 2.x. The `mcp` extra is capped at `<3`.
- **Evidence briefs quote the documents.** `--task brief` now opens with the top passages and their citations, before the diagnostics.
- **Fast, fresh indexes.** Documents are indexed once and then reused. Each index records the source path, size, modification time, SHA-256, parser, and MARE version, and MARE re-indexes automatically when any of them change. On a 149-page PDF, a repeat query drops from about 3.3 s to about 0.1 s.

## MCP

- New `query_folder` tool.
- Every tool declares MCP tool annotations (`title`, `readOnlyHint`, `destructiveHint`, `idempotentHint`, `openWorldHint`). Corpus-only tools are read-only; URL tools are open-world.
- The server sends instructions that tell agents to read `agent_contract` before answering and to quote citations.
- New `mare mcp --root PATH` sets the server's working directory. Relative paths resolve there and indexes go to `<root>/generated`, even when a desktop client launches the server from `/`.
- MCP query and ingest tools now default to `reuse=True`. This is safe because reuse is fingerprint-checked.
- Non-loopback HTTP/SSE binding requires `--allow-unauthenticated-remote`. MARE has no built-in HTTP authentication, so put it behind an authenticated proxy.
- URL ingestion is disabled on HTTP/SSE unless `--allow-remote-url-fetch` is passed.
- Proof assets are served only from `generated/` and only as image files.
- DNS-rebinding protection (Host and Origin checks) is kept on the 2.x SDK, including `--allow-host`, `--allow-origin`, and `--disable-dns-rebinding-protection`.

## Retrieval Quality

- The lexical retriever now applies light English stemming, so "unlocking", "unlocks", and "unlock" match, and "steps" matches "step".
- Corpus-level rarity weighting: terms that appear on most pages count for less than rare, specific terms. Score ranges are bounded so the support thresholds keep their meaning.
- Sections made of numbered items now count as steps for "show me the steps" style questions.
- Tokenization is cached per retriever instead of repeated for every query.
- On 30 user-style questions over a 149-page laptop manual: hit@1 rose from 0.57 to 0.67, hit@3 from 0.80 to 0.93, and MRR@5 from 0.69 to 0.79. The bundled manual and research-paper eval sets are unchanged at 1.0.

## Retrieval Controls

- Cross-surface retrieval filters for source, document ID, page, evidence type, and metadata: `--filter-source`, `--filter-doc-id`, `--filter-page`, `--filter-object-type`, `--filter-metadata KEY=VALUE`, `RetrievalFilters` in Python, and a `filters` object on MCP query tools.
- Bounded compound-query retrieval: `--decomposition-query-limit` and `--decomposition-timeout-seconds` retrieve each facet of a compound question separately and report which facets are covered and which are unsupported. The agent contract will not approve an answer while a facet lacks evidence.
- Evidence rescue runs its alternate queries in parallel within a time budget. `mare chat` exposes `--rescue-query-limit` and `--rescue-timeout-seconds`, and timeouts are reported accurately.

## Fixes

- Snippets could show a page label (for example `procedure`) instead of document text, and citation metadata could be replaced by a weaker match. Fused results now take their evidence from the strongest text match.
- Evidence rescue padded queries with generic words such as "section page requirement procedure". The inflated scores made it report an improvement while pulling in unrelated pages. Rescue now only removes conversational filler and reuses follow-up questions that share the question's key terms.
- `--reuse` could serve a stale index after a document was edited. Folder runs re-ingested every document on every run.
- Querying a saved corpus whose source PDF had moved or been deleted crashed during highlight rendering. The highlight is now skipped.
- Folder discovery loaded MARE's own `generated/` cache alongside the source documents, which counted evidence twice.
- pypdf's per-font warnings (for example "fontTools is required ...") no longer flood the output. Set `MARE_PDF_WARNINGS=1` to see them.
- Text-only sources (Markdown, text, DOCX) are no longer flagged for missing visual proof.
- Match reasons show the words the user typed instead of stems.
- Same-name documents from different folders stay distinct in multi-source retrieval.

## Upgrade Notes

- `mare workflow`, `mare chat`, and `mare ask` reuse fresh indexes by default. `--reuse` is now a no-op kept for compatibility. Use `--reindex` to force a rebuild. Indexes from earlier versions have no fingerprint and are rebuilt once.
- In Python, `load_document(..., reuse="auto")` (or `True`) reuses an index only while it is fresh. `reuse=False` still always re-ingests.
- Evidence rescue queries changed from template strings (`"exact evidence for ..."`) to keyword forms of the question. Scripts that matched on the old `retrieval_query` strings need updating.
- Lexical scores changed with stemming and rarity weighting. Compare stacks with `mare-eval` if you depend on specific score values.
- Remote MCP deployments must add `--allow-unauthenticated-remote` for non-loopback binds, and `--allow-remote-url-fetch` to keep URL ingestion.

## Reliability

- Tests: 222, run on Python 3.9 through 3.13 and against both MCP SDK 1.x and 2.x.
- GitHub Actions run on Ubuntu 24.04 with Node 24 action releases.
- Public builds fail if internal skill files are tracked or packaged.
