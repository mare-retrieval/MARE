from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from mare.demo import load_documents
from mare.engine import MAREngine
from mare.extensions import DocumentParser, MAREConfig, get_parser
from mare.types import Document, DocumentObject, RetrievalExplanation, RetrievalHit


@dataclass
class MAREApp:
    documents: list[Document]
    corpus_path: Path | None = None
    source_pdf: Path | None = None
    config: MAREConfig = field(default_factory=MAREConfig)
    engine: MAREngine = field(init=False)

    def __post_init__(self) -> None:
        self.engine = MAREngine(self.documents, config=self.config)

    @classmethod
    def from_documents(cls, documents: list[Document], config: MAREConfig | None = None) -> "MAREApp":
        return cls(documents=documents, config=config or MAREConfig())

    @classmethod
    def from_corpus(cls, corpus_path: str | Path, config: MAREConfig | None = None) -> "MAREApp":
        path = Path(corpus_path)
        documents = load_documents(path)
        return cls(documents=documents, corpus_path=path, config=config or MAREConfig())

    @classmethod
    def from_pdf(
        cls,
        pdf_path: str | Path,
        output_path: str | Path | None = None,
        reuse: bool = False,
        parser: str | DocumentParser | None = None,
        config: MAREConfig | None = None,
    ) -> "MAREApp":
        pdf_file = Path(pdf_path)
        corpus_path = Path(output_path) if output_path is not None else Path("generated") / f"{pdf_file.stem}.json"
        corpus_path.parent.mkdir(parents=True, exist_ok=True)
        resolved_config = config or MAREConfig()
        parser_instance = parser or resolved_config.parser or "builtin"
        if isinstance(parser_instance, str):
            parser_instance = get_parser(parser_instance)

        if not reuse or not corpus_path.exists():
            parser_instance.ingest(pdf_path=pdf_file, output_path=corpus_path)

        documents = load_documents(corpus_path)
        return cls(documents=documents, corpus_path=corpus_path, source_pdf=pdf_file, config=resolved_config)

    def explain(self, query: str, top_k: int = 3) -> RetrievalExplanation:
        return self.engine.explain(query, top_k=top_k)

    def retrieve(self, query: str, top_k: int = 3) -> list[RetrievalHit]:
        return self.engine.retrieve(query, top_k=top_k)

    def best_match(self, query: str, top_k: int = 3) -> RetrievalHit | None:
        results = self.retrieve(query=query, top_k=top_k)
        return results[0] if results else None

    def get_document(self, doc_id: str) -> Document | None:
        for document in self.documents:
            if document.doc_id == doc_id:
                return document
        return None

    def get_page_objects(self, doc_id: str, limit: int | None = None) -> list[DocumentObject]:
        document = self.get_document(doc_id)
        if not document:
            return []
        objects = document.objects
        return objects[:limit] if limit is not None else objects

    def as_langchain_retriever(self, top_k: int = 3):
        from mare.integrations import create_langchain_retriever

        return create_langchain_retriever(self, top_k=top_k)

    def as_langgraph_tool(self, top_k: int = 3, name: str = "mare_retrieve", description: str | None = None):
        from mare.integrations import create_langgraph_tool

        return create_langgraph_tool(self, top_k=top_k, name=name, description=description)

    def as_llamaindex_retriever(self, top_k: int = 3):
        from mare.integrations import create_llamaindex_retriever

        return create_llamaindex_retriever(self, top_k=top_k)


def load_corpus(corpus_path: str | Path, config: MAREConfig | None = None) -> MAREApp:
    return MAREApp.from_corpus(corpus_path, config=config)


def load_pdf(
    pdf_path: str | Path,
    output_path: str | Path | None = None,
    reuse: bool = False,
    parser: str | DocumentParser | None = None,
    config: MAREConfig | None = None,
) -> MAREApp:
    return MAREApp.from_pdf(pdf_path=pdf_path, output_path=output_path, reuse=reuse, parser=parser, config=config)
