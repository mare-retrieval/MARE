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


def _split_lines(text: str) -> list[str]:
    lines = [line.strip() for line in text.splitlines()]
    return [line for line in lines if line]


def _region_hint(index: int, total: int) -> str:
    if total <= 0:
        return "unknown"
    ratio = index / total
    if ratio < 0.33:
        return "top"
    if ratio < 0.67:
        return "middle"
    return "bottom"


def _estimate_columns(line: str) -> int:
    if "|" in line:
        return max(2, len([part for part in line.split("|") if part.strip()]))
    if "\t" in line:
        return max(2, len([part for part in line.split("\t") if part.strip()]))

    parts = [part for part in re.split(r"\s{2,}", line) if part.strip()]
    if len(parts) >= 2:
        return len(parts)

    return 1


def _is_probable_caption(line: str) -> bool:
    lowered = line.lower()
    return bool(
        re.match(r"^(figure|fig\.|diagram)\s*\d*", lowered)
        or lowered.startswith("table ")
        or lowered.startswith("fig. ")
    )


def _is_tabular_line(line: str) -> bool:
    lowered = line.lower()
    if re.match(r"^table\s+\d+", lowered):
        return True
    if "|" in line or "\t" in line:
        return True
    if re.search(r"\S\s{2,}\S", line) and _estimate_columns(line) >= 3:
        return True
    return False


def _collect_block(lines: list[str], start_index: int, predicate) -> tuple[list[str], int]:
    block: list[str] = []
    index = start_index
    while index < len(lines) and predicate(lines[index]):
        block.append(lines[index])
        index += 1
    return block, index


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
    lines = _split_lines(page_text)
    if lines:
        for idx, line in enumerate(lines, start=1):
            lowered = line.lower()
            if not (
                re.match(r"^(figure|fig\.|diagram)\s*\d*", lowered)
                or re.search(r"\bfigure\b", lowered)
                or re.search(r"\bdiagram\b", lowered)
            ):
                continue

            block = [line]
            if idx < len(lines):
                next_line = lines[idx]
                if next_line and not _is_probable_caption(next_line) and not _is_tabular_line(next_line):
                    block.append(next_line)

            label_match = re.match(r"^((?:figure|fig\.|diagram)\s*\d*)", lowered)
            label = label_match.group(1) if label_match else "figure"
            objects.append(
                DocumentObject(
                    object_id=f"{doc_id}:figure:{page}:{idx}",
                    doc_id=doc_id,
                    page=page,
                    object_type=ObjectType.FIGURE,
                    content=_normalize(" ".join(block)),
                    metadata={
                        "label": label.title(),
                        "region_hint": _region_hint(idx - 1, len(lines)),
                        "block_lines": str(len(block)),
                    },
                )
            )
        if objects:
            return objects

    for idx, sentence in enumerate(_split_sentences(page_text), start=1):
        lowered = sentence.lower()
        if re.search(r"\bfigure\b", lowered) or "fig." in lowered or re.search(r"\bdiagram\b", lowered):
            label_match = re.search(r"((?:figure|fig\.|diagram)\s*\d*)", sentence, flags=re.IGNORECASE)
            label = label_match.group(1) if label_match else "figure"
            objects.append(
                DocumentObject(
                    object_id=f"{doc_id}:figure:{page}:{idx}",
                    doc_id=doc_id,
                    page=page,
                    object_type=ObjectType.FIGURE,
                    content=sentence,
                    metadata={"label": label.title(), "region_hint": "unknown", "block_lines": "1"},
                )
            )
    return objects


def _extract_tables(page_text: str, doc_id: str, page: int) -> list[DocumentObject]:
    objects: list[DocumentObject] = []
    lines = _split_lines(page_text)
    if lines:
        index = 0
        object_no = 1
        while index < len(lines):
            line = lines[index]
            if not _is_tabular_line(line):
                index += 1
                continue

            start_index = index
            block, index = _collect_block(lines, index, _is_tabular_line)
            if not block:
                continue

            content = _normalize(" ".join(block))
            if len(content) < 20:
                continue

            label_match = re.match(r"^(table\s*\d*)", block[0], flags=re.IGNORECASE)
            label = label_match.group(1).title() if label_match else "Table"
            max_columns = max(_estimate_columns(item) for item in block)
            if not label_match and (len(block) < 2 or max_columns < 3):
                continue
            objects.append(
                DocumentObject(
                    object_id=f"{doc_id}:table:{page}:{object_no}",
                    doc_id=doc_id,
                    page=page,
                    object_type=ObjectType.TABLE,
                    content=content,
                    metadata={
                        "label": label,
                        "region_hint": _region_hint(start_index, len(lines)),
                        "columns_estimate": str(max_columns),
                        "block_lines": str(len(block)),
                    },
                )
            )
            object_no += 1
        if objects:
            return objects

    for idx, sentence in enumerate(_split_sentences(page_text), start=1):
        lowered = sentence.lower()
        if re.match(r"^\s*table\s*\d+", lowered):
            label_match = re.search(r"(table\s*\d*)", sentence, flags=re.IGNORECASE)
            label = label_match.group(1).title() if label_match else "Table"
            objects.append(
                DocumentObject(
                    object_id=f"{doc_id}:table:{page}:{idx}",
                    doc_id=doc_id,
                    page=page,
                    object_type=ObjectType.TABLE,
                    content=sentence,
                    metadata={"label": label, "region_hint": "unknown", "columns_estimate": "1", "block_lines": "1"},
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
