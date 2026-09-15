from __future__ import annotations

import argparse
import hashlib
import ipaddress
import inspect
import socket
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from mare.api import load_corpora, load_corpus, load_document, load_pdf
from mare.integrations import hits_to_evidence_payload

_PUBLIC_BASE_URL = ""
_MEDIA_PATH = "/media"
_RESTRICT_LOCAL_PATHS = False
_DOWNLOAD_TIMEOUT_SECONDS = 20
_MAX_DOWNLOAD_BYTES = 25 * 1024 * 1024


def _safe_download_dir() -> Path:
    path = Path("generated") / "downloads"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _require_allowed_local_path(path: str | Path) -> Path:
    candidate = Path(path).expanduser().resolve()
    if _RESTRICT_LOCAL_PATHS and not candidate.is_relative_to(Path.cwd().resolve()):
        raise ValueError("Remote MCP file access is restricted to the server working directory.")
    return candidate


def _validate_public_http_url(url: str) -> urllib.parse.ParseResult:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("pdf_url must use http or https.")
    if not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("pdf_url must contain a public host and must not include credentials.")

    try:
        addresses = {
            item[4][0]
            for item in socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80))
        }
    except socket.gaierror as exc:
        raise ValueError("pdf_url host could not be resolved.") from exc
    if not addresses:
        raise ValueError("pdf_url host could not be resolved.")
    for address in addresses:
        try:
            resolved = ipaddress.ip_address(address.split("%", 1)[0])
        except ValueError as exc:
            raise ValueError("pdf_url resolved to an invalid address.") from exc
        if not resolved.is_global:
            raise ValueError("pdf_url must not resolve to a private, loopback, link-local, or reserved address.")
    return parsed


class _SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _validate_public_http_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _download_pdf_url(pdf_url: str, download_path: str | None = None) -> Path:
    parsed = _validate_public_http_url(pdf_url)

    if download_path:
        target = _require_allowed_local_path(download_path)
    else:
        name = Path(parsed.path).name or "downloaded.pdf"
        if not name.lower().endswith(".pdf"):
            name = f"{name}.pdf"
        digest = hashlib.sha1(pdf_url.encode("utf-8")).hexdigest()[:10]
        stem = Path(name).stem or "downloaded"
        target = _safe_download_dir() / f"{stem}-{digest}.pdf"

    target.parent.mkdir(parents=True, exist_ok=True)
    opener = urllib.request.build_opener(_SafeRedirectHandler())
    request = urllib.request.Request(pdf_url, headers={"User-Agent": "mare-retrieval"})
    with opener.open(request, timeout=_DOWNLOAD_TIMEOUT_SECONDS) as response:
        _validate_public_http_url(response.geturl())
        declared_length = response.headers.get("Content-Length")
        if declared_length and int(declared_length) > _MAX_DOWNLOAD_BYTES:
            raise ValueError("PDF download exceeds the 25 MiB limit.")
        payload = response.read(_MAX_DOWNLOAD_BYTES + 1)
    if len(payload) > _MAX_DOWNLOAD_BYTES:
        raise ValueError("PDF download exceeds the 25 MiB limit.")
    if not payload.startswith(b"%PDF-"):
        raise ValueError("Downloaded content is not a PDF.")
    target.write_bytes(payload)
    return target


def _normalize_public_base_url(url: str) -> str:
    return url.rstrip("/")


def _normalize_media_path(path: str) -> str:
    trimmed = (path or "/media").strip()
    if not trimmed.startswith("/"):
        trimmed = f"/{trimmed}"
    return trimmed.rstrip("/") or "/media"


def _asset_url(path: str) -> str:
    if not _PUBLIC_BASE_URL or not path:
        return ""
    asset_path = Path(path)
    try:
        relative = asset_path.resolve().relative_to(Path.cwd().resolve())
    except ValueError:
        return ""
    quoted = urllib.parse.quote(relative.as_posix())
    return f"{_PUBLIC_BASE_URL}{_MEDIA_PATH}/{quoted}"


def _attach_remote_asset_urls(payload: dict[str, Any]) -> dict[str, Any]:
    proof_assets: list[dict[str, Any]] = []
    for result in payload.get("results", []):
        page_path = str(result.get("page_image_path") or "")
        highlight_path = str(result.get("highlight_image_path") or "")
        result["page_image_url"] = _asset_url(page_path)
        result["highlight_image_url"] = _asset_url(highlight_path)
        proof_assets.append(
            {
                "citation": result.get("citation") or "",
                "page": result.get("page"),
                "source_document": str(result.get("metadata", {}).get("source") or result.get("title") or ""),
                "page_image_path": page_path,
                "highlight_image_path": highlight_path,
                "page_image_url": result["page_image_url"],
                "highlight_image_url": result["highlight_image_url"],
            }
        )
    payload["proof_assets"] = proof_assets
    payload["primary_proof_asset"] = proof_assets[0] if proof_assets else {}
    payload["best_evidence"] = {
        "query": payload.get("query") or "",
        "citation": "",
        "snippet": "",
        "page": None,
        "source_document": "",
        "page_image_url": "",
        "highlight_image_url": "",
    }
    if payload.get("results"):
        best = payload["results"][0]
        payload["best_evidence"] = {
            "query": payload.get("query") or "",
            "citation": best.get("citation") or "",
            "snippet": best.get("snippet") or "",
            "page": best.get("page"),
            "source_document": str(best.get("metadata", {}).get("source") or best.get("title") or ""),
            "page_image_url": best.get("page_image_url") or "",
            "highlight_image_url": best.get("highlight_image_url") or "",
        }
    payload["proof_links"] = {
        "page_image_url": payload["best_evidence"].get("page_image_url") or "",
        "highlight_image_url": payload["best_evidence"].get("highlight_image_url") or "",
    }
    return payload


def ingest_pdf_tool(
    pdf_path: str,
    output_path: str | None = None,
    reuse: bool = False,
    parser: str = "builtin",
) -> dict[str, Any]:
    _require_allowed_local_path(pdf_path)
    if output_path:
        _require_allowed_local_path(output_path)
    app = load_pdf(pdf_path=pdf_path, output_path=output_path, reuse=reuse, parser=parser)
    return {
        "pdf_path": str(pdf_path),
        "corpus_path": str(app.corpus_path) if app.corpus_path else "",
        "document_count": len(app.documents),
        "pages": len(app.documents),
        "parser": parser,
        "source_pdf": str(app.source_pdf) if app.source_pdf else str(pdf_path),
    }


def ingest_document_tool(
    document_path: str,
    output_path: str | None = None,
    reuse: bool = False,
    parser: str = "builtin",
) -> dict[str, Any]:
    _require_allowed_local_path(document_path)
    if output_path:
        _require_allowed_local_path(output_path)
    app = load_document(source_path=document_path, output_path=output_path, reuse=reuse, parser=parser)
    return {
        "document_path": str(document_path),
        "corpus_path": str(app.corpus_path) if app.corpus_path else "",
        "document_count": len(app.documents),
        "pages": len(app.documents),
        "parser": parser,
        "source_document": str(app.source_document) if app.source_document else str(document_path),
    }


def query_pdf_tool(
    pdf_path: str,
    query: str,
    output_path: str | None = None,
    reuse: bool = False,
    parser: str = "builtin",
    top_k: int = 3,
) -> dict[str, Any]:
    _require_allowed_local_path(pdf_path)
    if output_path:
        _require_allowed_local_path(output_path)
    app = load_pdf(pdf_path=pdf_path, output_path=output_path, reuse=reuse, parser=parser)
    hits = app.retrieve(query=query, top_k=top_k)
    payload = hits_to_evidence_payload(query=query, hits=hits)
    _attach_remote_asset_urls(payload)
    payload.update(
        {
            "pdf_path": str(pdf_path),
            "corpus_path": str(app.corpus_path) if app.corpus_path else "",
            "parser": parser,
        }
    )
    return payload


def query_document_tool(
    document_path: str,
    query: str,
    output_path: str | None = None,
    reuse: bool = False,
    parser: str = "builtin",
    top_k: int = 3,
) -> dict[str, Any]:
    _require_allowed_local_path(document_path)
    if output_path:
        _require_allowed_local_path(output_path)
    app = load_document(source_path=document_path, output_path=output_path, reuse=reuse, parser=parser)
    hits = app.retrieve(query=query, top_k=top_k)
    payload = hits_to_evidence_payload(query=query, hits=hits)
    _attach_remote_asset_urls(payload)
    payload.update(
        {
            "document_path": str(document_path),
            "corpus_path": str(app.corpus_path) if app.corpus_path else "",
            "parser": parser,
        }
    )
    return payload


def ingest_pdf_url_tool(
    pdf_url: str,
    output_path: str | None = None,
    download_path: str | None = None,
    reuse: bool = False,
    parser: str = "builtin",
) -> dict[str, Any]:
    local_pdf = _download_pdf_url(pdf_url=pdf_url, download_path=download_path)
    payload = ingest_pdf_tool(
        pdf_path=str(local_pdf),
        output_path=output_path,
        reuse=reuse,
        parser=parser,
    )
    payload.update({"pdf_url": pdf_url, "download_path": str(local_pdf)})
    return payload


def query_pdf_url_tool(
    pdf_url: str,
    query: str,
    output_path: str | None = None,
    download_path: str | None = None,
    reuse: bool = False,
    parser: str = "builtin",
    top_k: int = 3,
) -> dict[str, Any]:
    local_pdf = _download_pdf_url(pdf_url=pdf_url, download_path=download_path)
    payload = query_pdf_tool(
        pdf_path=str(local_pdf),
        query=query,
        output_path=output_path,
        reuse=reuse,
        parser=parser,
        top_k=top_k,
    )
    payload.update({"pdf_url": pdf_url, "download_path": str(local_pdf)})
    return payload


def query_corpus_tool(corpus_path: str, query: str, top_k: int = 3) -> dict[str, Any]:
    _require_allowed_local_path(corpus_path)
    app = load_corpus(corpus_path=corpus_path)
    hits = app.retrieve(query=query, top_k=top_k)
    payload = hits_to_evidence_payload(query=query, hits=hits)
    _attach_remote_asset_urls(payload)
    payload.update({"corpus_path": str(corpus_path)})
    return payload


def query_corpora_tool(corpus_paths: list[str], query: str, top_k: int = 3) -> dict[str, Any]:
    for corpus_path in corpus_paths:
        _require_allowed_local_path(corpus_path)
    app = load_corpora(corpus_paths=corpus_paths)
    hits = app.retrieve(query=query, top_k=top_k)
    payload = hits_to_evidence_payload(query=query, hits=hits)
    _attach_remote_asset_urls(payload)
    payload.update(
        {
            "corpus_paths": [str(path) for path in corpus_paths],
            "corpus_count": len(corpus_paths),
        }
    )
    return payload


def page_objects_tool(corpus_path: str, doc_id: str, limit: int = 10) -> dict[str, Any]:
    _require_allowed_local_path(corpus_path)
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
    _require_allowed_local_path(corpus_path)
    app = load_corpus(corpus_path=corpus_path)
    return app.describe_corpus(page_limit=page_limit, object_limit=object_limit)


def search_objects_tool(
    corpus_path: str,
    query: str,
    object_type: str | None = None,
    limit: int = 10,
) -> dict[str, Any]:
    _require_allowed_local_path(corpus_path)
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
        from starlette.responses import FileResponse, PlainTextResponse
    except ImportError as exc:
        raise RuntimeError(
            "MARE MCP support requires the `mcp` package. Install it with "
            "`pip install 'mare-retrieval[mcp]'` or `pip install mcp`."
        ) from exc

    server = FastMCP("MARE")

    @server.custom_route(f"{_MEDIA_PATH}/{{asset_path:path}}", methods=["GET"])
    async def media_asset(request):
        asset_path = request.path_params.get("asset_path", "")
        requested = (asset_path or "").lstrip("/")
        candidate = (Path.cwd() / requested).resolve()
        cwd = Path.cwd().resolve()
        if not candidate.is_relative_to(cwd):
            return PlainTextResponse("Forbidden", status_code=403)
        if not candidate.is_file():
            return PlainTextResponse("Not Found", status_code=404)
        return FileResponse(candidate)

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
    def ingest_document(
        document_path: str,
        output_path: str | None = None,
        reuse: bool = False,
        parser: str = "builtin",
    ) -> dict[str, Any]:
        """Ingest a source document into a MARE corpus and return the generated corpus path and summary."""

        return ingest_document_tool(document_path=document_path, output_path=output_path, reuse=reuse, parser=parser)

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
    def query_document(
        document_path: str,
        query: str,
        output_path: str | None = None,
        reuse: bool = False,
        parser: str = "builtin",
        top_k: int = 3,
    ) -> dict[str, Any]:
        """Query a source document directly and return grounded evidence with snippet, proof metadata, and assets when available."""

        return query_document_tool(
            document_path=document_path,
            query=query,
            output_path=output_path,
            reuse=reuse,
            parser=parser,
            top_k=top_k,
        )

    @server.tool()
    def ingest_pdf_url(
        pdf_url: str,
        output_path: str | None = None,
        download_path: str | None = None,
        reuse: bool = False,
        parser: str = "builtin",
    ) -> dict[str, Any]:
        """Download a PDF from an HTTP(S) URL, ingest it into a MARE corpus, and return the generated corpus path."""

        return ingest_pdf_url_tool(
            pdf_url=pdf_url,
            output_path=output_path,
            download_path=download_path,
            reuse=reuse,
            parser=parser,
        )

    @server.tool()
    def query_pdf_url(
        pdf_url: str,
        query: str,
        output_path: str | None = None,
        download_path: str | None = None,
        reuse: bool = False,
        parser: str = "builtin",
        top_k: int = 3,
    ) -> dict[str, Any]:
        """Download a PDF from an HTTP(S) URL, then return grounded evidence with page, snippet, highlight, and metadata."""

        return query_pdf_url_tool(
            pdf_url=pdf_url,
            query=query,
            output_path=output_path,
            download_path=download_path,
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
    parser.add_argument(
        "--allow-host",
        action="append",
        default=[],
        help="Additional allowed Host header pattern for remote MCP traffic, e.g. abc123.ngrok-free.app:*",
    )
    parser.add_argument(
        "--allow-origin",
        action="append",
        default=[],
        help="Additional allowed Origin pattern for remote MCP traffic, e.g. https://abc123.ngrok-free.app",
    )
    parser.add_argument(
        "--disable-dns-rebinding-protection",
        action="store_true",
        help="Disable FastMCP host/origin protection. Use only for controlled local testing.",
    )
    parser.add_argument(
        "--public-base-url",
        default="",
        help="Public HTTPS base URL for remote asset links, e.g. https://abc123.ngrok-free.app",
    )
    parser.add_argument(
        "--media-path",
        default="/media/",
        help="HTTP path used to serve generated proof assets. Default: /media/",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    global _PUBLIC_BASE_URL, _MEDIA_PATH, _RESTRICT_LOCAL_PATHS
    args = build_arg_parser().parse_args(argv)
    _PUBLIC_BASE_URL = _normalize_public_base_url(args.public_base_url)
    _MEDIA_PATH = _normalize_media_path(args.media_path)
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
    _RESTRICT_LOCAL_PATHS = transport != "stdio"
    show_banner = not args.no_banner
    settings = getattr(server, "settings", None)
    if settings is not None:
        settings.host = args.host
        settings.port = args.port
        settings.streamable_http_path = args.path.rstrip("/") or "/mcp"
        settings.sse_path = args.sse_path.rstrip("/") or "/sse"
        settings.message_path = args.message_path if args.message_path.endswith("/") else f"{args.message_path}/"
        transport_security = getattr(settings, "transport_security", None)
        if transport_security is not None:
            if args.disable_dns_rebinding_protection:
                transport_security.enable_dns_rebinding_protection = False
            for host_pattern in args.allow_host:
                if host_pattern not in transport_security.allowed_hosts:
                    transport_security.allowed_hosts.append(host_pattern)
            for origin_pattern in args.allow_origin:
                if origin_pattern not in transport_security.allowed_origins:
                    transport_security.allowed_origins.append(origin_pattern)
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
    "ingest_pdf_url_tool",
    "main",
    "page_objects_tool",
    "query_corpora_tool",
    "query_corpus_tool",
    "query_pdf_tool",
    "query_pdf_url_tool",
    "search_objects_tool",
]
