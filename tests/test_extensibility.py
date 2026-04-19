from __future__ import annotations

import json
from pathlib import Path

from mare import IdentityReranker, KeywordBoostReranker, MAREApp
from mare.extensions import MAREConfig, get_parser
from mare.retrievers.base import BaseRetriever
from mare.types import Document, Modality, RetrievalHit


class _CustomParser:
    def ingest(self, pdf_path: Path, output_path: Path) -> Path:
        payload = {
            "source_pdf": str(pdf_path),
            "documents": [
                {
                    "doc_id": "custom-p1",
                    "title": "Custom",
                    "page": 1,
                    "text": "Custom parser output for setup instructions.",
                    "image_caption": "",
                    "layout_hints": "",
                    "page_image_path": "",
                    "objects": [],
                    "metadata": {"source": str(pdf_path)},
                }
            ],
        }
        output_path.write_text(json.dumps(payload))
        return output_path


class _AlwaysTopTextRetriever(BaseRetriever):
    modality = Modality.TEXT

    def retrieve(self, query: str, top_k: int = 5) -> list[RetrievalHit]:
        return [
            RetrievalHit(
                doc_id="override-1",
                title="Override",
                page=9,
                modality=self.modality,
                score=0.99,
                reason=f"Custom retriever handled: {query}",
                snippet="Overridden retrieval result.",
            )
        ][:top_k]


class _ReverseReranker:
    def rerank(self, query: str, hits: list[RetrievalHit], top_k: int = 5) -> list[RetrievalHit]:
        return list(reversed(hits))[:top_k]


def test_custom_parser_can_build_a_corpus(tmp_path: Path) -> None:
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_text("placeholder")
    output_path = tmp_path / "sample.json"

    app = MAREApp.from_pdf(pdf_path=pdf_path, output_path=output_path, parser=_CustomParser())

    assert app.documents[0].doc_id == "custom-p1"
    assert app.documents[0].text.startswith("Custom parser output")


def test_custom_retriever_factory_can_override_default_retrieval() -> None:
    docs = [Document(doc_id="base-1", title="Base", page=1, text="Base document text.")]
    config = MAREConfig(retriever_factories={Modality.TEXT: lambda documents: _AlwaysTopTextRetriever(documents)})

    app = MAREApp.from_documents(docs, config=config)
    best = app.best_match("anything")

    assert best is not None
    assert best.doc_id == "override-1"
    assert "Custom retriever handled" in best.reason


def test_custom_reranker_can_reorder_fused_results() -> None:
    docs = [
        Document(doc_id="1", title="Doc1", page=1, text="adapter instructions and setup"),
        Document(doc_id="2", title="Doc2", page=2, text="adapter instructions and setup"),
    ]
    config = MAREConfig(reranker=_ReverseReranker())

    app = MAREApp.from_documents(docs, config=config)
    results = app.retrieve("adapter instructions", top_k=2)

    assert len(results) == 2
    assert results[0].doc_id == "2"


def test_builtin_parsers_are_discoverable() -> None:
    assert get_parser("builtin") is not None
    assert get_parser("docling") is not None
    assert get_parser("unstructured") is not None


def test_identity_reranker_preserves_order() -> None:
    hits = [
        RetrievalHit(doc_id="1", title="A", page=1, modality=Modality.TEXT, score=0.9, reason="a"),
        RetrievalHit(doc_id="2", title="B", page=2, modality=Modality.TEXT, score=0.8, reason="b"),
    ]
    reranked = IdentityReranker().rerank("adapter", hits, top_k=2)

    assert [hit.doc_id for hit in reranked] == ["1", "2"]


def test_keyword_boost_reranker_prefers_label_overlap() -> None:
    hits = [
        RetrievalHit(
            doc_id="1",
            title="Table",
            page=1,
            modality=Modality.TEXT,
            score=0.6,
            reason="table result",
            snippet="comparison baseline",
            metadata={"label": "Table 2"},
        ),
        RetrievalHit(
            doc_id="2",
            title="Section",
            page=2,
            modality=Modality.TEXT,
            score=0.6,
            reason="plain result",
            snippet="plain text",
        ),
    ]
    reranked = KeywordBoostReranker().rerank("comparison table", hits, top_k=2)

    assert reranked[0].doc_id == "1"
