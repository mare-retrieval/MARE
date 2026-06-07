from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re
from typing import Any

from mare.demo import load_documents
from mare.engine import MAREngine
from mare.extensions import DocumentParser, MAREConfig, get_parser, resolve_runtime_config
from mare.types import Document, DocumentObject, RetrievalExplanation, RetrievalHit


@dataclass
class MAREApp:
    documents: list[Document]
    corpus_path: Path | None = None
    corpus_paths: list[Path] = field(default_factory=list)
    source_document: Path | None = None
    source_documents: list[Path] = field(default_factory=list)
    source_pdf: Path | None = None
    source_pdfs: list[Path] = field(default_factory=list)
    config: MAREConfig = field(default_factory=MAREConfig)
    engine: MAREngine = field(init=False)

    def __post_init__(self) -> None:
        if self.corpus_path and not self.corpus_paths:
            self.corpus_paths = [self.corpus_path]
        if self.source_document and not self.source_documents:
            self.source_documents = [self.source_document]
        if self.source_pdf and not self.source_pdfs:
            self.source_pdfs = [self.source_pdf]
        if self.source_pdfs and not self.source_documents:
            self.source_documents = list(self.source_pdfs)
        if self.source_documents and not self.source_pdfs:
            self.source_pdfs = list(self.source_documents)
        if self.source_pdfs and not self.source_pdf and len(self.source_pdfs) == 1:
            self.source_pdf = self.source_pdfs[0]
        if self.source_documents and not self.source_document and len(self.source_documents) == 1:
            self.source_document = self.source_documents[0]
        self.engine = MAREngine(self.documents, config=self.config)

    @classmethod
    def from_documents(cls, documents: list[Document], config: MAREConfig | None = None) -> "MAREApp":
        return cls(documents=documents, config=config or MAREConfig())

    @classmethod
    def from_corpus(cls, corpus_path: str | Path, config: MAREConfig | None = None) -> "MAREApp":
        path = Path(corpus_path)
        documents = load_documents(path)
        source_documents = cls._source_documents_from_documents(documents)
        primary_source = source_documents[0] if len(source_documents) == 1 else None
        return cls(
            documents=documents,
            corpus_path=path,
            corpus_paths=[path],
            source_document=primary_source,
            source_documents=source_documents,
            source_pdf=primary_source,
            source_pdfs=source_documents,
            config=config or MAREConfig(),
        )

    @classmethod
    def from_corpora(cls, corpus_paths: list[str | Path], config: MAREConfig | None = None) -> "MAREApp":
        paths = [Path(path) for path in corpus_paths]
        documents: list[Document] = []
        for path in paths:
            documents.extend(load_documents(path))
        source_documents = cls._source_documents_from_documents(documents)
        primary_source = source_documents[0] if len(source_documents) == 1 else None
        return cls(
            documents=documents,
            corpus_paths=paths,
            source_document=primary_source,
            source_documents=source_documents,
            source_pdf=primary_source,
            source_pdfs=source_documents,
            config=config or MAREConfig(),
        )

    @classmethod
    def from_document(
        cls,
        source_path: str | Path,
        output_path: str | Path | None = None,
        reuse: bool = False,
        parser: str | DocumentParser | None = None,
        config: MAREConfig | None = None,
    ) -> "MAREApp":
        source_file = Path(source_path)
        corpus_path = Path(output_path) if output_path is not None else Path("generated") / f"{source_file.stem}.json"
        corpus_path.parent.mkdir(parents=True, exist_ok=True)
        resolved_config = config or MAREConfig()
        parser_instance = _resolve_parser(source_file, parser or resolved_config.parser or "builtin")

        if not reuse or not corpus_path.exists():
            parser_instance.ingest(source_file, corpus_path)

        documents = load_documents(corpus_path)
        return cls(
            documents=documents,
            corpus_path=corpus_path,
            source_document=source_file,
            source_documents=[source_file],
            source_pdf=source_file,
            source_pdfs=[source_file],
            config=resolved_config,
        )

    @classmethod
    def from_pdf(
        cls,
        pdf_path: str | Path,
        output_path: str | Path | None = None,
        reuse: bool = False,
        parser: str | DocumentParser | None = None,
        config: MAREConfig | None = None,
    ) -> "MAREApp":
        return cls.from_document(
            source_path=pdf_path,
            output_path=output_path,
            reuse=reuse,
            parser=parser,
            config=config,
        )

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

    def describe_corpus(self, page_limit: int = 5, object_limit: int = 3) -> dict[str, Any]:
        object_counts: dict[str, int] = {}
        pages: list[dict[str, Any]] = []

        for document in self.documents:
            page_object_counts: dict[str, int] = {}
            for obj in document.objects:
                object_name = obj.object_type.value
                object_counts[object_name] = object_counts.get(object_name, 0) + 1
                page_object_counts[object_name] = page_object_counts.get(object_name, 0) + 1

            if len(pages) < page_limit:
                pages.append(
                    {
                        "doc_id": document.doc_id,
                        "title": document.title,
                        "page": document.page,
                        "layout_hints": document.layout_hints,
                        "signals": document.metadata.get("signals", ""),
                        "preview_text": self._preview_text(document.text),
                        "object_counts": page_object_counts,
                        "objects": [
                            self._serialize_object(obj)
                            for obj in document.objects[:object_limit]
                        ],
                    }
                )

        return {
            "corpus_path": str(self.corpus_path) if self.corpus_path else "",
            "corpus_paths": [str(path) for path in self.corpus_paths],
            "corpus_count": len(self.corpus_paths) if self.corpus_paths else (1 if self.corpus_path else 0),
            "source_document": str(self.source_document) if self.source_document else "",
            "source_documents": [str(path) for path in self.source_documents],
            "source_pdf": str(self.source_pdf) if self.source_pdf else "",
            "source_pdfs": [str(path) for path in self.source_pdfs],
            "title": self.documents[0].title if self.documents else "",
            "page_count": len(self.documents),
            "document_count": len(self.documents),
            "object_counts": object_counts,
            "available_object_types": sorted(object_counts),
            "pages": pages,
        }

    def search_objects(
        self,
        query: str,
        object_type: str | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []

        normalized_object_type = object_type.lower() if object_type else None
        matches: list[tuple[float, DocumentObject, Document]] = []

        for document in self.documents:
            for obj in document.objects:
                if normalized_object_type and obj.object_type.value != normalized_object_type:
                    continue

                content = obj.content.lower()
                label = obj.metadata.get("label", "").lower()
                overlap = sum(1 for token in query_tokens if token in content or token in label)
                if overlap == 0:
                    continue

                score = overlap / max(len(query_tokens), 1)
                if label:
                    score += 0.2 * sum(1 for token in query_tokens if token in label)
                matches.append((score, obj, document))

        matches.sort(key=lambda item: (-item[0], item[1].page, item[1].object_id))
        return [
            {
                **self._serialize_object(obj),
                "title": document.title,
                "score": round(score, 4),
                "page_image_path": document.page_image_path,
                "signals": document.metadata.get("signals", ""),
            }
            for score, obj, document in matches[:limit]
        ]

    def as_langchain_retriever(self, top_k: int = 3):
        from mare.integrations import create_langchain_retriever

        return create_langchain_retriever(self, top_k=top_k)

    def as_langchain_tool(self, top_k: int = 3, name: str = "mare_retrieve", description: str | None = None):
        from mare.integrations import create_langchain_tool

        return create_langchain_tool(self, top_k=top_k, name=name, description=description)

    def as_langgraph_tool(self, top_k: int = 3, name: str = "mare_retrieve", description: str | None = None):
        from mare.integrations import create_langgraph_tool

        return create_langgraph_tool(self, top_k=top_k, name=name, description=description)

    def as_llamaindex_retriever(self, top_k: int = 3):
        from mare.integrations import create_llamaindex_retriever

        return create_llamaindex_retriever(self, top_k=top_k)

    def as_llamaindex_tool(self, top_k: int = 3, name: str = "mare_retrieve", description: str | None = None):
        from mare.integrations import create_llamaindex_tool

        return create_llamaindex_tool(self, top_k=top_k, name=name, description=description)

    @staticmethod
    def _preview_text(text: str, limit: int = 220) -> str:
        compact = " ".join(text.split())
        if len(compact) <= limit:
            return compact
        return compact[: limit - 1].rstrip() + "…"

    @staticmethod
    def _serialize_object(obj: DocumentObject) -> dict[str, Any]:
        return {
            "object_id": obj.object_id,
            "doc_id": obj.doc_id,
            "page": obj.page,
            "object_type": obj.object_type.value,
            "content": obj.content,
            "metadata": obj.metadata,
        }

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        return re.findall(r"[a-z0-9]+", text.lower())

    @staticmethod
    def _source_documents_from_documents(documents: list[Document]) -> list[Path]:
        seen: set[str] = set()
        paths: list[Path] = []
        for document in documents:
            source = document.metadata.get("source", "")
            if source and source not in seen:
                seen.add(source)
                paths.append(Path(source))
        return paths


def _resolve_parser(source_path: Path, parser: str | DocumentParser) -> DocumentParser:
    if not isinstance(parser, str):
        return parser
    if parser == "builtin":
        suffix = source_path.suffix.lower()
        if suffix in {".md", ".markdown", ".txt"}:
            return get_parser("text")
        if suffix == ".docx":
            return get_parser("docx")
    return get_parser(parser)


def load_corpus(corpus_path: str | Path, config: MAREConfig | None = None) -> MAREApp:
    return MAREApp.from_corpus(corpus_path, config=resolve_runtime_config(config))


def load_corpora(corpus_paths: list[str | Path], config: MAREConfig | None = None) -> MAREApp:
    return MAREApp.from_corpora(corpus_paths, config=resolve_runtime_config(config))


def load_pdf(
    pdf_path: str | Path,
    output_path: str | Path | None = None,
    reuse: bool = False,
    parser: str | DocumentParser | None = None,
    config: MAREConfig | None = None,
) -> MAREApp:
    return MAREApp.from_pdf(
        pdf_path=pdf_path,
        output_path=output_path,
        reuse=reuse,
        parser=parser,
        config=resolve_runtime_config(config),
    )


def load_document(
    source_path: str | Path,
    output_path: str | Path | None = None,
    reuse: bool = False,
    parser: str | DocumentParser | None = None,
    config: MAREConfig | None = None,
) -> MAREApp:
    return MAREApp.from_document(
        source_path=source_path,
        output_path=output_path,
        reuse=reuse,
        parser=parser,
        config=resolve_runtime_config(config),
    )
