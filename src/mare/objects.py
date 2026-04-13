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


def _extract_procedures(page_text: str, doc_id: str, page: int) -> list[DocumentObject]:
    matches = list(re.finditer(r"(?:^|\s)(\d+)\.\s+", page_text))
    if not matches:
        return []

    objects: list[DocumentObject] = []
    for idx, match in enumerate(matches):
        step_no = match.group(1)
        start = match.start(1)
        end = matches[idx + 1].start(1) if idx + 1 < len(matches) else len(page_text)
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
    objects.extend(_extract_procedures(page_text, doc_id, page))
    objects.extend(_extract_figures(page_text, doc_id, page))
    objects.extend(_extract_tables(page_text, doc_id, page))
    objects.extend(_extract_sections(page_text, doc_id, page))
    return objects
