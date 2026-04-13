from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


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
