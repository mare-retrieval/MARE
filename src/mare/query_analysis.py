from __future__ import annotations

import re


_QUESTION_START = r"what|which|who|when|where|why|how|does|do|is|are|can|should|must|compare|list|find|show|explain"


def decompose_query(query: str, *, limit: int = 3) -> list[str]:
    """Split an explicitly compound question into bounded retrieval facets.

    The splitter is deliberately conservative: it handles sentence boundaries,
    semicolons, and conjunctions that introduce another question. Ordinary noun
    phrases such as "tables and figures" remain intact.
    """
    if limit <= 1:
        return []
    normalized = " ".join(query.split()).strip()
    if not normalized:
        return []

    marked = re.sub(
        rf"\s+(?:and|also)\s+(?=(?:{_QUESTION_START})\b)",
        " | ",
        normalized,
        flags=re.IGNORECASE,
    )
    parts = [part.strip(" ,?.") for part in re.split(r"\s*[;?]\s*|\s+\|\s+", marked) if part.strip(" ,?.")]

    if len(parts) < 2:
        comparison = re.match(r"^compare\s+(.+?)\s+(?:with|versus|vs\.?)\s+(.+?)[?.]*$", normalized, re.IGNORECASE)
        if comparison:
            parts = [comparison.group(1).strip(" ,?."), comparison.group(2).strip(" ,?.")]

    if len(parts) < 2:
        return []

    facets: list[str] = []
    seen: set[str] = set()
    for part in parts:
        cleaned = " ".join(part.split())
        key = cleaned.casefold()
        if not cleaned or key in seen:
            continue
        seen.add(key)
        facets.append(cleaned)
        if len(facets) >= limit:
            break
    return facets if len(facets) >= 2 else []
