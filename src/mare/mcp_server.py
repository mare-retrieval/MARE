from __future__ import annotations

from pathlib import Path
from typing import Any

from mare.api import load_corpus, load_pdf
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
    def page_objects(corpus_path: str, doc_id: str, limit: int = 10) -> dict[str, Any]:
        """List extracted document objects for a page/document entry inside a MARE corpus."""

        return page_objects_tool(corpus_path=corpus_path, doc_id=doc_id, limit=limit)

    return server


def main() -> None:
    server = create_mcp_server()
    run = getattr(server, "run", None)
    if run is None:
        raise RuntimeError("The installed MCP package does not expose `FastMCP.run()`. Please upgrade `mcp`.")
    run()


__all__ = [
    "create_mcp_server",
    "ingest_pdf_tool",
    "main",
    "page_objects_tool",
    "query_corpus_tool",
    "query_pdf_tool",
]
