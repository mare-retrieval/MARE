from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from mare.api import MAREApp, load_corpora, load_corpus, load_pdf


def _default_output_path(pdf_path: Path) -> Path:
    return Path("generated") / f"{pdf_path.stem}.json"


def _load_app(
    *,
    pdfs: list[str],
    corpora: list[str],
    reuse: bool = False,
    parser: str = "builtin",
) -> MAREApp:
    if not pdfs and not corpora:
        raise ValueError("Provide at least one --pdf or --corpus input.")

    if pdfs and not corpora and len(pdfs) == 1:
        return load_pdf(pdf_path=pdfs[0], output_path=_default_output_path(Path(pdfs[0])), reuse=reuse, parser=parser)

    resolved_corpora = list(corpora)
    for pdf in pdfs:
        app = load_pdf(pdf_path=pdf, output_path=_default_output_path(Path(pdf)), reuse=reuse, parser=parser)
        if app.corpus_path is None:
            raise RuntimeError(f"Failed to build a corpus for {pdf}.")
        resolved_corpora.append(str(app.corpus_path))

    if len(resolved_corpora) == 1:
        return load_corpus(resolved_corpora[0])
    return load_corpora(resolved_corpora)


def _build_workflow_payload(
    app: MAREApp,
    *,
    query: str,
    object_query: str,
    object_type: str | None,
    top_k: int,
    page_limit: int,
    object_limit: int,
) -> dict[str, Any]:
    summary = app.describe_corpus(page_limit=page_limit, object_limit=object_limit)
    browsed_objects = app.search_objects(query=object_query, object_type=object_type, limit=object_limit)
    explanation = app.explain(query, top_k=top_k)
    return {
        "workflow": "agent-evidence",
        "source": {
            "corpus": str(app.corpus_path) if app.corpus_path else "",
            "corpora": [str(path) for path in app.corpus_paths],
            "source_pdf": str(app.source_pdf) if app.source_pdf else "",
            "source_pdfs": [str(path) for path in app.source_pdfs],
            "documents": len(app.documents),
        },
        "steps": {
            "describe_corpus": summary,
            "search_objects": {
                "query": object_query,
                "object_type": object_type or "",
                "results": browsed_objects,
            },
            "query_corpus": {
                "query": query,
                "plan": {
                    "intent": explanation.plan.intent,
                    "selected_modalities": [item.value for item in explanation.plan.selected_modalities],
                    "discarded_modalities": [item.value for item in explanation.plan.discarded_modalities],
                    "confidence": explanation.plan.confidence,
                    "rationale": explanation.plan.rationale,
                },
                "results": [
                    {
                        "doc_id": hit.doc_id,
                        "title": hit.title,
                        "page": hit.page,
                        "score": hit.score,
                        "snippet": hit.snippet,
                        "reason": hit.reason,
                        "page_image_path": hit.page_image_path,
                        "highlight_image_path": hit.highlight_image_path,
                        "object_id": hit.object_id,
                        "object_type": hit.object_type,
                        "metadata": hit.metadata,
                    }
                    for hit in explanation.fused_results
                ],
            },
        },
    }


def _print_pretty(payload: dict[str, Any]) -> None:
    source = payload["source"]
    describe = payload["steps"]["describe_corpus"]
    searched = payload["steps"]["search_objects"]
    query_step = payload["steps"]["query_corpus"]
    results = query_step["results"]

    print("MARE Agent Workflow")
    print("")
    print("Source")
    if source["source_pdfs"]:
        print(f"PDFs: {', '.join(source['source_pdfs'])}")
    if source["corpora"]:
        print(f"Corpora: {', '.join(source['corpora'])}")
    print(f"Documents: {source['documents']}")
    print("")

    print("Corpus Summary")
    print(f"Pages: {describe['page_count']}")
    object_counts = describe.get("object_counts", {})
    if object_counts:
        counts = ", ".join(f"{name}={count}" for name, count in sorted(object_counts.items()))
        print(f"Objects: {counts}")
    else:
        print("Objects: none")
    print("")

    print("Object Search")
    print(f"Query: {searched['query']}")
    if searched["object_type"]:
        print(f"Filter: {searched['object_type']}")
    if searched["results"]:
        first = searched["results"][0]
        print(f"Top object: {first['object_type']} on page {first['page']}")
        print(f"Content: {first['content']}")
    else:
        print("Top object: none")
    print("")

    print("Grounded Retrieval")
    print(f"Query: {query_step['query']}")
    print(f"Intent: {query_step['plan']['intent']}")
    if not results:
        print("Best result: no evidence found")
        return

    best = results[0]
    source_pdf = best.get("metadata", {}).get("source", "")
    print(f"Best result: page {best['page']} ({best['object_type'] or 'page'})")
    if source_pdf:
        print(f"Source PDF: {source_pdf}")
    print(f"Reason: {best['reason']}")
    print(f"Snippet: {best['snippet'] or '[no snippet available]'}")
    print(f"Page image: {best['page_image_path'] or '[no page image available]'}")
    print(f"Highlight: {best['highlight_image_path'] or '[no highlight available]'}")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a human-friendly, agent-style MARE evidence workflow over one or more PDFs/corpora"
    )
    parser.add_argument("--pdf", action="append", default=[], help="Path to a source PDF. Repeat to compare PDFs.")
    parser.add_argument(
        "--corpus",
        dest="corpora",
        action="append",
        default=[],
        help="Path to an existing MARE corpus JSON file. Repeat to query multiple corpora.",
    )
    parser.add_argument("--query", required=True, help="Final grounded question to ask")
    parser.add_argument(
        "--object-query",
        help="Optional evidence-object search query used before final retrieval. Defaults to --query.",
    )
    parser.add_argument(
        "--object-type",
        choices=("page", "procedure", "figure", "table", "section"),
        help="Optional object type filter for the evidence-browse step",
    )
    parser.add_argument("--top-k", type=int, default=3, help="How many final retrieval hits to return")
    parser.add_argument("--page-limit", type=int, default=3, help="How many pages to show in the corpus summary")
    parser.add_argument("--object-limit", type=int, default=5, help="How many objects to show in summary/search")
    parser.add_argument("--reuse", action="store_true", help="Reuse generated corpora for PDFs when available")
    parser.add_argument("--parser", default="builtin", help="Parser to use for --pdf ingestion. Default: builtin")
    parser.add_argument(
        "--format",
        choices=("pretty", "json"),
        default="pretty",
        help="Output format. Use json for agent-style payloads, pretty for human evaluation.",
    )
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()
    app = _load_app(pdfs=args.pdf, corpora=args.corpora, reuse=args.reuse, parser=args.parser)
    payload = _build_workflow_payload(
        app,
        query=args.query,
        object_query=args.object_query or args.query,
        object_type=args.object_type,
        top_k=args.top_k,
        page_limit=args.page_limit,
        object_limit=args.object_limit,
    )
    if args.format == "json":
        print(json.dumps(payload, indent=2))
        return
    _print_pretty(payload)


if __name__ == "__main__":
    main()
