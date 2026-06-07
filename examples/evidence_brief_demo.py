from __future__ import annotations

"""
Example: print an Evidence Brief for the bundled mixed-document workspace.

Typical usage from a repo checkout:

PYTHONPATH=src python3 examples/evidence_brief_demo.py

Use your own folder and question:

PYTHONPATH=src python3 examples/evidence_brief_demo.py \
  --folder ./docs \
  --query "what actions are required before onboarding is complete"
"""

import argparse

from mare.workflow import _build_workflow_payload, _load_app


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a trust-first MARE Evidence Brief over a document folder")
    parser.add_argument("--folder", default="examples/mixed_docs", help="Folder containing supported documents")
    parser.add_argument("--query", default="show me the onboarding steps", help="Question to ask")
    parser.add_argument("--top-k", type=int, default=3, help="How many retrieval hits to consider")
    parser.add_argument("--reuse", action="store_true", help="Reuse generated corpora when available")
    parser.add_argument("--parser", default="builtin", help="Parser to use. Default: builtin")
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()
    app = _load_app(
        documents=[],
        corpora=[],
        folder=args.folder,
        reuse=args.reuse,
        parser=args.parser,
    )
    payload = _build_workflow_payload(
        app,
        query=args.query,
        object_query=args.query,
        object_type=None,
        top_k=args.top_k,
        page_limit=3,
        object_limit=5,
    )
    query_step = payload["steps"]["query_corpus"]
    brief = query_step.get("evidence_brief", {})
    support = brief.get("support") or {}

    print(f"Evidence brief query: {query_step['query']}")
    print(brief.get("overview") or "No evidence brief available.")
    if support.get("message"):
        print(f"Support note: {support['message']}")
    print(f"Sources: {', '.join(brief.get('source_documents') or []) or '[none]'}")
    source_diversity = brief.get("source_diversity") or {}
    if source_diversity.get("label"):
        print(f"Source coverage: {source_diversity['label']}")
    print(f"Proof assets: {', '.join(brief.get('available_proof_assets') or []) or '[none]'}")
    for index, item in enumerate(brief.get("conflict_hints") or [], start=1):
        print(f"Conflict hint {index}: {item.get('message') or '[no message]'}")
    for index, item in enumerate(brief.get("evidence_gaps") or [], start=1):
        print(f"Evidence gap {index}: {item}")
    for index, item in enumerate(brief.get("next_questions") or [], start=1):
        print(f"Next question {index}: {item}")


if __name__ == "__main__":
    main()
