from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from mare.demo import load_documents
from mare.engine import MAREngine
from mare.ingest import ingest_pdf
from mare.types import Document, RetrievalExplanation, RetrievalHit


@dataclass
class MAREApp:
    documents: list[Document]
    corpus_path: Path | None = None
    source_pdf: Path | None = None
    engine: MAREngine = field(init=False)

    def __post_init__(self) -> None:
        self.engine = MAREngine(self.documents)

    @classmethod
    def from_documents(cls, documents: list[Document]) -> "MAREApp":
        return cls(documents=documents)

    @classmethod
    def from_corpus(cls, corpus_path: str | Path) -> "MAREApp":
        path = Path(corpus_path)
        documents = load_documents(path)
        return cls(documents=documents, corpus_path=path)

    @classmethod
    def from_pdf(
        cls,
        pdf_path: str | Path,
        output_path: str | Path | None = None,
        reuse: bool = False,
    ) -> "MAREApp":
        pdf_file = Path(pdf_path)
        corpus_path = Path(output_path) if output_path is not None else Path("generated") / f"{pdf_file.stem}.json"
        corpus_path.parent.mkdir(parents=True, exist_ok=True)

        if not reuse or not corpus_path.exists():
            ingest_pdf(pdf_path=pdf_file, output_path=corpus_path)

        documents = load_documents(corpus_path)
        return cls(documents=documents, corpus_path=corpus_path, source_pdf=pdf_file)

    def explain(self, query: str, top_k: int = 3) -> RetrievalExplanation:
        return self.engine.explain(query, top_k=top_k)

    def retrieve(self, query: str, top_k: int = 3) -> list[RetrievalHit]:
        return self.engine.retrieve(query, top_k=top_k)

    def best_match(self, query: str, top_k: int = 3) -> RetrievalHit | None:
        results = self.retrieve(query=query, top_k=top_k)
        return results[0] if results else None


def load_corpus(corpus_path: str | Path) -> MAREApp:
    return MAREApp.from_corpus(corpus_path)


def load_pdf(pdf_path: str | Path, output_path: str | Path | None = None, reuse: bool = False) -> MAREApp:
    return MAREApp.from_pdf(pdf_path=pdf_path, output_path=output_path, reuse=reuse)
