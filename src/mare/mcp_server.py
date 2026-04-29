from __future__ import annotations

import argparse
import inspect
import sys
from pathlib import Path
from typing import Any

from mare.api import load_corpora, load_corpus, load_pdf
from mare.integrations import hits_to_evidence_payload


def ingest_pdf_tool(
    pdf_path: str,
    output_path: str | None = None,
    reuse: bool = False,
    parser: str = "builtin",
) -> dict[str, Any]:
    app = load_pdf(pdf_path=pdf_path, output_path=output_path, reuse=reuse, parser=parser)
    return {
        "pdf_path": str(pdf_path),
        "corpus_path": str(app.corpus_path) if app.corpus_path else "",
        "document_count": len(app.documents),
        "pages": len(app.documents),
        "parser": parser,
        "source_pdf": str(app.source_pdf) if app.source_pdf else str(pdf_path),
    }


def query_pdf_tool(
    pdf_path: str,
    query: str,
    output_path: str | None = None,
    reuse: bool = False,
    parser: str = "builtin",
    top_k: int = 3,
) -> dict[str, Any]:
    app = load_pdf(pdf_path=pdf_path, output_path=output_path, reuse=reuse, parser=parser)
    hits = app.retrieve(query=query, top_k=top_k)
    payload = hits_to_evidence_payload(query=query, hits=hits)
    payload.update(
        {
            "pdf_path": str(pdf_path),
            "corpus_path": str(app.corpus_path) if app.corpus_path else "",
            "parser": parser,
        }
    )
    return payload


def query_corpus_tool(corpus_path: str, query: str, top_k: int = 3) -> dict[str, Any]:
    app = load_corpus(corpus_path=corpus_path)
    hits = app.retrieve(query=query, top_k=top_k)
    payload = hits_to_evidence_payload(query=query, hits=hits)
    payload.update({"corpus_path": str(corpus_path)})
    return payload


def query_corpora_tool(corpus_paths: list[str], query: str, top_k: int = 3) -> dict[str, Any]:
    app = load_corpora(corpus_paths=corpus_paths)
    hits = app.retrieve(query=query, top_k=top_k)
    payload = hits_to_evidence_payload(query=query, hits=hits)
    payload.update(
        {
            "corpus_paths": [str(path) for path in corpus_paths],
            "corpus_count": len(corpus_paths),
        }
    )
    return payload


def page_objects_tool(corpus_path: str, doc_id: str, limit: int = 10) -> dict[str, Any]:
    app = load_corpus(corpus_path=corpus_path)
    objects = app.get_page_objects(doc_id, limit=limit)
    return {
        "corpus_path": str(corpus_path),
        "doc_id": doc_id,
        "objects": [
            {
                "object_id": obj.object_id,
                "doc_id": obj.doc_id,
                "page": obj.page,
                "object_type": obj.object_type.value,
                "content": obj.content,
                "metadata": obj.metadata,
            }
            for obj in objects
        ],
    }


def describe_corpus_tool(corpus_path: str, page_limit: int = 5, object_limit: int = 3) -> dict[str, Any]:
    app = load_corpus(corpus_path=corpus_path)
    return app.describe_corpus(page_limit=page_limit, object_limit=object_limit)


def search_objects_tool(
    corpus_path: str,
    query: str,
    object_type: str | None = None,
    limit: int = 10,
) -> dict[str, Any]:
    app = load_corpus(corpus_path=corpus_path)
    return {
        "corpus_path": str(corpus_path),
        "query": query,
        "object_type": object_type or "",
        "results": app.search_objects(query=query, object_type=object_type, limit=limit),
    }


def create_mcp_server():
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:
        raise RuntimeError(
            "MARE MCP support requires the `mcp` package. Install it with "
            "`pip install 'mare-retrieval[mcp]'` or `pip install mcp`."
        ) from exc

    server = FastMCP("MARE")

    @server.tool()
    def ingest_pdf(
        pdf_path: str,
        output_path: str | None = None,
        reuse: bool = False,
        parser: str = "builtin",
    ) -> dict[str, Any]:
        """Ingest a PDF into a MARE corpus and return the generated corpus path and summary."""

        return ingest_pdf_tool(pdf_path=pdf_path, output_path=output_path, reuse=reuse, parser=parser)

    @server.tool()
    def query_pdf(
        pdf_path: str,
        query: str,
        output_path: str | None = None,
        reuse: bool = False,
        parser: str = "builtin",
        top_k: int = 3,
    ) -> dict[str, Any]:
        """Query a PDF directly and return grounded evidence with page, snippet, highlight, and metadata."""

        return query_pdf_tool(
            pdf_path=pdf_path,
            query=query,
            output_path=output_path,
            reuse=reuse,
            parser=parser,
            top_k=top_k,
        )

    @server.tool()
    def query_corpus(corpus_path: str, query: str, top_k: int = 3) -> dict[str, Any]:
        """Query an existing MARE corpus JSON and return grounded evidence results."""

        return query_corpus_tool(corpus_path=corpus_path, query=query, top_k=top_k)

    @server.tool()
    def query_corpora(corpus_paths: list[str], query: str, top_k: int = 3) -> dict[str, Any]:
        """Query multiple MARE corpora together and return the best grounded evidence across PDFs."""

        return query_corpora_tool(corpus_paths=corpus_paths, query=query, top_k=top_k)

    @server.tool()
    def page_objects(corpus_path: str, doc_id: str, limit: int = 10) -> dict[str, Any]:
        """List extracted document objects for a page/document entry inside a MARE corpus."""

        return page_objects_tool(corpus_path=corpus_path, doc_id=doc_id, limit=limit)

    @server.tool()
    def describe_corpus(corpus_path: str, page_limit: int = 5, object_limit: int = 3) -> dict[str, Any]:
        """Summarize a MARE corpus so an agent can understand what pages, objects, and signals exist before querying."""

        return describe_corpus_tool(corpus_path=corpus_path, page_limit=page_limit, object_limit=object_limit)

    @server.tool()
    def search_objects(
        corpus_path: str,
        query: str,
        object_type: str | None = None,
        limit: int = 10,
    ) -> dict[str, Any]:
        """Search extracted objects inside a MARE corpus using lightweight lexical matching over evidence objects."""

        return search_objects_tool(corpus_path=corpus_path, query=query, object_type=object_type, limit=limit)

    return server


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run the MARE MCP server. Use stdio when launched by an MCP client, or HTTP/SSE when you need a "
            "remote MCP endpoint for enterprise or ChatGPT/API integrations."
        )
    )
    parser.add_argument(
        "--transport",
        choices=("stdio", "http", "sse", "streamable-http"),
        default="stdio",
        help="Transport to serve. Default: stdio. Use http for a remote MCP endpoint.",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Bind host for HTTP/SSE transports")
    parser.add_argument("--port", type=int, default=8000, help="Bind port for HTTP/SSE transports")
    parser.add_argument(
        "--path",
        default="/mcp/",
        help="Endpoint path for HTTP transport. Default: /mcp/",
    )
    parser.add_argument(
        "--message-path",
        default="/messages/",
        help="Message path for SSE transport. Default: /messages/",
    )
    parser.add_argument(
        "--sse-path",
        default="/sse/",
        help="Connection path for SSE transport. Default: /sse/",
    )
    parser.add_argument(
        "--no-banner",
        action="store_true",
        help="Disable the FastMCP startup banner",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_arg_parser().parse_args(argv)
    if args.transport == "stdio" and sys.stdin.isatty() and sys.stdout.isatty():
        raise SystemExit(
            "mare-mcp defaults to stdio, which is meant to be launched by an MCP-capable client rather than run "
            "interactively in a shell.\n\n"
            "For a human-facing local evaluation flow, use `mare-workflow` or `mare-ui`.\n"
            "For a remote MCP endpoint, run `mare-mcp --transport http --host 0.0.0.0 --port 8000`.\n"
            "For local MCP clients, use the example config in examples/mcp_stdio_config.json."
        )
    server = create_mcp_server()
    run = getattr(server, "run", None)
    if run is None:
        raise RuntimeError("The installed MCP package does not expose `FastMCP.run()`. Please upgrade `mcp`.")
    run_signature = inspect.signature(run)

    def invoke_run(**kwargs: Any) -> None:
        accepted = {name: value for name, value in kwargs.items() if name in run_signature.parameters}
        run(**accepted)

    transport = args.transport
    show_banner = not args.no_banner
    settings = getattr(server, "settings", None)
    if settings is not None:
        settings.host = args.host
        settings.port = args.port
        settings.streamable_http_path = args.path.rstrip("/") or "/mcp"
        settings.sse_path = args.sse_path.rstrip("/") or "/sse"
        settings.message_path = args.message_path if args.message_path.endswith("/") else f"{args.message_path}/"
    if transport == "stdio":
        invoke_run(transport="stdio", show_banner=show_banner)
        return
    if transport in ("http", "streamable-http"):
        invoke_run(transport="streamable-http", show_banner=show_banner)
        return
    invoke_run(transport="sse", show_banner=show_banner)


__all__ = [
    "create_mcp_server",
    "describe_corpus_tool",
    "ingest_pdf_tool",
    "main",
    "page_objects_tool",
    "query_corpora_tool",
    "query_corpus_tool",
    "query_pdf_tool",
    "search_objects_tool",
]
