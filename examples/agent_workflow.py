from __future__ import annotations

"""
Example: an agent-style MARE workflow over an existing corpus.

This script demonstrates the intended sequence for an agent or backend:

1. Describe the corpus to understand page/object coverage.
2. Search extracted evidence objects to narrow down useful regions.
3. Run final grounded retrieval to get page, snippet, and highlight proof.

Typical usage:

PYTHONPATH=src python3 examples/agent_workflow.py \
  --corpus generated/manual.json \
  --query "how do I configure wake on lan" \
  --object-query "wake on lan" \
  --object-type section
"""

import argparse
import json

from mare import MAREApp


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a MARE agent-style evidence workflow")
    parser.add_argument("--corpus", required=True, help="Path to an existing MARE corpus JSON file")
    parser.add_argument("--query", required=True, help="Final grounded question to ask of the corpus")
    parser.add_argument(
        "--object-query",
        help="Optional evidence-object search query used before final retrieval. Defaults to --query.",
    )
    parser.add_argument(
        "--object-type",
        choices=("page", "procedure", "figure", "table", "section"),
        help="Optional object type filter for the pre-retrieval browse step",
    )
    parser.add_argument("--top-k", type=int, default=3, help="How many final retrieval hits to return")
    parser.add_argument("--page-limit", type=int, default=3, help="How many pages to include in the corpus summary")
    parser.add_argument(
        "--object-limit",
        type=int,
        default=5,
        help="How many objects to include in the corpus summary and object browse step",
    )
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()
    app = MAREApp.from_corpus(args.corpus)

    object_query = args.object_query or args.query
    summary = app.describe_corpus(page_limit=args.page_limit, object_limit=args.object_limit)
    browsed_objects = app.search_objects(
        query=object_query,
        object_type=args.object_type,
        limit=args.object_limit,
    )
    explanation = app.explain(args.query, top_k=args.top_k)

    print(
        json.dumps(
            {
                "workflow": "agent-evidence",
                "source": {
                    "corpus": str(app.corpus_path) if app.corpus_path else args.corpus,
                    "documents": len(app.documents),
                },
                "steps": {
                    "describe_corpus": summary,
                    "search_objects": {
                        "query": object_query,
                        "object_type": args.object_type or "",
                        "results": browsed_objects,
                    },
                    "query_corpus": {
                        "query": args.query,
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
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
