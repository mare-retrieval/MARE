from __future__ import annotations

import argparse
import datetime as dt
import fnmatch
import json
from pathlib import Path

from mare.api import MAREApp
from mare.integrations import format_evidence_citation
from mare.workflow import _build_workflow_payload, _load_app


_SKIP_DIR_NAMES = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    ".pytest_cache",
    "__pycache__",
    "node_modules",
}


class ChatSessionStore:
    def __init__(self, path: Path, *, session_name: str, source_documents: list[str], corpus_paths: list[str]) -> None:
        self.path = path
        self.session_name = session_name
        self.source_documents = source_documents
        self.corpus_paths = corpus_paths
        self.payload = self._load()

    def _base_payload(self) -> dict:
        timestamp = dt.datetime.now().isoformat(timespec="seconds")
        return {
            "session_name": self.session_name,
            "created_at": timestamp,
            "updated_at": timestamp,
            "source_documents": self.source_documents,
            "corpora": self.corpus_paths,
            "entries": [],
        }

    def _load(self) -> dict:
        if not self.path.exists():
            return self._base_payload()
        try:
            payload = json.loads(self.path.read_text())
        except (OSError, json.JSONDecodeError):
            return self._base_payload()
        if not isinstance(payload, dict):
            return self._base_payload()
        payload.setdefault("session_name", self.session_name)
        payload.setdefault("created_at", dt.datetime.now().isoformat(timespec="seconds"))
        payload["updated_at"] = dt.datetime.now().isoformat(timespec="seconds")
        payload["source_documents"] = self.source_documents
        payload["corpora"] = self.corpus_paths
        payload.setdefault("entries", [])
        if not isinstance(payload["entries"], list):
            payload["entries"] = []
        return payload

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.payload["updated_at"] = dt.datetime.now().isoformat(timespec="seconds")
        self.path.write_text(json.dumps(self.payload, indent=2) + "\n")

    def append(self, *, entry_type: str, query: str, payload: dict | None = None) -> None:
        summary: dict[str, str | int | None] = {}
        if payload:
            results = payload.get("steps", {}).get("query_corpus", {}).get("results", [])
            best = results[0] if results else None
            if best:
                summary = {
                    "citation": best.get("citation")
                    or format_evidence_citation(
                        title=best.get("title", ""),
                        page=best["page"],
                        metadata=best.get("metadata", {}),
                    ),
                    "object_type": best.get("object_type") or "page",
                    "page": best.get("page"),
                    "snippet": best.get("snippet") or "",
                }
        self.payload["entries"].append(
            {
                "timestamp": dt.datetime.now().isoformat(timespec="seconds"),
                "type": entry_type,
                "query": query,
                "top_result": summary,
            }
        )
        self.save()

    def clear(self) -> None:
        created_at = self.payload.get("created_at", dt.datetime.now().isoformat(timespec="seconds"))
        self.payload = self._base_payload()
        self.payload["created_at"] = created_at
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
    source_pdf = payload.get("source_pdf", "")
    if source_pdf and not isinstance(source_pdf, str):
        return None
    return payload


def _discover_folder_inputs(
    folder: Path,
    *,
    include: list[str] | None = None,
    exclude: list[str] | None = None,
) -> tuple[list[str], list[str]]:
    supported_document_suffixes = {".pdf", ".md", ".markdown", ".txt", ".docx"}
    pdfs: list[str] = []
    corpora: list[str] = []
    for path in _iter_folder_files(folder, include=include, exclude=exclude):
        suffix = path.suffix.lower()
        if suffix in supported_document_suffixes:
            pdfs.append(str(path))
            continue
        if suffix == ".json" and _read_probable_corpus(path) is not None:
            corpora.append(str(path))
    pdfs.sort()
    corpora.sort()
    return pdfs, corpora


def _build_app_from_args(
    *,
    folder: str | None,
    documents: list[str],
    corpora: list[str],
    include: list[str],
    exclude: list[str],
    reuse: bool,
    parser: str,
) -> MAREApp:
    resolved_documents = list(dict.fromkeys(documents))
    resolved_corpora = list(dict.fromkeys(corpora))
    if folder:
        folder_pdfs, folder_corpora = _discover_folder_inputs(Path(folder), include=include, exclude=exclude)
        resolved_documents = list(dict.fromkeys([*resolved_documents, *folder_pdfs]))
        resolved_corpora = list(dict.fromkeys([*resolved_corpora, *folder_corpora]))
    return _load_app(documents=resolved_documents, corpora=resolved_corpora, reuse=reuse, parser=parser)


def _print_intro(app: MAREApp) -> None:
    source_documents = [str(path) for path in app.source_documents]
    print("MARE Chat")
    print("")
    if source_documents:
        print(f"Loaded documents: {', '.join(source_documents)}")
    if app.corpus_paths:
        print(f"Loaded corpora: {', '.join(str(path) for path in app.corpus_paths)}")
    print("Type a question, or use :help, :brief, :review, :sources, :actions, :requirements, :risks, :deadlines, :json <question>, :quit")
    print("")


def _print_help() -> None:
    print("Commands")
    print(":actions .. Extract action items with citations for the rest of the line")
    print(":brief ... Show support strength, evidence gaps, proof assets, and next questions")
    print(":clear-history Clear saved session history for this chat session")
    print(":compare .. Compare grounded evidence across top matches for the rest of the line")
    print(":deadlines Extract deadlines and due-date language for the rest of the line")
    print(":help      Show this help")
    print(":history    Show recent saved session history")
    print(":requirements Extract requirement language with citations for the rest of the line")
    print(":review .. Assemble a grounded review with answer, support, and findings")
    print(":risks ... Extract risk, warning, or caution evidence for the rest of the line")
    print(":steps ... Extract procedure-like steps with citations for the rest of the line")
    print(":summary . Summarize grounded evidence across top matches for the rest of the line")
    print(":sources   Show loaded documents and corpora")
    print(":json ...  Return the workflow payload as JSON for the rest of the line")
    print(":quit      Exit mare-chat")
    print("")


def _print_sources(app: MAREApp) -> None:
    print("Sources")
    if app.source_documents:
        print(f"Documents: {', '.join(str(path) for path in app.source_documents)}")
    else:
        print("Documents: none")
    if app.corpus_paths:
        print(f"Corpora: {', '.join(str(path) for path in app.corpus_paths)}")
    else:
        print("Corpora: none")
    print("")


def _print_history(session_store: ChatSessionStore) -> None:
    entries = session_store.payload.get("entries", [])
    print(f"Session history: {session_store.session_name}")
    print(f"Session file: {session_store.path}")
    if not entries:
        print("Entries: none")
        print("")
        return

    print("Recent entries")
    for index, entry in enumerate(entries[-5:], start=max(len(entries) - 4, 1)):
        line = f"{index}. [{entry['type']}] {entry['query']} ({entry['timestamp']})"
        print(line)
        top_result = entry.get("top_result") or {}
        if top_result.get("citation"):
            print(f"   Top evidence: {top_result['citation']}")
        if top_result.get("snippet"):
            print(f"   Snippet: {top_result['snippet']}")
    print("")


def _format_score(score: float | None) -> str:
    if score is None:
        return "n/a"
    return f"{score:.3f}"


def _print_top_results(results: list[dict]) -> None:
    if len(results) <= 1:
        return
    print("Other evidence")
    for index, hit in enumerate(results[1:4], start=2):
        citation = hit.get("citation") or format_evidence_citation(
            title=hit.get("title", ""),
            page=hit["page"],
            metadata=hit.get("metadata", {}),
        )
        label = f"{index}. {citation} | {hit['object_type'] or 'page'} | score={_format_score(hit.get('score'))}"
        print(label)
        if hit.get("snippet"):
            print(f"   Snippet: {hit['snippet']}")
    print("")


def _print_steps(app: MAREApp, query: str, *, object_limit: int) -> None:
    results = app.search_objects(query=query, object_type="procedure", limit=object_limit)
    print(f"Step query: {query}")
    if not results:
        print("Steps: No matching procedure evidence found.")
        print("")
        return

    print("Steps")
    for index, hit in enumerate(results, start=1):
        metadata = hit.get("metadata", {})
        heading = metadata.get("heading", "")
        step_label = metadata.get("step", "")
        citation = f"page {hit['page']}"
        if hit.get("title"):
            citation += f" | {hit['title']}"
        if heading:
            citation += f" | {heading}"
        if step_label:
            citation += f" | step {step_label}"
        print(f"{index}. {hit['content']}")
        print(f"   Citation: {citation}")
    print("")


def _print_comparison(payload: dict) -> None:
    query_step = payload["steps"]["query_corpus"]
    results = query_step["results"]
    print(f"Compare query: {query_step['query']}")
    if not results:
        print("Compare: No matching evidence found.")
        print("")
        return

    print("Comparison")
    for index, hit in enumerate(results[:4], start=1):
        citation = hit.get("citation") or format_evidence_citation(
            title=hit.get("title", ""),
            page=hit["page"],
            metadata=hit.get("metadata", {}),
        )
        label = f"{index}. {citation} | {hit['object_type'] or 'page'} | score={_format_score(hit.get('score'))}"
        print(label)
        print(f"   Snippet: {hit['snippet'] or '[no snippet available]'}")
        print(f"   Reason: {hit['reason']}")
    print("")


def _print_summary(payload: dict) -> None:
    query_step = payload["steps"]["query_corpus"]
    results = query_step["results"]
    summary = query_step.get("summary", {})
    print(f"Summary query: {query_step['query']}")
    if not results:
        print("Summary: No matching evidence found.")
        print("")
        return

    print("Grounded summary")
    if summary.get("overview"):
        print(f"Overview: {summary['overview']}")
    highlights = summary.get("highlights") or []
    for index, item in enumerate(highlights, start=1):
        citation = item.get("citation") or ""
        snippet = item.get("snippet") or "[no snippet available]"
        print(f"{index}. {snippet}")
        print(f"   Citation: {citation}")
        if item.get("reason"):
            print(f"   Reason: {item['reason']}")
    print("")


def _print_findings(payload: dict, finding_type: str) -> None:
    query_step = payload["steps"]["query_corpus"]
    findings = query_step.get("findings", {}).get(finding_type, {})
    print(f"{finding_type.title()} query: {query_step['query']}")
    if not findings.get("items"):
        print(findings.get("overview") or f"No grounded {finding_type} found.")
        print("")
        return

    print(findings.get("overview") or finding_type.title())
    for index, item in enumerate(findings["items"], start=1):
        print(f"{index}. {item.get('snippet') or '[no snippet available]'}")
        print(f"   Citation: {item.get('citation') or '[no citation available]'}")
        print(f"   Signal: {item.get('signal') or '[no signal]'}")
        if item.get("reason"):
            print(f"   Reason: {item['reason']}")
    print("")


def _print_review(payload: dict) -> None:
    query_step = payload["steps"]["query_corpus"]
    review = query_step.get("review", {})
    best = review.get("best_evidence", {})
    evidence_brief = review.get("evidence_brief") or query_step.get("evidence_brief") or {}
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
    if evidence_brief.get("overview"):
        print(f"Evidence brief: {evidence_brief['overview']}")
    for index, item in enumerate(evidence_brief.get("next_questions") or [], start=1):
        print(f"Next question {index}: {item}")
    finding_counts = review.get("finding_counts", {})
    print(
        "Findings: "
        + ", ".join(f"{name}={finding_counts.get(name, 0)}" for name in ("actions", "requirements", "risks", "deadlines"))
    )
    for index, item in enumerate(review.get("highlights") or [], start=1):
        print(f"{index}. {item}")
    print("")


def _print_evidence_brief(payload: dict) -> None:
    query_step = payload["steps"]["query_corpus"]
    evidence_brief = query_step.get("evidence_brief", {})
    support = evidence_brief.get("support") or {}
    print(f"Evidence brief query: {query_step['query']}")
    print(evidence_brief.get("overview") or "No evidence brief available.")
    if support.get("message"):
        print(f"Support note: {support['message']}")
    sources = evidence_brief.get("source_documents") or []
    print(f"Sources: {', '.join(sources) if sources else '[none]'}")
    source_diversity = evidence_brief.get("source_diversity") or {}
    if source_diversity.get("label"):
        print(f"Source coverage: {source_diversity['label']}")
    proof_assets = evidence_brief.get("available_proof_assets") or []
    print(f"Proof assets: {', '.join(proof_assets) if proof_assets else '[none]'}")
    for index, item in enumerate(evidence_brief.get("conflict_hints") or [], start=1):
        print(f"Conflict hint {index}: {item.get('message') or '[no message]'}")
    for index, item in enumerate(evidence_brief.get("evidence_gaps") or [], start=1):
        print(f"Evidence gap {index}: {item}")
    for index, item in enumerate(evidence_brief.get("next_questions") or [], start=1):
        print(f"Next question {index}: {item}")
    print("")


def _print_answer(payload: dict) -> None:
    query_step = payload["steps"]["query_corpus"]
    plan = query_step["plan"]
    results = query_step["results"]
    print(f"Question: {query_step['query']}")
    retriever = query_step.get("retriever", {})
    if retriever.get("label"):
        print(f"Retriever: {retriever['label']}")
    if retriever.get("note"):
        print(f"Retriever note: {retriever['note']}")
    print(f"Intent: {plan['intent']}")
    print(f"Confidence: {_format_score(plan.get('confidence'))}")
    if plan.get("selected_modalities"):
        print(f"Modalities: {', '.join(plan['selected_modalities'])}")
    if plan.get("rationale"):
        print(f"Plan reason: {plan['rationale']}")
    if not results:
        print("Answer: No matching evidence found.")
        print("")
        return

    best = results[0]
    support = query_step.get("support", {})
    evidence_brief = query_step.get("evidence_brief", {})
    source_document = best.get("metadata", {}).get("source", "")
    print(f"Best page: {best['page']}")
    if source_document:
        print(f"Source document: {source_document}")
    print(
        "Citation: "
        + (
            best.get("citation")
            or format_evidence_citation(title=best.get("title", ""), page=best["page"], metadata=best.get("metadata", {}))
        )
    )
    print(f"Object type: {best['object_type'] or 'page'}")
    print(f"Score: {_format_score(best.get('score'))}")
    if support.get("label"):
        print(f"Support: {support['label']}")
    if support.get("message"):
        print(f"Support note: {support['message']}")
    if evidence_brief.get("overview"):
        print(f"Evidence brief: {evidence_brief['overview']}")
    gaps = evidence_brief.get("evidence_gaps") or []
    if gaps:
        print(f"Evidence gaps: {gaps[0]}")
    next_questions = evidence_brief.get("next_questions") or []
    if next_questions:
        print(f"Next question: {next_questions[0]}")
    print(f"Snippet: {best['snippet'] or '[no snippet available]'}")
    print(f"Reason: {best['reason']}")
    print(f"Page image: {best['page_image_path'] or '[no page image available]'}")
    print(f"Highlight: {best['highlight_image_path'] or '[no highlight available]'}")
    print("")
    _print_top_results(results)


def _default_session_slug(app: MAREApp) -> str:
    if app.source_documents:
        stem = Path(str(app.source_documents[0])).stem
        return f"{stem}-chat"
    if app.corpus_paths:
        stem = Path(str(app.corpus_paths[0])).stem
        return f"{stem}-chat"
    return "mare-chat"


def build_session_store(app: MAREApp, *, session_file: str | None = None, session_name: str | None = None) -> ChatSessionStore:
    resolved_session_name = session_name or _default_session_slug(app)
    session_path = Path(session_file) if session_file else Path("generated/chat_sessions") / f"{resolved_session_name}.json"
    return ChatSessionStore(
        session_path,
        session_name=resolved_session_name,
        source_documents=[str(path) for path in app.source_documents],
        corpus_paths=[str(path) for path in app.corpus_paths],
    )


def run_chat(
    app: MAREApp,
    *,
    top_k: int = 3,
    page_limit: int = 3,
    object_limit: int = 5,
    session_store: ChatSessionStore | None = None,
) -> None:
    _print_intro(app)
    while True:
        try:
            raw = input("mare> ").strip()
        except EOFError:
            print("")
            break
        except KeyboardInterrupt:
            print("")
            break

        if not raw:
            continue
        if raw in {":quit", ":exit"}:
            break
        if raw == ":help":
            _print_help()
            continue
        if raw == ":history":
            if session_store is None:
                print("Session history is disabled for this chat.")
                print("")
                continue
            _print_history(session_store)
            continue
        if raw == ":clear-history":
            if session_store is None:
                print("Session history is disabled for this chat.")
                print("")
                continue
            session_store.clear()
            print("Session history cleared.")
            print("")
            continue
        if raw == ":sources":
            _print_sources(app)
            continue
        if raw.startswith(":compare"):
            query = raw[len(":compare") :].strip()
            if not query:
                print("Usage: :compare <question>")
                print("")
                continue
            payload = _build_workflow_payload(
                app,
                query=query,
                object_query=query,
                object_type=None,
                top_k=top_k,
                page_limit=page_limit,
                object_limit=object_limit,
            )
            _print_comparison(payload)
            if session_store is not None:
                session_store.append(entry_type="compare", query=query, payload=payload)
            continue
        if raw.startswith(":summary"):
            query = raw[len(":summary") :].strip()
            if not query:
                print("Usage: :summary <question>")
                print("")
                continue
            payload = _build_workflow_payload(
                app,
                query=query,
                object_query=query,
                object_type=None,
                top_k=top_k,
                page_limit=page_limit,
                object_limit=object_limit,
            )
            _print_summary(payload)
            if session_store is not None:
                session_store.append(entry_type="summary", query=query, payload=payload)
            continue
        if raw.startswith(":brief"):
            query = raw[len(":brief") :].strip()
            if not query:
                print("Usage: :brief <question>")
                print("")
                continue
            payload = _build_workflow_payload(
                app,
                query=query,
                object_query=query,
                object_type=None,
                top_k=top_k,
                page_limit=page_limit,
                object_limit=object_limit,
            )
            _print_evidence_brief(payload)
            if session_store is not None:
                session_store.append(entry_type="brief", query=query, payload=payload)
            continue
        if raw.startswith(":review"):
            query = raw[len(":review") :].strip()
            if not query:
                print("Usage: :review <question>")
                print("")
                continue
            payload = _build_workflow_payload(
                app,
                query=query,
                object_query=query,
                object_type=None,
                top_k=top_k,
                page_limit=page_limit,
                object_limit=object_limit,
            )
            _print_review(payload)
            if session_store is not None:
                session_store.append(entry_type="review", query=query, payload=payload)
            continue
        if raw.startswith(":steps"):
            query = raw[len(":steps") :].strip()
            if not query:
                print("Usage: :steps <question>")
                print("")
                continue
            _print_steps(app, query, object_limit=object_limit)
            if session_store is not None:
                session_store.append(entry_type="steps", query=query)
            continue
        if raw.startswith(":json"):
            query = raw[len(":json") :].strip()
            if not query:
                print("Usage: :json <question>")
                print("")
                continue
            payload = _build_workflow_payload(
                app,
                query=query,
                object_query=query,
                object_type=None,
                top_k=top_k,
                page_limit=page_limit,
                object_limit=object_limit,
            )
            print(json.dumps(payload, indent=2))
            print("")
            if session_store is not None:
                session_store.append(entry_type="json", query=query, payload=payload)
            continue
        for command_name in ("actions", "requirements", "risks", "deadlines"):
            prefix = f":{command_name}"
            if raw.startswith(prefix):
                query = raw[len(prefix) :].strip()
                if not query:
                    print(f"Usage: {prefix} <question>")
                    print("")
                    break
                payload = _build_workflow_payload(
                    app,
                    query=query,
                    object_query=query,
                    object_type=None,
                    top_k=top_k,
                    page_limit=page_limit,
                    object_limit=object_limit,
                )
                _print_findings(payload, command_name)
                if session_store is not None:
                    session_store.append(entry_type=command_name, query=query, payload=payload)
                break
        else:
            payload = _build_workflow_payload(
                app,
                query=raw,
                object_query=raw,
                object_type=None,
                top_k=top_k,
                page_limit=page_limit,
                object_limit=object_limit,
            )
            _print_answer(payload)
            if session_store is not None:
                session_store.append(entry_type="ask", query=raw, payload=payload)
            continue
        continue


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a simple document evidence chat loop over source documents or corpora")
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
        help="Path to a source document. Repeat to load multiple documents.",
    )
    parser.add_argument("--pdf", action="append", default=[], help="Path to a PDF. Repeat to load multiple PDFs.")
    parser.add_argument(
        "--corpus",
        dest="corpora",
        action="append",
        default=[],
        help="Path to an existing MARE corpus JSON. Repeat to load multiple corpora.",
    )
    parser.add_argument("--reuse", action="store_true", help="Reuse generated corpora for PDFs when available")
    parser.add_argument("--parser", default="builtin", help="Parser to use for --pdf ingestion. Default: builtin")
    parser.add_argument("--top-k", type=int, default=3, help="How many retrieval hits to consider")
    parser.add_argument("--page-limit", type=int, default=3, help="How many pages to include in summaries")
    parser.add_argument("--object-limit", type=int, default=5, help="How many objects to include in summaries")
    parser.add_argument("--session-file", help="Optional JSON file path for saving chat session history")
    parser.add_argument("--session-name", help="Optional session name used for saved chat history")
    parser.add_argument("--no-history", action="store_true", help="Disable saved chat session history")
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()
    documents = [*args.document, *args.pdf]
    app = _build_app_from_args(
        folder=args.folder,
        documents=documents,
        corpora=args.corpora,
        include=args.include,
        exclude=args.exclude,
        reuse=args.reuse,
        parser=args.parser,
    )
    session_store = None
    if not args.no_history:
        session_store = build_session_store(app, session_file=args.session_file, session_name=args.session_name)
    run_chat(
        app,
        top_k=args.top_k,
        page_limit=args.page_limit,
        object_limit=args.object_limit,
        session_store=session_store,
    )


if __name__ == "__main__":
    main()
