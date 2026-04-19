from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Protocol

from mare.ingest import ingest_pdf
from mare.retrievers.base import BaseRetriever
from mare.types import Modality, RetrievalHit


class DocumentParser(Protocol):
    """Build or update a MARE corpus from a source document."""

    def ingest(self, pdf_path: Path, output_path: Path) -> Path:
        """Return the path to the generated corpus file."""


class ResultReranker(Protocol):
    """Optional second-stage reranker for fused results."""

    def rerank(self, query: str, hits: list[RetrievalHit], top_k: int = 5) -> list[RetrievalHit]:
        """Return reranked hits, usually on a small candidate set."""


RetrieverFactory = Callable[[list], BaseRetriever]


@dataclass
class MAREConfig:
    parser: str | DocumentParser | None = None
    retriever_factories: dict[Modality, RetrieverFactory] = field(default_factory=dict)
    reranker: ResultReranker | None = None


class BuiltinPDFParser:
    """Default local parser that uses MARE's built-in PDF ingestion."""

    def ingest(self, pdf_path: Path, output_path: Path) -> Path:
        ingest_pdf(pdf_path=pdf_path, output_path=output_path)
        return output_path


class DoclingParser:
    """Placeholder adapter for Docling-backed parsing.

    This keeps MARE's parser interface stable while letting developers wire in
    richer OCR/layout/table extraction when Docling is available in their env.
    """

    def ingest(self, pdf_path: Path, output_path: Path) -> Path:
        raise RuntimeError(
            "DoclingParser is an integration stub. Install/configure Docling in your environment and "
            "implement this adapter to emit a MARE-compatible corpus."
        )


class UnstructuredParser:
    """Placeholder adapter for Unstructured-backed parsing."""

    def ingest(self, pdf_path: Path, output_path: Path) -> Path:
        raise RuntimeError(
            "UnstructuredParser is an integration stub. Install/configure Unstructured in your environment and "
            "implement this adapter to emit a MARE-compatible corpus."
        )


class IdentityReranker:
    """No-op reranker useful as a baseline or composition default."""

    def rerank(self, query: str, hits: list[RetrievalHit], top_k: int = 5) -> list[RetrievalHit]:
        return hits[:top_k]


class KeywordBoostReranker:
    """Small built-in reranker that rewards exact term overlap and metadata labels."""

    def rerank(self, query: str, hits: list[RetrievalHit], top_k: int = 5) -> list[RetrievalHit]:
        query_terms = set(query.lower().split())
        rescored: list[tuple[float, RetrievalHit]] = []
        for hit in hits:
            label_terms = set(str(hit.metadata.get("label", "")).lower().split())
            text_terms = set((hit.snippet or hit.reason or "").lower().split())
            overlap = len(query_terms & (label_terms | text_terms))
            rescored.append((hit.score + (0.03 * overlap), hit))

        rescored.sort(key=lambda item: item[0], reverse=True)
        reranked: list[RetrievalHit] = []
        for score, hit in rescored[:top_k]:
            hit.score = round(score, 4)
            reranked.append(hit)
        return reranked


_PARSER_REGISTRY: dict[str, DocumentParser] = {
    "builtin": BuiltinPDFParser(),
    "docling": DoclingParser(),
    "unstructured": UnstructuredParser(),
}


def register_parser(name: str, parser: DocumentParser) -> None:
    _PARSER_REGISTRY[name] = parser


def get_parser(name: str) -> DocumentParser:
    try:
        return _PARSER_REGISTRY[name]
    except KeyError as exc:
        available = ", ".join(sorted(_PARSER_REGISTRY))
        raise KeyError(f"Unknown parser '{name}'. Available parsers: {available}") from exc
