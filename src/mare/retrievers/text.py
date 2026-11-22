from __future__ import annotations

import math
import re
from collections import Counter

from mare.highlight import render_highlighted_page, render_object_region_highlight
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

SYNONYM_GROUPS = (
    {"attach", "connect", "hook", "insert", "plug"},
    {"compare", "comparison", "differences", "vs", "versus"},
    {"configure", "configuration", "set", "setup"},
    {"instruction", "instructions", "procedure", "procedures", "step", "steps"},
    {"chart", "matrix", "table", "tables"},
    {"caution", "risk", "risks", "warning", "warnings"},
)

_VOWELS = set("aeiouy")


def _stem(token: str) -> str:
    """Light, dependency-free English suffix stripping.

    Maps common inflections onto one form so "unlocking", "unlocks", and "unlock" match,
    and "steps" matches "step". It is intentionally conservative: short tokens, numbers,
    and words without a vowel left in the stem are returned unchanged.
    """
    if len(token) <= 3 or not token.isalpha():
        return token
    stem = token
    if stem.endswith("ies") and len(stem) > 4:
        stem = stem[:-3] + "y"
    elif stem.endswith("sses"):
        stem = stem[:-2]
    elif stem.endswith("ing") and len(stem) > 5:
        stem = stem[:-3]
    elif stem.endswith("ed") and len(stem) > 4 and not stem.endswith("eed"):
        stem = stem[:-2]
    elif stem.endswith("s") and not stem.endswith(("ss", "us", "is")):
        stem = stem[:-1]
    if stem != token and not _VOWELS & set(stem):
        return token
    if len(stem) > 3 and stem[-1] == stem[-2] and stem[-1] not in "lsz":
        stem = stem[:-1]
    if stem.endswith("e") and len(stem) > 4:
        stem = stem[:-1]
    return stem


def _stem_set(words) -> set[str]:
    return {_stem(word) for word in words}


SYNONYM_LOOKUP: dict[str, set[str]] = {}
for _group in SYNONYM_GROUPS:
    _stemmed_group = _stem_set(_group)
    for _token in _stemmed_group:
        SYNONYM_LOOKUP.setdefault(_token, set()).update(_stemmed_group - {_token})

_TABLE_QUERY = _stem_set({"table", "compare", "comparison"})
_PROCEDURE_QUERY = _stem_set({"install", "reinstall", "remove", "loosen", "tighten", "instruction"})
_STEP_QUERY = _stem_set({"step", "procedure", "instruction"})
_PROCEDURE_OBJECT_QUERY = _PROCEDURE_QUERY | _STEP_QUERY
_NUMBERED_LIST = re.compile(r"(?:^|\s)\d+[.)]\s+\S")
_FIGURE_QUERY = _stem_set({"figure", "diagram", "architecture"})


def _tokenize(value: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", value.lower())


def _content_tokens(value: str) -> list[str]:
    return [_stem(token) for token in _tokenize(value) if token not in STOPWORDS]


def _display_terms(terms, query: str, limit: int = 5) -> str:
    """Show matched terms as the user typed them ("charging"), not as stems ("charg")."""
    originals: dict[str, str] = {}
    for word in _tokenize(query):
        if word not in STOPWORDS:
            originals.setdefault(_stem(word), word)
    return ", ".join(sorted(originals.get(term, term) for term in terms)[:limit])


def _query_terms_for_snippet(query: str) -> list[str]:
    terms: list[str] = []
    for term in _tokenize(query):
        if len(term) <= 1 or term in STOPWORDS:
            continue
        for variant in (term, _stem(term)):
            if variant not in terms:
                terms.append(variant)
        for alias in sorted(SYNONYM_LOOKUP.get(_stem(term), ())):
            if alias not in terms:
                terms.append(alias)
    return terms


def _alias_matches(query_tokens: list[str], content_tokens: list[str]) -> dict[str, str]:
    content_set = set(content_tokens)
    matches: dict[str, str] = {}
    for token in query_tokens:
        if token in content_set:
            continue
        aliases = SYNONYM_LOOKUP.get(token, set())
        alias_overlap = sorted(content_set & aliases)
        if alias_overlap:
            matches[token] = alias_overlap[0]
    return matches


def _best_snippet(text: str, query: str, window: int = 220) -> str:
    normalized = re.sub(r"\s+", " ", text).strip()
    if not normalized:
        return ""

    query_terms = _query_terms_for_snippet(query)
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


def _bm25_score(
    query_tokens: list[str],
    doc_tokens: list[str],
    avg_doc_len: float,
    k1: float = 1.5,
    b: float = 0.75,
    rarity: dict[str, float] | None = None,
) -> float:
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
        # Length-based base weight keeps scores in the range support thresholds expect;
        # corpus rarity (when known) discounts terms that appear on most pages.
        idf = (1.0 + math.log(1 + len(term))) * _term_weight(term, rarity)
        numerator = tf * (k1 + 1)
        denominator = tf + k1 * (1 - b + b * (doc_len / avg_doc_len if avg_doc_len else 1.0))
        score += idf * (numerator / denominator)

    return score


def _term_weight(term: str, rarity: dict[str, float] | None) -> float:
    """Weight in [0.35, 1.0]: 1.0 for rare terms, lower for terms on most pages."""
    if not rarity:
        return 1.0
    return 0.35 + 0.65 * rarity.get(term, 1.0)


def _corpus_rarity(document_counts: list[Counter]) -> dict[str, float]:
    """Normalized inverse document frequency per term, in [0, 1].

    Corpora with fewer than three pages cannot tell rare from common terms, so every
    term is treated as rare there and scoring matches the unweighted behavior.
    """
    total = len(document_counts)
    if total < 3:
        return {}
    frequency: Counter = Counter()
    for counts in document_counts:
        frequency.update(counts.keys())
    scale = math.log(total)
    return {term: max(0.0, math.log(total / df) / scale) for term, df in frequency.items()}


def _structure_bonus(query_tokens: set[str], document) -> tuple[float, list[str]]:
    bonus = 0.0
    reasons: list[str] = []
    layout_hints = set(_tokenize(document.layout_hints))
    signals = set(_tokenize(document.metadata.get("signals", "")))

    if query_tokens & _TABLE_QUERY and ({"table", "comparison"} & (layout_hints | signals)):
        bonus += 0.2
        reasons.append("table-aware boost")

    if query_tokens & (_PROCEDURE_QUERY | _STEP_QUERY) and ({"procedure", "instruction"} & signals):
        bonus += 0.15
        reasons.append("procedure-aware boost")

    if query_tokens & _FIGURE_QUERY and ({"figure"} & (layout_hints | signals)):
        bonus += 0.15
        reasons.append("figure-aware boost")

    return bonus, reasons


def _object_bonus(query_tokens: set[str], obj: DocumentObject) -> tuple[float, list[str]]:
    bonus = 0.0
    reasons: list[str] = []
    label_tokens = set(_content_tokens(obj.metadata.get("label", "")))

    if obj.object_type == ObjectType.TABLE and query_tokens & _TABLE_QUERY:
        bonus += 0.25
        reasons.append("table-object boost")
        if int(obj.metadata.get("columns_estimate", "1")) >= 3:
            bonus += 0.08
            reasons.append("multi-column table boost")
    if obj.object_type == ObjectType.PROCEDURE and query_tokens & _PROCEDURE_OBJECT_QUERY:
        bonus += 0.2
        reasons.append("procedure-object boost")
    elif query_tokens & _STEP_QUERY and len(_NUMBERED_LIST.findall(obj.content)) >= 2:
        # A section made of numbered items is the steps a "show me the steps" question wants.
        bonus += 0.2
        reasons.append("numbered-steps boost")
    if obj.metadata.get("grouped") == "true":
        heading_tokens = set(_content_tokens(obj.metadata.get("heading", "")))
        if query_tokens & heading_tokens:
            bonus += 0.3
            reasons.append("grouped-heading boost")
    if obj.object_type == ObjectType.FIGURE and query_tokens & _FIGURE_QUERY:
        bonus += 0.2
        reasons.append("figure-object boost")
    if label_tokens and query_tokens & label_tokens:
        bonus += 0.08
        reasons.append("label overlap boost")

    return bonus, reasons


def _best_query_phrase_bonus(query_tokens: list[str], content: str) -> tuple[float, list[str]]:
    if len(query_tokens) < 2:
        return 0.0, []

    normalized_content = " ".join(_content_tokens(content))
    best_len = 0
    for start in range(len(query_tokens)):
        for end in range(start + 2, len(query_tokens) + 1):
            phrase = " ".join(query_tokens[start:end])
            if phrase and phrase in normalized_content:
                best_len = max(best_len, end - start)

    if best_len == 0:
        return 0.0, []
    return min(0.2, 0.05 * best_len), [f"phrase match x{best_len}"]


def _score_object(
    query_tokens: list[str], obj: DocumentObject, rarity: dict[str, float] | None = None
) -> tuple[float, list[str], set[str]]:
    content_tokens = _content_tokens(obj.content)
    overlap = set(query_tokens) & set(content_tokens)
    alias_matches = _alias_matches(query_tokens, content_tokens)
    if not overlap and not alias_matches:
        return 0.0, [], set()

    avg_len = max(len(content_tokens), 1)
    bm25_score = _bm25_score(query_tokens, content_tokens, avg_len, rarity=rarity)
    bonus, reasons = _object_bonus(set(query_tokens), obj)
    phrase_bonus, phrase_reasons = _best_query_phrase_bonus(query_tokens, obj.content)
    density_bonus = min(0.18, (len(overlap) + (0.65 * len(alias_matches))) / max(len(content_tokens), 1))
    conciseness_bonus = min(0.12, 12 / max(len(content_tokens), 12))
    alias_bonus = min(0.15, 0.05 * len(alias_matches))
    if alias_matches:
        reasons.append(
            "alias matches: " + ", ".join(f"{query}->{matched}" for query, matched in sorted(alias_matches.items()))
        )
    score = min(
        1.0,
        (0.35 * min(1.0, bm25_score / 6.0)) + bonus + phrase_bonus + density_bonus + conciseness_bonus + alias_bonus,
    )
    return score, reasons + phrase_reasons, overlap


def _best_object(
    query_tokens: list[str], objects: list[DocumentObject], rarity: dict[str, float] | None = None
) -> tuple[DocumentObject | None, float, list[str], set[str]]:
    best_object: DocumentObject | None = None
    best_score = 0.0
    best_reasons: list[str] = []
    best_overlap: set[str] = set()

    for obj in objects:
        score, reasons, overlap = _score_object(query_tokens, obj, rarity)
        if score > best_score:
            best_object = obj
            best_score = score
            best_reasons = reasons
            best_overlap = overlap

    return best_object, best_score, best_reasons, best_overlap


class TextRetriever(BaseRetriever):
    modality = Modality.TEXT

    def __init__(self, documents) -> None:
        super().__init__(documents)
        self._index: tuple[list[list[str]], list[Counter], float, dict[str, float]] | None = None

    def _ensure_index(self) -> tuple[list[list[str]], list[Counter], float, dict[str, float]]:
        # Tokenize once per retriever instead of once per query.
        if self._index is None:
            tokens = [_content_tokens(document.text) for document in self.documents]
            counts = [Counter(item) for item in tokens]
            avg_len = sum(len(item) for item in tokens) / max(len(tokens), 1)
            self._index = (tokens, counts, avg_len, _corpus_rarity(counts))
        return self._index

    def retrieve(self, query: str, top_k: int = 5) -> list[RetrievalHit]:
        query_tokens = _content_tokens(query)
        query_counts = Counter(query_tokens)
        all_tokens, all_counts, avg_doc_len, rarity = self._ensure_index()
        hits: list[RetrievalHit] = []

        for document, doc_tokens, doc_counts in zip(self.documents, all_tokens, all_counts):
            overlap = set(query_counts) & set(doc_counts)
            alias_matches = _alias_matches(query_tokens, doc_tokens)
            best_object, object_score, object_bonus_reasons, object_overlap = _best_object(
                query_tokens, document.objects, rarity
            )
            if not overlap and not alias_matches and not object_overlap:
                continue

            cosine_score = 0.0
            bm25_score = 0.0
            reason_parts: list[str] = []
            if overlap:
                # Rarity-weighted cosine: shared common words count for less than shared rare ones.
                numerator = sum(
                    query_counts[token] * doc_counts[token] * _term_weight(token, rarity) for token in overlap
                )
                norm = math.sqrt(
                    sum((v * _term_weight(t, rarity)) ** 2 for t, v in query_counts.items())
                ) * math.sqrt(sum(v * v for v in doc_counts.values()))
                cosine_score = numerator / norm if norm else 0.0
                bm25_score = _bm25_score(query_tokens, doc_tokens, avg_doc_len, rarity=rarity)
                reason_parts.append(f"Matched text terms: {_display_terms(overlap, query)}")
            if alias_matches:
                reason_parts.append(
                    "Alias matches: " + ", ".join(f"{query}->{matched}" for query, matched in sorted(alias_matches.items()))
                )

            structure_bonus, bonus_reasons = _structure_bonus(set(query_tokens), document)
            alias_bonus = min(0.18, 0.06 * len(alias_matches))
            score = (0.45 * cosine_score) + (0.2 * min(1.0, bm25_score / 8.0)) + structure_bonus + object_score + alias_bonus
            snippet = best_object.content if best_object else _best_snippet(document.text, query)
            hit_metadata = dict(document.metadata)
            if best_object:
                reason_parts.append(
                    f"Best object: {best_object.object_type.value} ({_display_terms(object_overlap, query)})"
                )
                if object_bonus_reasons:
                    reason_parts.append(f"Object boosts: {', '.join(object_bonus_reasons)}")
                hit_metadata.update(best_object.metadata)
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
                    metadata=hit_metadata,
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
            if not hit.highlight_image_path and hit.page_image_path and hit.object_type in {"table", "figure", "section"}:
                hit.highlight_image_path = render_object_region_highlight(
                    page_image_path=hit.page_image_path,
                    page_number=hit.page,
                    object_type=hit.object_type,
                    metadata=hit.metadata,
                )

        return top_hits
