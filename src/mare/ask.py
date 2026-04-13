from __future__ import annotations

import argparse
from pathlib import Path

from mare.api import load_pdf


def _default_output_path(pdf_path: Path) -> Path:
    return Path("generated") / f"{pdf_path.stem}.json"


def _print_answer_block(query: str, corpus_path: Path, explanation) -> None:
    print(f"Question: {query}")
    print(f"Corpus: {corpus_path}")
    print("")

    if not explanation.fused_results:
        print("Answer: No matching page found.")
        return

    best = explanation.fused_results[0]
    print("Best Match")
    print(f"Page: {best.page}")
    print(f"Score: {best.score}")
    print(f"Reason: {best.reason}")
    print(f"Snippet: {best.snippet or '[no snippet available]'}")
    print(f"Image: {best.page_image_path or '[no page image available]'}")


def ask_pdf(pdf_path: Path, query: str, top_k: int = 3, reuse: bool = False):
    app = load_pdf(pdf_path=pdf_path, output_path=_default_output_path(pdf_path), reuse=reuse)
    explanation = app.explain(query, top_k=top_k)
    output_path = app.corpus_path or _default_output_path(pdf_path)
    return output_path, explanation


def main() -> None:
    parser = argparse.ArgumentParser(description="Ask a PDF a question with MARE")
    parser.add_argument("pdf", help="Path to a PDF file")
    parser.add_argument("query", help="Question to ask about the PDF")
    parser.add_argument("--top-k", type=int, default=3, help="How many results to retrieve")
    parser.add_argument(
        "--reuse",
        action="store_true",
        help="Reuse an existing generated corpus if present instead of re-ingesting",
    )
    args = parser.parse_args()

    pdf_path = Path(args.pdf)
    output_path, explanation = ask_pdf(pdf_path=pdf_path, query=args.query, top_k=args.top_k, reuse=args.reuse)
    _print_answer_block(args.query, output_path, explanation)


if __name__ == "__main__":
    main()
