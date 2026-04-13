from __future__ import annotations

import math
import re
from collections import Counter

from mare.highlight import render_highlighted_page
from mare.retrievers.base import BaseRetriever
from mare.types import Modality, RetrievalHit

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
            if not overlap:
                continue

            numerator = sum(query_counts[token] * doc_counts[token] for token in overlap)
            norm = math.sqrt(sum(v * v for v in query_counts.values())) * math.sqrt(
                sum(v * v for v in doc_counts.values())
            )
            cosine_score = numerator / norm if norm else 0.0
            bm25_score = _bm25_score(query_tokens, doc_tokens, avg_doc_len)
            structure_bonus, bonus_reasons = _structure_bonus(set(query_tokens), document)
            score = (0.55 * cosine_score) + (0.25 * min(1.0, bm25_score / 8.0)) + structure_bonus
            snippet = _best_snippet(document.text, query)
            reason_parts = [f"Matched text terms: {', '.join(sorted(overlap)[:5])}"]
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
