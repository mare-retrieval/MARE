from __future__ import annotations

import hashlib
import re
from pathlib import Path


def _require_pypdfium2():
    try:
        import pypdfium2 as pdfium
    except ImportError as exc:
        raise RuntimeError("pypdfium2 is required for evidence highlighting.") from exc
    return pdfium


def _require_pillow():
    try:
        from PIL import Image, ImageDraw
    except ImportError as exc:
        raise RuntimeError("Pillow is required for evidence highlighting.") from exc
    return Image, ImageDraw


def _query_terms(query: str) -> list[str]:
    return [term for term in re.findall(r"[a-z0-9]+", query.lower()) if len(term) >= 4]


def _candidate_search_strings(query: str, snippet: str) -> list[str]:
    candidates: list[str] = []
    cleaned_snippet = snippet.replace("...", " ").strip()
    for piece in re.split(r"(?<=[.!?])\s+", cleaned_snippet):
        piece = piece.strip()
        if len(piece) >= 12:
            candidates.append(piece[:160])
    if query.strip():
        candidates.append(query.strip())
    candidates.extend(_query_terms(query))

    seen: set[str] = set()
    unique: list[str] = []
    for item in candidates:
        key = item.lower()
        if key and key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


def _search_rectangles(textpage, query: str, snippet: str) -> list[tuple[float, float, float, float]]:
    rects: list[tuple[float, float, float, float]] = []
    for candidate in _candidate_search_strings(query, snippet):
        searcher = textpage.search(candidate)
        match = searcher.get_next()
        if not match:
            continue
        index, count = match
        rect_count = textpage.count_rects(index, count)
        if rect_count <= 0:
            continue
        rects = [textpage.get_rect(i) for i in range(rect_count)]
        if rects:
            return rects
    return rects


def render_highlighted_page(
    pdf_path: str | Path,
    page_number: int,
    page_image_path: str | Path,
    query: str,
    snippet: str,
    scale: float = 1.5,
) -> str:
    pdfium = _require_pypdfium2()
    Image, ImageDraw = _require_pillow()

    page_image = Path(page_image_path)
    if not page_image.exists():
        return ""

    output_dir = page_image.parent / "highlights"
    output_dir.mkdir(parents=True, exist_ok=True)
    key = hashlib.md5(f"{page_number}:{query}:{snippet}".encode("utf-8")).hexdigest()[:12]
    output_path = output_dir / f"page-{page_number}-{key}.png"
    if output_path.exists():
        return str(output_path)

    pdf = pdfium.PdfDocument(str(pdf_path))
    page = pdf[page_number - 1]
    textpage = page.get_textpage()
    rects = _search_rectangles(textpage, query=query, snippet=snippet)
    if not rects:
        return ""

    image = Image.open(page_image).convert("RGBA")
    overlay = Image.new("RGBA", image.size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(overlay)
    page_height = page.get_height()

    for left, bottom, right, top in rects:
        x0 = left * scale
        x1 = right * scale
        y0 = (page_height - top) * scale
        y1 = (page_height - bottom) * scale
        draw.rectangle([x0 - 2, y0 - 2, x1 + 2, y1 + 2], fill=(255, 230, 0, 110), outline=(255, 170, 0, 180))

    highlighted = Image.alpha_composite(image, overlay).convert("RGB")
    highlighted.save(output_path)
    return str(output_path)


def render_object_region_highlight(
    page_image_path: str | Path,
    page_number: int,
    object_type: str,
    metadata: dict[str, str] | None = None,
) -> str:
    Image, ImageDraw = _require_pillow()

    page_image = Path(page_image_path)
    if not page_image.exists():
        return ""

    metadata = metadata or {}
    region_hint = (metadata.get("region_hint") or "middle").lower()
    label = metadata.get("label", "")
    key = hashlib.md5(f"{page_number}:{object_type}:{region_hint}:{label}".encode("utf-8")).hexdigest()[:12]
    output_dir = page_image.parent / "highlights"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"page-{page_number}-object-{key}.png"
    if output_path.exists():
        return str(output_path)

    image = Image.open(page_image).convert("RGBA")
    width, height = image.size
    overlay = Image.new("RGBA", image.size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(overlay)

    bands = {
        "top": (0.12, 0.36),
        "middle": (0.36, 0.68),
        "bottom": (0.68, 0.9),
        "unknown": (0.28, 0.72),
    }
    start_ratio, end_ratio = bands.get(region_hint, bands["unknown"])
    y0 = int(height * start_ratio)
    y1 = int(height * end_ratio)
    x0 = int(width * 0.08)
    x1 = int(width * 0.92)

    fill = (80, 170, 255, 70)
    outline = (20, 120, 220, 200)
    if object_type == "table":
        fill = (40, 180, 99, 70)
        outline = (20, 120, 70, 210)
    elif object_type == "figure":
        fill = (168, 85, 247, 70)
        outline = (126, 34, 206, 210)

    draw.rounded_rectangle([x0, y0, x1, y1], radius=14, fill=fill, outline=outline, width=4)

    highlighted = Image.alpha_composite(image, overlay).convert("RGB")
    highlighted.save(output_path)
    return str(output_path)
