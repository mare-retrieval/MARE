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


_PARSER_REGISTRY: dict[str, DocumentParser] = {
    "builtin": BuiltinPDFParser(),
}


def register_parser(name: str, parser: DocumentParser) -> None:
    _PARSER_REGISTRY[name] = parser


def get_parser(name: str) -> DocumentParser:
    try:
        return _PARSER_REGISTRY[name]
    except KeyError as exc:
        available = ", ".join(sorted(_PARSER_REGISTRY))
        raise KeyError(f"Unknown parser '{name}'. Available parsers: {available}") from exc
