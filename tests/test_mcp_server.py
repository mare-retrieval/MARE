from __future__ import annotations

from pathlib import Path

from mare.mcp_server import ingest_pdf_tool, page_objects_tool, query_corpus_tool, query_pdf_tool
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


def test_query_corpus_tool_returns_evidence_payload(monkeypatch) -> None:
    monkeypatch.setattr("mare.mcp_server.load_corpus", lambda **kwargs: _FakeApp())

    payload = query_corpus_tool("generated/manual.json", "connect the adapter", top_k=1)

    assert payload["corpus_path"] == "generated/manual.json"
    assert payload["results"][0]["page"] == 10


def test_page_objects_tool_returns_serialized_objects(monkeypatch) -> None:
    monkeypatch.setattr("mare.mcp_server.load_corpus", lambda **kwargs: _FakeApp())

    payload = page_objects_tool("generated/manual.json", "doc-1", limit=5)

    assert payload["doc_id"] == "doc-1"
    assert payload["objects"][0]["object_type"] == "procedure"
