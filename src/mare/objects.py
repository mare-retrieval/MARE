from __future__ import annotations

import re

from mare.types import DocumentObject, ObjectType


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _split_sentences(text: str) -> list[str]:
    cleaned = _normalize(text)
    if not cleaned:
        return []
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+", cleaned) if part.strip()]


def _find_step_markers(page_text: str) -> list[tuple[int, str]]:
    markers: list[tuple[int, str]] = []

    # Common manual styles:
    # "1. Do this"
    # "1 Do this"
    # "2 Select Settings ..."
    patterns = [
        r"(?:^|\s)(\d{1,2})[.)]\s+",
        r"(?:^|\s)([1-9])\s+(?=[A-Z])",
    ]

    for pattern in patterns:
        for match in re.finditer(pattern, page_text):
            markers.append((match.start(1), match.group(1)))

    deduped: dict[int, str] = {}
    for start, step in sorted(markers, key=lambda item: item[0]):
        deduped.setdefault(start, step)

    return [(start, step) for start, step in deduped.items()]


def _extract_procedures(page_text: str, doc_id: str, page: int) -> list[DocumentObject]:
    matches = _find_step_markers(page_text)
    if not matches:
        return []

    objects: list[DocumentObject] = []
    for idx, (start, step_no) in enumerate(matches):
        end = matches[idx + 1][0] if idx + 1 < len(matches) else len(page_text)
        content = _normalize(page_text[start:end])
        if len(content) < 12:
            continue
        objects.append(
            DocumentObject(
                object_id=f"{doc_id}:procedure:{page}:{step_no}",
                doc_id=doc_id,
                page=page,
                object_type=ObjectType.PROCEDURE,
                content=content,
                metadata={"step": step_no},
            )
        )
    return objects


def _find_heading(text: str) -> str:
    normalized = _normalize(text)
    if not normalized:
        return ""

    candidates = [
        r"(Wake on LAN \(WOL\) feature)",
        r"(Wired LAN)",
        r"(Wireless LAN)",
        r"(Connecting the AC adapter)",
        r"(Turning off(?: on [^.]+)?)",
        r"(Turning the computer on and off)",
    ]
    for pattern in candidates:
        match = re.search(pattern, normalized, flags=re.IGNORECASE)
        if match:
            return match.group(1)

    heading_match = re.match(r"(?:[A-Za-z& ]+\s+\d+\s+)?([A-Z][A-Za-z0-9&() /+-]{6,60})", normalized)
    if heading_match:
        heading = heading_match.group(1).strip()
        if len(heading.split()) <= 10:
            return heading
    return ""


def _extract_procedure_groups(page_text: str, doc_id: str, page: int, procedure_objects: list[DocumentObject]) -> list[DocumentObject]:
    if len(procedure_objects) < 2:
        return []

    heading = _find_heading(page_text)
    if not heading:
        return []

    grouped_text = " ".join(obj.content for obj in procedure_objects)
    grouped_text = _normalize(f"{heading}. {grouped_text}")
    if len(grouped_text) < 40:
        return []

    return [
        DocumentObject(
            object_id=f"{doc_id}:procedure_group:{page}:1",
            doc_id=doc_id,
            page=page,
            object_type=ObjectType.PROCEDURE,
            content=grouped_text,
            metadata={"grouped": "true", "heading": heading},
        )
    ]


def _extract_figures(page_text: str, doc_id: str, page: int) -> list[DocumentObject]:
    objects: list[DocumentObject] = []
    for idx, sentence in enumerate(_split_sentences(page_text), start=1):
        lowered = sentence.lower()
        if re.search(r"\bfigure\b", lowered) or "fig." in lowered or re.search(r"\bdiagram\b", lowered):
            objects.append(
                DocumentObject(
                    object_id=f"{doc_id}:figure:{page}:{idx}",
                    doc_id=doc_id,
                    page=page,
                    object_type=ObjectType.FIGURE,
                    content=sentence,
                )
            )
    return objects


def _extract_tables(page_text: str, doc_id: str, page: int) -> list[DocumentObject]:
    objects: list[DocumentObject] = []
    for idx, sentence in enumerate(_split_sentences(page_text), start=1):
        lowered = sentence.lower()
        if re.search(r"\btable\b", lowered):
            objects.append(
                DocumentObject(
                    object_id=f"{doc_id}:table:{page}:{idx}",
                    doc_id=doc_id,
                    page=page,
                    object_type=ObjectType.TABLE,
                    content=sentence,
                )
            )
    return objects


def _extract_sections(page_text: str, doc_id: str, page: int) -> list[DocumentObject]:
    sentences = _split_sentences(page_text)
    if not sentences:
        return []

    chunk_size = 2
    objects: list[DocumentObject] = []
    for idx in range(0, len(sentences), chunk_size):
        content = _normalize(" ".join(sentences[idx : idx + chunk_size]))
        if len(content) < 30:
            continue
        chunk_no = (idx // chunk_size) + 1
        objects.append(
            DocumentObject(
                object_id=f"{doc_id}:section:{page}:{chunk_no}",
                doc_id=doc_id,
                page=page,
                object_type=ObjectType.SECTION,
                content=content,
            )
        )
    return objects


def extract_document_objects(page_text: str, doc_id: str, page: int) -> list[DocumentObject]:
    objects: list[DocumentObject] = []
    procedure_objects = _extract_procedures(page_text, doc_id, page)
    objects.extend(procedure_objects)
    objects.extend(_extract_procedure_groups(page_text, doc_id, page, procedure_objects))
    objects.extend(_extract_figures(page_text, doc_id, page))
    objects.extend(_extract_tables(page_text, doc_id, page))
    objects.extend(_extract_sections(page_text, doc_id, page))
    return objects
