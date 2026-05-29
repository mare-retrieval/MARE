from __future__ import annotations

import argparse
import datetime as dt
import fnmatch
import json
from pathlib import Path
from typing import Any

from mare.api import MAREApp, load_corpora, load_corpus, load_document
from mare.integrations import build_all_grounded_findings_payload, build_grounded_review_payload, build_grounded_summary_payload, format_evidence_citation


_SKIP_DIR_NAMES = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    ".pytest_cache",
    "__pycache__",
    "node_modules",
}


class WorkflowHistoryStore:
    def __init__(self, path: Path, *, history_name: str, source_documents: list[str], corpus_paths: list[str]) -> None:
        self.path = path
        self.history_name = history_name
        self.source_documents = source_documents
        self.corpus_paths = corpus_paths
        self.payload = self._load()

    def _base_payload(self) -> dict[str, Any]:
        timestamp = dt.datetime.now().isoformat(timespec="seconds")
        return {
            "history_name": self.history_name,
            "created_at": timestamp,
            "updated_at": timestamp,
            "source_documents": self.source_documents,
            "corpora": self.corpus_paths,
            "runs": [],
        }

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return self._base_payload()
        try:
            payload = json.loads(self.path.read_text())
        except (OSError, json.JSONDecodeError):
            return self._base_payload()
        if not isinstance(payload, dict):
            return self._base_payload()
        payload.setdefault("history_name", self.history_name)
        payload.setdefault("created_at", dt.datetime.now().isoformat(timespec="seconds"))
        payload["updated_at"] = dt.datetime.now().isoformat(timespec="seconds")
        payload["source_documents"] = self.source_documents
        payload["corpora"] = self.corpus_paths
        payload.setdefault("runs", [])
        if not isinstance(payload["runs"], list):
            payload["runs"] = []
        return payload

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.payload["updated_at"] = dt.datetime.now().isoformat(timespec="seconds")
        self.path.write_text(json.dumps(self.payload, indent=2) + "\n")

    def append(self, *, payload: dict[str, Any], output_format: str, object_query: str, object_type: str | None) -> None:
        query_step = payload["steps"]["query_corpus"]
        results = query_step["results"]
        best = results[0] if results else None
        self.payload["runs"].append(
            {
                "timestamp": dt.datetime.now().isoformat(timespec="seconds"),
                "query": query_step["query"],
                "object_query": object_query,
                "object_type": object_type or "",
                "output_format": output_format,
                "intent": query_step["plan"]["intent"],
                "result_count": len(results),
                "top_result": (
                    {
                        "citation": best.get("citation") or "",
                        "object_type": best.get("object_type") or "page",
                        "page": best.get("page"),
                        "snippet": best.get("snippet") or "",
                        "reason": best.get("reason") or "",
                    }
                    if best
                    else {}
                ),
            }
        )
        self.save()


def _matches_patterns(path: Path, folder: Path, patterns: list[str]) -> bool:
    relative_path = str(path.relative_to(folder))
    return any(fnmatch.fnmatch(relative_path, pattern) for pattern in patterns)


def _iter_folder_files(folder: Path, *, include: list[str] | None = None, exclude: list[str] | None = None):
    include_patterns = include or []
    exclude_patterns = exclude or []
    for path in folder.rglob("*"):
        if any(part in _SKIP_DIR_NAMES for part in path.parts):
            continue
        if not path.is_file():
            continue
        if include_patterns and not _matches_patterns(path, folder, include_patterns):
            continue
        if exclude_patterns and _matches_patterns(path, folder, exclude_patterns):
            continue
        yield path


def _read_probable_corpus(path: Path) -> dict | None:
    try:
        payload = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    if not isinstance(payload.get("documents"), list):
        return None
    return payload


def _discover_folder_inputs(
    folder: Path,
    *,
    include: list[str] | None = None,
    exclude: list[str] | None = None,
) -> tuple[list[str], list[str]]:
    supported_document_suffixes = {".pdf", ".md", ".markdown", ".txt", ".docx"}
    documents: list[str] = []
    corpora: list[str] = []
    for path in _iter_folder_files(folder, include=include, exclude=exclude):
        suffix = path.suffix.lower()
        if suffix in supported_document_suffixes:
            documents.append(str(path))
            continue
        if suffix == ".json" and _read_probable_corpus(path) is not None:
            corpora.append(str(path))
    documents.sort()
    corpora.sort()
    return documents, corpora


def _default_output_path(source_path: Path) -> Path:
    return Path("generated") / f"{source_path.stem}.json"


def _resolved_retriever_label(app: MAREApp) -> str:
    label = getattr(app.config, "retriever_label", "") if getattr(app, "config", None) else ""
    return label or "Built-in lexical"


def _retriever_resolution_note(app: MAREApp) -> str:
    note = getattr(app.config, "retriever_resolution_note", "") if getattr(app, "config", None) else ""
    return note or ""


def _build_support_assessment(explanation) -> dict[str, str | float | None]:
    if not explanation.fused_results:
        return {
            "status": "none",
            "label": "No support",
            "message": "No grounded evidence was found for this query.",
            "best_score": None,
            "plan_confidence": explanation.plan.confidence,
        }

    best = explanation.fused_results[0]
    best_score = float(best.score)
    plan_confidence = float(explanation.plan.confidence)

    if best_score >= 0.85 and plan_confidence >= 0.7:
        status = "strong"
        label = "Strong support"
        message = "Grounded evidence looks strong for this answer."
    elif best_score >= 0.65 and plan_confidence >= 0.55:
        status = "moderate"
        label = "Moderate support"
        message = "Grounded evidence is useful, but you may want to inspect the proof directly."
    else:
        status = "weak"
        label = "Weak support"
        message = "Evidence is weak or ambiguous. Inspect the proof carefully or refine the question."

    return {
        "status": status,
        "label": label,
        "message": message,
        "best_score": best_score,
        "plan_confidence": plan_confidence,
    }


def _load_app(
    *,
    documents: list[str],
    corpora: list[str],
    folder: str | None = None,
    include: list[str] | None = None,
    exclude: list[str] | None = None,
    reuse: bool = False,
    parser: str = "builtin",
) -> MAREApp:
    resolved_documents = list(dict.fromkeys(documents))
    resolved_corpora = list(dict.fromkeys(corpora))
    if folder:
        folder_documents, folder_corpora = _discover_folder_inputs(Path(folder), include=include, exclude=exclude)
        resolved_documents = list(dict.fromkeys([*resolved_documents, *folder_documents]))
        resolved_corpora = list(dict.fromkeys([*resolved_corpora, *folder_corpora]))

    if not resolved_documents and not resolved_corpora:
        raise ValueError("Provide at least one --document/--pdf/--folder or --corpus input.")

    if resolved_documents and not resolved_corpora and len(resolved_documents) == 1:
        return load_document(
            source_path=resolved_documents[0],
            output_path=_default_output_path(Path(resolved_documents[0])),
            reuse=reuse,
            parser=parser,
        )

    for source_path in resolved_documents:
        app = load_document(
            source_path=source_path,
            output_path=_default_output_path(Path(source_path)),
            reuse=reuse,
            parser=parser,
        )
        if app.corpus_path is None:
            raise RuntimeError(f"Failed to build a corpus for {source_path}.")
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
    support = _build_support_assessment(explanation)
    retrieval_results = [
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
            "citation": format_evidence_citation(title=hit.title, page=hit.page, metadata=hit.metadata),
        }
        for hit in explanation.fused_results
    ]
    comparison = _build_comparison_view(retrieval_results)
    grounded_summary = build_grounded_summary_payload(retrieval_results)
    findings = build_all_grounded_findings_payload(retrieval_results)
    review = build_grounded_review_payload(
        retrieval_results,
        comparison=comparison,
        summary=grounded_summary,
        findings=findings,
        support=support,
    )

    return {
        "workflow": "agent-evidence",
        "source": {
            "corpus": str(app.corpus_path) if app.corpus_path else "",
            "corpora": [str(path) for path in app.corpus_paths],
            "source_document": str(app.source_document) if app.source_document else "",
            "source_documents": [str(path) for path in app.source_documents],
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
                "retriever": {
                    "label": _resolved_retriever_label(app),
                    "note": _retriever_resolution_note(app),
                },
                "plan": {
                    "intent": explanation.plan.intent,
                    "selected_modalities": [item.value for item in explanation.plan.selected_modalities],
                    "discarded_modalities": [item.value for item in explanation.plan.discarded_modalities],
                    "confidence": explanation.plan.confidence,
                    "rationale": explanation.plan.rationale,
                },
                "results": retrieval_results,
                "comparison": comparison,
                "summary": grounded_summary,
                "findings": findings,
                "review": review,
                "support": support,
            },
        },
    }


def _build_comparison_view(results: list[dict[str, Any]], *, limit: int = 4) -> list[dict[str, Any]]:
    comparison: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, str, int]] = set()
    for hit in results:
        metadata = hit.get("metadata", {})
        source_document = metadata.get("source", "") or hit.get("title", "")
        key = (source_document, hit.get("object_type") or "page", hit.get("page") or 0)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        comparison.append(
            {
                "source_document": source_document,
                "citation": hit.get("citation") or "",
                "object_type": hit.get("object_type") or "page",
                "page": hit.get("page"),
                "score": hit.get("score"),
                "reason": hit.get("reason") or "",
                "snippet": hit.get("snippet") or "",
            }
        )
        if len(comparison) >= limit:
            break
    return comparison


def _print_pretty(payload: dict[str, Any]) -> None:
    source = payload["source"]
    describe = payload["steps"]["describe_corpus"]
    searched = payload["steps"]["search_objects"]
    query_step = payload["steps"]["query_corpus"]
    results = query_step["results"]
    comparison = query_step.get("comparison", [])
    summary = query_step.get("summary", {})

    print("MARE Agent Workflow")
    print("")
    print("Source")
    if source["source_documents"]:
        print(f"Documents: {', '.join(source['source_documents'])}")
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
    retriever = query_step.get("retriever", {})
    if retriever.get("label"):
        print(f"Retriever: {retriever['label']}")
    if retriever.get("note"):
        print(f"Retriever note: {retriever['note']}")
    print(f"Intent: {query_step['plan']['intent']}")
    if not results:
        print("Best result: no evidence found")
        return

    if summary.get("overview"):
        print(f"Summary: {summary['overview']}")
    support = query_step.get("support", {})
    if support.get("label"):
        print(f"Support: {support['label']}")
    if support.get("message"):
        print(f"Support note: {support['message']}")

    best = results[0]
    source_document = best.get("metadata", {}).get("source", "")
    print(f"Best result: page {best['page']} ({best['object_type'] or 'page'})")
    if source_document:
        print(f"Source document: {source_document}")
    print(f"Citation: {best.get('citation') or format_evidence_citation(title=best.get('title', ''), page=best['page'], metadata=best.get('metadata', {}))}")
    print(f"Reason: {best['reason']}")
    print(f"Snippet: {best['snippet'] or '[no snippet available]'}")
    print(f"Page image: {best['page_image_path'] or '[no page image available]'}")
    print(f"Highlight: {best['highlight_image_path'] or '[no highlight available]'}")
    if len(comparison) > 1:
        print("")
        print("Comparison View")
        for index, item in enumerate(comparison, start=1):
            score_label = f"{item['score']:.3f}" if isinstance(item.get("score"), (int, float)) else "n/a"
            print(f"{index}. {item['citation']} | {item['object_type']} | score={score_label}")
            print(f"   Source: {item['source_document']}")
            print(f"   Snippet: {item['snippet'] or '[no snippet available]'}")
            print(f"   Reason: {item['reason']}")


def _print_findings(payload: dict[str, Any], finding_type: str) -> None:
    query_step = payload["steps"]["query_corpus"]
    findings = query_step.get("findings", {}).get(finding_type, {})
    print(f"{finding_type.title()} query: {query_step['query']}")
    if not findings.get("items"):
        print(findings.get("overview") or f"No grounded {finding_type} found.")
        print("")
        return

    print(findings.get("overview") or finding_type.title())
    for index, item in enumerate(findings["items"], start=1):
        score_label = f"{item['score']:.3f}" if isinstance(item.get("score"), (int, float)) else "n/a"
        print(f"{index}. {item['snippet']}")
        print(f"   Citation: {item.get('citation') or '[no citation available]'}")
        print(f"   Signal: {item.get('signal') or '[no signal]'}")
        print(f"   Score: {score_label}")
        if item.get("reason"):
            print(f"   Reason: {item['reason']}")
    print("")


def _print_review(payload: dict[str, Any]) -> None:
    query_step = payload["steps"]["query_corpus"]
    review = query_step.get("review", {})
    best = review.get("best_evidence", {})
    print(f"Review query: {query_step['query']}")
    print(review.get("overview") or "No grounded review available.")
    support = review.get("support") or {}
    if support.get("label"):
        print(f"Support: {support['label']}")
    if support.get("message"):
        print(f"Support note: {support['message']}")
    if best.get("citation"):
        print(f"Primary citation: {best['citation']}")
    if best.get("snippet"):
        print(f"Primary snippet: {best['snippet']}")
    if best.get("reason"):
        print(f"Primary reason: {best['reason']}")
    finding_counts = review.get("finding_counts", {})
    print(
        "Findings: "
        + ", ".join(f"{name}={finding_counts.get(name, 0)}" for name in ("actions", "requirements", "risks", "deadlines"))
    )
    highlights = review.get("highlights") or []
    if highlights:
        print("Highlights")
        for index, item in enumerate(highlights, start=1):
            print(f"{index}. {item}")
    print("")


def _default_history_slug(app: MAREApp) -> str:
    if app.source_documents:
        return f"{Path(str(app.source_documents[0])).stem}-workflow"
    if app.corpus_paths:
        return f"{Path(str(app.corpus_paths[0])).stem}-workflow"
    return "mare-workflow"


def build_history_store(
    app: MAREApp,
    *,
    history_file: str | None = None,
    history_name: str | None = None,
) -> WorkflowHistoryStore:
    resolved_history_name = history_name or _default_history_slug(app)
    history_path = Path(history_file) if history_file else Path("generated/workflow_runs") / f"{resolved_history_name}.json"
    return WorkflowHistoryStore(
        history_path,
        history_name=resolved_history_name,
        source_documents=[str(path) for path in app.source_documents],
        corpus_paths=[str(path) for path in app.corpus_paths],
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a human-friendly, agent-style MARE evidence workflow over one or more PDFs/corpora"
    )
    parser.add_argument("--folder", help="Folder containing documents and/or MARE corpus JSON files")
    parser.add_argument(
        "--include",
        action="append",
        default=[],
        help="Optional glob pattern relative to --folder to include. Repeat to add more patterns.",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        help="Optional glob pattern relative to --folder to exclude. Repeat to add more patterns.",
    )
    parser.add_argument(
        "--document",
        action="append",
        default=[],
        help="Path to a source document. Repeat to compare documents.",
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
    parser.add_argument(
        "--task",
        choices=("answer", "review", "compare", "summary", "actions", "requirements", "risks", "deadlines"),
        default="answer",
        help="Optional user-facing task view to print in pretty mode. JSON output always includes the full payload.",
    )
    parser.add_argument("--history-file", help="Optional JSON file path for saving workflow run history")
    parser.add_argument("--history-name", help="Optional history name used for saved workflow runs")
    parser.add_argument("--no-history", action="store_true", help="Disable saved workflow run history")
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()
    documents = [*args.document, *args.pdf]
    app = _load_app(
        documents=documents,
        corpora=args.corpora,
        folder=args.folder,
        include=args.include,
        exclude=args.exclude,
        reuse=args.reuse,
        parser=args.parser,
    )
    payload = _build_workflow_payload(
        app,
        query=args.query,
        object_query=args.object_query or args.query,
        object_type=args.object_type,
        top_k=args.top_k,
        page_limit=args.page_limit,
        object_limit=args.object_limit,
    )
    if not args.no_history:
        history_store = build_history_store(app, history_file=args.history_file, history_name=args.history_name)
        history_store.append(
            payload=payload,
            output_format=args.format,
            object_query=args.object_query or args.query,
            object_type=args.object_type,
        )
    if args.format == "json":
        print(json.dumps(payload, indent=2))
        return
    if args.task == "review":
        _print_review(payload)
        return
    if args.task in {"actions", "requirements", "risks", "deadlines"}:
        _print_findings(payload, args.task)
        return
    if args.task == "compare":
        query_step = payload["steps"]["query_corpus"]
        print(f"Compare query: {query_step['query']}")
        comparison = query_step.get("comparison", [])
        if not comparison:
            print("Compare: No matching evidence found.")
            return
        print("Comparison")
        for index, item in enumerate(comparison, start=1):
            score_label = f"{item['score']:.3f}" if isinstance(item.get("score"), (int, float)) else "n/a"
            print(f"{index}. {item['citation']} | {item['object_type']} | score={score_label}")
            print(f"   Source: {item['source_document']}")
            print(f"   Snippet: {item['snippet'] or '[no snippet available]'}")
            print(f"   Reason: {item['reason']}")
        return
    if args.task == "summary":
        query_step = payload["steps"]["query_corpus"]
        summary = query_step.get("summary", {})
        print(f"Summary query: {query_step['query']}")
        print(summary.get("overview") or "No grounded evidence found.")
        for index, item in enumerate(summary.get("highlights") or [], start=1):
            print(f"{index}. {item.get('snippet') or '[no snippet available]'}")
            print(f"   Citation: {item.get('citation') or '[no citation available]'}")
            if item.get("reason"):
                print(f"   Reason: {item['reason']}")
        return
    _print_pretty(payload)


if __name__ == "__main__":
    main()
