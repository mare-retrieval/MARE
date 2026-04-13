from __future__ import annotations

import math
import re
from collections import Counter

from mare.highlight import render_highlighted_page
from mare.retrievers.base import BaseRetriever
from mare.types import DocumentObject, Modality, ObjectType, RetrievalHit

STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "how",
    "if",
    "in",
    "is",
    "it",
    "me",
    "of",
    "on",
    "or",
    "show",
    "the",
    "to",
    "what",
    "where",
    "which",
    "with",
}


def _tokenize(value: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", value.lower())


def _content_tokens(value: str) -> list[str]:
    return [token for token in _tokenize(value) if token not in STOPWORDS]


def _best_snippet(text: str, query: str, window: int = 220) -> str:
    normalized = re.sub(r"\s+", " ", text).strip()
    if not normalized:
        return ""

    query_terms = [term for term in _tokenize(query) if len(term) > 1]
    if not query_terms:
        return normalized[:window]

    lowered = normalized.lower()
    best_index = -1
    for term in query_terms:
        found = lowered.find(term)
        if found != -1:
            best_index = found if best_index == -1 else min(best_index, found)

    if best_index == -1:
        return normalized[:window]

    start = max(0, best_index - 60)
    end = min(len(normalized), start + window)
    snippet = normalized[start:end].strip()
    if start > 0:
        snippet = "..." + snippet
    if end < len(normalized):
        snippet = snippet + "..."
    return snippet


def _bm25_score(query_tokens: list[str], doc_tokens: list[str], avg_doc_len: float, k1: float = 1.5, b: float = 0.75) -> float:
    if not query_tokens or not doc_tokens:
        return 0.0

    doc_counts = Counter(doc_tokens)
    query_terms = set(query_tokens)
    doc_len = len(doc_tokens)
    score = 0.0

    for term in query_terms:
        tf = doc_counts.get(term, 0)
        if tf == 0:
            continue
        # Small local approximation: reward repeated matches without requiring a corpus-wide IDF table.
        idf = 1.0 + math.log(1 + len(term))
        numerator = tf * (k1 + 1)
        denominator = tf + k1 * (1 - b + b * (doc_len / avg_doc_len if avg_doc_len else 1.0))
        score += idf * (numerator / denominator)

    return score


def _structure_bonus(query_tokens: set[str], document) -> tuple[float, list[str]]:
    bonus = 0.0
    reasons: list[str] = []
    layout_hints = set(_tokenize(document.layout_hints))
    signals = set(_tokenize(document.metadata.get("signals", "")))

    if query_tokens & {"table", "compare", "comparison"} and ({"table", "comparison"} & (layout_hints | signals)):
        bonus += 0.2
        reasons.append("table-aware boost")

    if query_tokens & {"install", "reinstall", "remove", "loosen", "tighten", "instruction"} and (
        {"procedure", "instruction"} & signals
    ):
        bonus += 0.15
        reasons.append("procedure-aware boost")

    if query_tokens & {"figure", "diagram", "architecture"} and ({"figure"} & (layout_hints | signals)):
        bonus += 0.15
        reasons.append("figure-aware boost")

    return bonus, reasons


def _object_bonus(query_tokens: set[str], obj: DocumentObject) -> tuple[float, list[str]]:
    bonus = 0.0
    reasons: list[str] = []

    if obj.object_type == ObjectType.TABLE and query_tokens & {"table", "comparison", "compare"}:
        bonus += 0.25
        reasons.append("table-object boost")
    if obj.object_type == ObjectType.PROCEDURE and query_tokens & {
        "install",
        "reinstall",
        "remove",
        "loosen",
        "tighten",
        "step",
        "instruction",
    }:
        bonus += 0.2
        reasons.append("procedure-object boost")
    if obj.object_type == ObjectType.FIGURE and query_tokens & {"figure", "diagram", "architecture"}:
        bonus += 0.2
        reasons.append("figure-object boost")

    return bonus, reasons


def _score_object(query_tokens: list[str], obj: DocumentObject) -> tuple[float, list[str], set[str]]:
    content_tokens = _content_tokens(obj.content)
    overlap = set(query_tokens) & set(content_tokens)
    if not overlap:
        return 0.0, [], set()

    avg_len = max(len(content_tokens), 1)
    bm25_score = _bm25_score(query_tokens, content_tokens, avg_len)
    bonus, reasons = _object_bonus(set(query_tokens), obj)
    score = min(1.0, (0.45 * min(1.0, bm25_score / 6.0)) + bonus + (0.08 * len(overlap)))
    return score, reasons, overlap


def _best_object(query_tokens: list[str], objects: list[DocumentObject]) -> tuple[DocumentObject | None, float, list[str], set[str]]:
    best_object: DocumentObject | None = None
    best_score = 0.0
    best_reasons: list[str] = []
    best_overlap: set[str] = set()

    for obj in objects:
        score, reasons, overlap = _score_object(query_tokens, obj)
        if score > best_score:
            best_object = obj
            best_score = score
            best_reasons = reasons
            best_overlap = overlap

    return best_object, best_score, best_reasons, best_overlap


class TextRetriever(BaseRetriever):
    modality = Modality.TEXT

    def retrieve(self, query: str, top_k: int = 5) -> list[RetrievalHit]:
        query_tokens = _content_tokens(query)
        query_counts = Counter(query_tokens)
        avg_doc_len = sum(len(_content_tokens(document.text)) for document in self.documents) / max(len(self.documents), 1)
        hits: list[RetrievalHit] = []

        for document in self.documents:
            doc_tokens = _content_tokens(document.text)
            doc_counts = Counter(doc_tokens)
            overlap = set(query_counts) & set(doc_counts)
            best_object, object_score, object_bonus_reasons, object_overlap = _best_object(query_tokens, document.objects)
            if not overlap and not object_overlap:
                continue

            cosine_score = 0.0
            bm25_score = 0.0
            reason_parts: list[str] = []
            if overlap:
                numerator = sum(query_counts[token] * doc_counts[token] for token in overlap)
                norm = math.sqrt(sum(v * v for v in query_counts.values())) * math.sqrt(
                    sum(v * v for v in doc_counts.values())
                )
                cosine_score = numerator / norm if norm else 0.0
                bm25_score = _bm25_score(query_tokens, doc_tokens, avg_doc_len)
                reason_parts.append(f"Matched text terms: {', '.join(sorted(overlap)[:5])}")

            structure_bonus, bonus_reasons = _structure_bonus(set(query_tokens), document)
            score = (0.45 * cosine_score) + (0.2 * min(1.0, bm25_score / 8.0)) + structure_bonus + object_score
            snippet = best_object.content if best_object else _best_snippet(document.text, query)
            if best_object:
                reason_parts.append(
                    f"Best object: {best_object.object_type.value} ({', '.join(sorted(object_overlap)[:5])})"
                )
                if object_bonus_reasons:
                    reason_parts.append(f"Object boosts: {', '.join(object_bonus_reasons)}")
            if bonus_reasons:
                reason_parts.append(f"Structure boosts: {', '.join(bonus_reasons)}")
            hits.append(
                RetrievalHit(
                    doc_id=document.doc_id,
                    title=document.title,
                    page=document.page,
                    modality=self.modality,
                    score=score,
                    reason=" | ".join(reason_parts),
                    snippet=snippet,
                    page_image_path=document.page_image_path,
                    object_id=best_object.object_id if best_object else "",
                    object_type=best_object.object_type.value if best_object else "",
                    metadata=document.metadata,
                )
            )

        top_hits = sorted(hits, key=lambda hit: hit.score, reverse=True)[:top_k]
        for hit in top_hits:
            source_pdf = hit.metadata.get("source", "")
            if source_pdf and hit.page_image_path and hit.snippet:
                hit.highlight_image_path = render_highlighted_page(
                    pdf_path=source_pdf,
                    page_number=hit.page,
                    page_image_path=hit.page_image_path,
                    query=query,
                    snippet=hit.snippet,
                )

        return top_hits
