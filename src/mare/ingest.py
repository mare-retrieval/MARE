from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from mare.objects import extract_document_objects
from mare.types import Document


def _require_pypdf():
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError(
            "pypdf is required for PDF ingestion. Install dependencies with `pip install -e .` "
            "or `pip install pypdf`."
        ) from exc
    return PdfReader


def _require_pdf_renderer():
    try:
        import pypdfium2 as pdfium
    except ImportError as exc:
        raise RuntimeError(
            "pypdfium2 is required for page image rendering. Install it with `pip install pypdfium2`."
        ) from exc
    return pdfium


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _infer_layout_hints(text: str) -> str:
    hints: list[str] = []
    lowered = text.lower()

    if re.search(r"\btable\b", lowered):
        hints.append("table")
    if re.search(r"\bfigure\b", lowered) or "fig." in lowered:
        hints.append("figure")
    if re.search(r"\babstract\b", lowered):
        hints.append("abstract")
    if re.search(r"\breferences\b", lowered):
        hints.append("references")

    return " ".join(hints)


def _infer_page_signals(text: str) -> str:
    lowered = text.lower()
    signals: list[str] = []

    if re.search(r"\btable\b", lowered):
        signals.append("table")
    if re.search(r"\bfigure\b", lowered) or "fig." in lowered or re.search(r"\bdiagram\b", lowered):
        signals.append("figure")
    if re.search(r"(^|\s)\d+\.", lowered):
        signals.append("procedure")
    if any(re.search(pattern, lowered) for pattern in (r"\bcompare\b", r"\bcomparison\b", r"\bversus\b", r"\bvs\.\b")):
        signals.append("comparison")
    if any(
        re.search(pattern, lowered)
        for pattern in (r"\binstall\b", r"\breinstall\b", r"\bremove\b", r"\bloosen\b", r"\btighten\b", r"\buse the\b")
    ):
        signals.append("instruction")

    return " ".join(signals)


def _render_page_images(pdf_path: Path, image_dir: Path, scale: float = 1.5) -> list[str]:
    pdfium = _require_pdf_renderer()
    image_dir.mkdir(parents=True, exist_ok=True)
    pdf = pdfium.PdfDocument(str(pdf_path))
    image_paths: list[str] = []

    for page_index in range(len(pdf)):
        page = pdf[page_index]
        bitmap = page.render(scale=scale)
        image = bitmap.to_pil()
        image_path = image_dir / f"page-{page_index + 1}.png"
        image.save(image_path)
        image_paths.append(str(image_path))

    return image_paths


def ingest_pdf(pdf_path: str | Path, output_path: str | Path | None = None) -> dict[str, Any]:
    PdfReader = _require_pypdf()
    pdf_file = Path(pdf_path)
    reader = PdfReader(str(pdf_file))
    title = pdf_file.stem
    output = Path(output_path) if output_path is not None else Path("generated") / f"{pdf_file.stem}.json"
    page_images = _render_page_images(pdf_file, output.with_suffix(""))
    documents: list[Document] = []

    for idx, page in enumerate(reader.pages, start=1):
        raw_text = page.extract_text() or ""
        text = _normalize_text(raw_text)
        if not text:
            text = f"[No extractable text found on page {idx}]"

        documents.append(
            Document(
                doc_id=f"{pdf_file.stem.lower().replace(' ', '-')}-p{idx}",
                title=title,
                page=idx,
                text=text,
                image_caption="",
                layout_hints=_infer_layout_hints(text),
                page_image_path=page_images[idx - 1] if idx - 1 < len(page_images) else "",
                objects=extract_document_objects(raw_text, f"{pdf_file.stem.lower().replace(' ', '-')}-p{idx}", idx),
                metadata={
                    "source": str(pdf_file),
                    "collection": "pdf-ingest",
                    "signals": _infer_page_signals(text),
                },
            )
        )

    payload = {
        "source_pdf": str(pdf_file),
        "documents": [
            {
                "doc_id": doc.doc_id,
                "title": doc.title,
                "page": doc.page,
                "text": doc.text,
                "image_caption": doc.image_caption,
                "layout_hints": doc.layout_hints,
                "page_image_path": doc.page_image_path,
                "objects": [
                    {
                        "object_id": obj.object_id,
                        "doc_id": obj.doc_id,
                        "page": obj.page,
                        "object_type": obj.object_type.value,
                        "content": obj.content,
                        "metadata": obj.metadata,
                    }
                    for obj in doc.objects
                ],
                "metadata": doc.metadata,
            }
            for doc in documents
        ],
    }

    output.write_text(json.dumps(payload, indent=2))

    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest a PDF into a MARE JSON corpus")
    parser.add_argument("pdf", help="Path to a PDF file")
    parser.add_argument(
        "--output",
        "-o",
        help="Output JSON file path. Defaults to generated/<pdf-stem>.json",
    )
    args = parser.parse_args()

    pdf_path = Path(args.pdf)
    output = Path(args.output) if args.output else Path("generated") / f"{pdf_path.stem}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = ingest_pdf(pdf_path=pdf_path, output_path=output)

    print(
        json.dumps(
            {
                "source_pdf": payload["source_pdf"],
                "pages_indexed": len(payload["documents"]),
                "output": str(output),
                "page_images_dir": str(output.with_suffix("")),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
