from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class Modality(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    LAYOUT = "layout"


class ObjectType(str, Enum):
    PAGE = "page"
    PROCEDURE = "procedure"
    FIGURE = "figure"
    TABLE = "table"
    SECTION = "section"


@dataclass(frozen=True)
class RetrievalFilters:
    document_ids: tuple[str, ...] = ()
    sources: tuple[str, ...] = ()
    pages: tuple[int, ...] = ()
    object_types: tuple[str, ...] = ()
    metadata: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, value: dict | None) -> "RetrievalFilters | None":
        if not value:
            return None
        return cls(
            document_ids=tuple(str(item) for item in value.get("document_ids", [])),
            sources=tuple(str(item) for item in value.get("sources", [])),
            pages=tuple(int(item) for item in value.get("pages", [])),
            object_types=tuple(str(item) for item in value.get("object_types", [])),
            metadata={str(key): str(item) for key, item in value.get("metadata", {}).items()},
        )

    def matches(self, hit: "RetrievalHit") -> bool:
        if self.document_ids and hit.doc_id not in self.document_ids:
            return False
        if self.pages and hit.page not in self.pages:
            return False
        if self.object_types and (hit.object_type or "page").lower() not in {item.lower() for item in self.object_types}:
            return False
        if self.sources:
            source = str(hit.metadata.get("source") or hit.title)
            allowed = {item.casefold() for item in self.sources}
            if source.casefold() not in allowed and Path(source).name.casefold() not in allowed:
                return False
        for key, value in self.metadata.items():
            if str(hit.metadata.get(key, "")).casefold() != str(value).casefold():
                return False
        return True

    def as_dict(self) -> dict:
        return {
            "document_ids": list(self.document_ids),
            "sources": list(self.sources),
            "pages": list(self.pages),
            "object_types": list(self.object_types),
            "metadata": dict(self.metadata),
        }


@dataclass
class DocumentObject:
    object_id: str
    doc_id: str
    page: int
    object_type: ObjectType
    content: str
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass
class Document:
    doc_id: str
    title: str
    page: int
    text: str = ""
    image_caption: str = ""
    layout_hints: str = ""
    page_image_path: str = ""
    objects: list[DocumentObject] = field(default_factory=list)
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass
class RetrievalHit:
    doc_id: str
    title: str
    page: int
    modality: Modality
    score: float
    reason: str
    snippet: str = ""
    page_image_path: str = ""
    highlight_image_path: str = ""
    object_id: str = ""
    object_type: str = ""
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass
class QueryPlan:
    query: str
    selected_modalities: list[Modality]
    discarded_modalities: list[Modality]
    confidence: float
    intent: str
    rationale: str


@dataclass
class RetrievalExplanation:
    plan: QueryPlan
    per_modality_results: dict[Modality, list[RetrievalHit]]
    fused_results: list[RetrievalHit]
