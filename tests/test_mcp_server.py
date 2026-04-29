from __future__ import annotations

from pathlib import Path

from mare.mcp_server import (
    describe_corpus_tool,
    ingest_pdf_tool,
    ingest_pdf_url_tool,
    main,
    page_objects_tool,
    query_corpora_tool,
    query_corpus_tool,
    query_pdf_tool,
    query_pdf_url_tool,
    search_objects_tool,
)
from mare.types import Document, DocumentObject, Modality, ObjectType, RetrievalHit


class _FakeApp:
    def __init__(self, *, corpus_path: str = "generated/manual.json", source_pdf: str = "manual.pdf") -> None:
        self.corpus_path = Path(corpus_path)
        self.source_pdf = Path(source_pdf)
        self.documents = [
            Document(
                doc_id="doc-1",
                title="Manual",
                page=10,
                text="Connect the AC adapter to the laptop.",
                objects=[
                    DocumentObject(
                        object_id="doc-1:procedure:1",
                        doc_id="doc-1",
                        page=10,
                        object_type=ObjectType.PROCEDURE,
                        content="Connect the AC adapter to the laptop.",
                        metadata={},
                    )
                ],
            )
        ]

    def retrieve(self, query: str, top_k: int = 3):
        return [
            RetrievalHit(
                doc_id="doc-1",
                title="Manual",
                page=10,
                modality=Modality.TEXT,
                score=0.95,
                reason="Matched text terms: adapter",
                snippet="Connect the AC adapter to the laptop.",
                page_image_path="generated/manual/page-10.png",
                highlight_image_path="generated/manual/highlight-10.png",
                object_id="doc-1:procedure:1",
                object_type="procedure",
                metadata={"source": "manual.pdf"},
            )
        ][:top_k]

    def get_page_objects(self, doc_id: str, limit: int | None = None):
        objects = self.documents[0].objects if doc_id == "doc-1" else []
        return objects[:limit] if limit is not None else objects

    def describe_corpus(self, page_limit: int = 5, object_limit: int = 3):
        return {
            "corpus_path": str(self.corpus_path),
            "source_pdf": str(self.source_pdf),
            "title": "Manual",
            "page_count": 1,
            "document_count": 1,
            "object_counts": {"procedure": 1},
            "available_object_types": ["procedure"],
            "pages": [
                {
                    "doc_id": "doc-1",
                    "title": "Manual",
                    "page": 10,
                    "layout_hints": "",
                    "signals": "",
                    "preview_text": "Connect the AC adapter to the laptop.",
                    "object_counts": {"procedure": 1},
                    "objects": [
                        {
                            "object_id": "doc-1:procedure:1",
                            "doc_id": "doc-1",
                            "page": 10,
                            "object_type": "procedure",
                            "content": "Connect the AC adapter to the laptop.",
                            "metadata": {},
                        }
                    ][:object_limit],
                }
            ][:page_limit],
        }

    def search_objects(self, query: str, object_type: str | None = None, limit: int = 10):
        return [
            {
                "object_id": "doc-1:procedure:1",
                "doc_id": "doc-1",
                "page": 10,
                "object_type": object_type or "procedure",
                "content": "Connect the AC adapter to the laptop.",
                "metadata": {},
                "title": "Manual",
                "score": 1.0,
                "page_image_path": "generated/manual/page-10.png",
                "signals": "",
            }
        ][:limit]


def test_ingest_pdf_tool_returns_summary(monkeypatch) -> None:
    monkeypatch.setattr("mare.mcp_server.load_pdf", lambda **kwargs: _FakeApp())

    payload = ingest_pdf_tool("manual.pdf", parser="builtin")

    assert payload["pdf_path"] == "manual.pdf"
    assert payload["corpus_path"].endswith("generated/manual.json")
    assert payload["document_count"] == 1


def test_query_pdf_tool_returns_evidence_payload(monkeypatch) -> None:
    monkeypatch.setattr("mare.mcp_server.load_pdf", lambda **kwargs: _FakeApp())

    payload = query_pdf_tool("manual.pdf", "connect the adapter", top_k=1)

    assert payload["query"] == "connect the adapter"
    assert payload["results"][0]["object_type"] == "procedure"
    assert payload["results"][0]["highlight_image_path"].endswith("highlight-10.png")


def test_ingest_pdf_url_tool_downloads_then_ingests(monkeypatch, tmp_path: Path) -> None:
    download_target = tmp_path / "downloaded.pdf"
    monkeypatch.setattr("mare.mcp_server._download_pdf_url", lambda **kwargs: download_target)
    monkeypatch.setattr("mare.mcp_server.load_pdf", lambda **kwargs: _FakeApp())

    payload = ingest_pdf_url_tool("https://example.com/manual.pdf", parser="builtin")

    assert payload["pdf_url"] == "https://example.com/manual.pdf"
    assert payload["download_path"] == str(download_target)
    assert payload["document_count"] == 1


def test_query_pdf_url_tool_downloads_then_queries(monkeypatch, tmp_path: Path) -> None:
    download_target = tmp_path / "downloaded.pdf"
    monkeypatch.setattr("mare.mcp_server._download_pdf_url", lambda **kwargs: download_target)
    monkeypatch.setattr("mare.mcp_server.load_pdf", lambda **kwargs: _FakeApp())

    payload = query_pdf_url_tool("https://example.com/manual.pdf", "connect the adapter", top_k=1)

    assert payload["pdf_url"] == "https://example.com/manual.pdf"
    assert payload["download_path"] == str(download_target)
    assert payload["results"][0]["page"] == 10


def test_query_corpus_tool_returns_evidence_payload(monkeypatch) -> None:
    monkeypatch.setattr("mare.mcp_server.load_corpus", lambda **kwargs: _FakeApp())

    payload = query_corpus_tool("generated/manual.json", "connect the adapter", top_k=1)

    assert payload["corpus_path"] == "generated/manual.json"
    assert payload["results"][0]["page"] == 10


def test_query_corpora_tool_returns_evidence_payload(monkeypatch) -> None:
    monkeypatch.setattr("mare.mcp_server.load_corpora", lambda **kwargs: _FakeApp())

    payload = query_corpora_tool(["generated/manual-a.json", "generated/manual-b.json"], "connect the adapter", top_k=1)

    assert payload["corpus_count"] == 2
    assert payload["results"][0]["page"] == 10


def test_page_objects_tool_returns_serialized_objects(monkeypatch) -> None:
    monkeypatch.setattr("mare.mcp_server.load_corpus", lambda **kwargs: _FakeApp())

    payload = page_objects_tool("generated/manual.json", "doc-1", limit=5)

    assert payload["doc_id"] == "doc-1"
    assert payload["objects"][0]["object_type"] == "procedure"


def test_describe_corpus_tool_returns_summary(monkeypatch) -> None:
    monkeypatch.setattr("mare.mcp_server.load_corpus", lambda **kwargs: _FakeApp())

    payload = describe_corpus_tool("generated/manual.json", page_limit=2, object_limit=1)

    assert payload["page_count"] == 1
    assert payload["object_counts"]["procedure"] == 1
    assert payload["pages"][0]["objects"][0]["object_type"] == "procedure"


def test_search_objects_tool_returns_matching_objects(monkeypatch) -> None:
    monkeypatch.setattr("mare.mcp_server.load_corpus", lambda **kwargs: _FakeApp())

    payload = search_objects_tool("generated/manual.json", "ac adapter", object_type="procedure", limit=5)

    assert payload["query"] == "ac adapter"
    assert payload["results"][0]["object_type"] == "procedure"
    assert payload["results"][0]["score"] > 0


def test_main_exits_with_helpful_message_when_run_interactively(monkeypatch) -> None:
    class _TTY:
        def isatty(self) -> bool:
            return True

    monkeypatch.setattr("sys.stdin", _TTY())
    monkeypatch.setattr("sys.stdout", _TTY())

    try:
        main([])
    except SystemExit as exc:
        message = str(exc)
    else:
        raise AssertionError("Expected main() to exit when launched interactively.")

    assert "defaults to stdio" in message
    assert "mare-workflow" in message
    assert "examples/mcp_stdio_config.json" in message


def test_main_runs_http_transport_with_expected_defaults(monkeypatch) -> None:
    class _TTY:
        def isatty(self) -> bool:
            return True

    class _FakeServer:
        def __init__(self) -> None:
            self.calls = []
            self.settings = type(
                "Settings",
                (),
                {
                    "host": "127.0.0.1",
                    "port": 8000,
                    "streamable_http_path": "/mcp",
                    "sse_path": "/sse",
                    "message_path": "/messages/",
                    "transport_security": type(
                        "TransportSecurity",
                        (),
                        {
                            "enable_dns_rebinding_protection": True,
                            "allowed_hosts": ["127.0.0.1:*"],
                            "allowed_origins": ["http://127.0.0.1:*"],
                        },
                    )(),
                },
            )()

        def run(self, transport, mount_path=None) -> None:
            self.calls.append({"transport": transport, "mount_path": mount_path})

    fake_server = _FakeServer()
    monkeypatch.setattr("sys.stdin", _TTY())
    monkeypatch.setattr("sys.stdout", _TTY())
    monkeypatch.setattr("mare.mcp_server.create_mcp_server", lambda: fake_server)

    main(["--transport", "http", "--host", "0.0.0.0", "--port", "9000"])

    assert fake_server.calls == [
        {
            "transport": "streamable-http",
            "mount_path": None,
        }
    ]
    assert fake_server.settings.host == "0.0.0.0"
    assert fake_server.settings.port == 9000
    assert fake_server.settings.streamable_http_path == "/mcp"


def test_main_extends_allowed_hosts_and_origins(monkeypatch) -> None:
    class _TTY:
        def isatty(self) -> bool:
            return True

    class _FakeServer:
        def __init__(self) -> None:
            self.calls = []
            self.settings = type(
                "Settings",
                (),
                {
                    "host": "127.0.0.1",
                    "port": 8000,
                    "streamable_http_path": "/mcp",
                    "sse_path": "/sse",
                    "message_path": "/messages/",
                    "transport_security": type(
                        "TransportSecurity",
                        (),
                        {
                            "enable_dns_rebinding_protection": True,
                            "allowed_hosts": ["127.0.0.1:*"],
                            "allowed_origins": ["http://127.0.0.1:*"],
                        },
                    )(),
                },
            )()

        def run(self, transport, mount_path=None) -> None:
            self.calls.append({"transport": transport, "mount_path": mount_path})

    fake_server = _FakeServer()
    monkeypatch.setattr("sys.stdin", _TTY())
    monkeypatch.setattr("sys.stdout", _TTY())
    monkeypatch.setattr("mare.mcp_server.create_mcp_server", lambda: fake_server)

    main(
        [
            "--transport",
            "http",
            "--allow-host",
            "demo.ngrok-free.app:*",
            "--allow-origin",
            "https://demo.ngrok-free.app",
        ]
    )

    assert "demo.ngrok-free.app:*" in fake_server.settings.transport_security.allowed_hosts
    assert "https://demo.ngrok-free.app" in fake_server.settings.transport_security.allowed_origins
