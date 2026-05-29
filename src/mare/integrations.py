from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from mare.types import RetrievalHit


_FINDING_PATTERNS: dict[str, tuple[re.Pattern[str], ...]] = {
    "actions": (
        re.compile(r"\b(must|should|need to|required to|complete|submit|review|install|connect|plug|update|provide|send|ensure|enable)\b", re.IGNORECASE),
    ),
    "requirements": (
        re.compile(r"\b(must|shall|required|required to|mandatory|need to|needs to|requirement)\b", re.IGNORECASE),
    ),
    "risks": (
        re.compile(r"\b(risk|risks|warning|warnings|caution|cautions|hazard|failure|penalty|avoid|do not|don't|unless)\b", re.IGNORECASE),
    ),
    "deadlines": (
        re.compile(r"\b(due|deadline|deadlines|by\s+\w+|before\b|within\s+\d+\s+(day|days|week|weeks|month|months)|no later than)\b", re.IGNORECASE),
        re.compile(r"\b(january|february|march|april|may|june|july|august|september|october|november|december)\b", re.IGNORECASE),
        re.compile(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b"),
    ),
}


def format_evidence_citation(
    *,
    title: str,
    page: int,
    metadata: dict[str, Any] | None = None,
) -> str:
    resolved_metadata = metadata or {}
    source = str(resolved_metadata.get("source") or "").strip()
    source_label = Path(source).name if source else title
    parts = [source_label]

    line_start = str(resolved_metadata.get("line_start") or "").strip()
    line_end = str(resolved_metadata.get("line_end") or "").strip()
    heading = str(resolved_metadata.get("heading") or resolved_metadata.get("label") or "").strip()

    if line_start and line_end:
        if line_start == line_end:
            parts.append(f"line {line_start}")
        else:
            parts.append(f"lines {line_start}-{line_end}")
    else:
        parts.append(f"page {page}")

    if heading:
        parts.append(heading)

    return " | ".join(part for part in parts if part)


def _hit_metadata(hit: RetrievalHit) -> dict[str, Any]:
    metadata = dict(hit.metadata)
    metadata.update(
        {
            "doc_id": hit.doc_id,
            "title": hit.title,
            "page": hit.page,
            "score": hit.score,
            "reason": hit.reason,
            "modality": hit.modality.value,
            "page_image_path": hit.page_image_path,
            "highlight_image_path": hit.highlight_image_path,
            "object_id": hit.object_id,
            "object_type": hit.object_type,
            "citation": format_evidence_citation(title=hit.title, page=hit.page, metadata=hit.metadata),
        }
    )
    return metadata


def _hit_text(hit: RetrievalHit) -> str:
    return hit.snippet or hit.reason or hit.title


def _serialize_hit(hit: RetrievalHit) -> dict[str, Any]:
    return {
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
        "metadata": dict(hit.metadata),
        "citation": format_evidence_citation(title=hit.title, page=hit.page, metadata=hit.metadata),
    }


def _build_comparison_payload(results: list[dict[str, Any]], *, limit: int = 4) -> list[dict[str, Any]]:
    comparison: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, str, int]] = set()
    for hit in results:
        metadata = hit.get("metadata", {})
        source_document = str(metadata.get("source") or hit.get("title") or "")
        key = (source_document, str(hit.get("object_type") or "page"), int(hit.get("page") or 0))
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


def build_grounded_summary_payload(results: list[dict[str, Any]], *, limit: int = 3) -> dict[str, Any]:
    highlights: list[dict[str, Any]] = []
    unique_sources: set[str] = set()
    for hit in results:
        metadata = hit.get("metadata", {})
        source_document = str(metadata.get("source") or hit.get("title") or "")
        if source_document:
            unique_sources.add(source_document)
        highlights.append(
            {
                "citation": hit.get("citation") or "",
                "source_document": source_document,
                "object_type": hit.get("object_type") or "page",
                "snippet": hit.get("snippet") or "",
                "reason": hit.get("reason") or "",
            }
        )
        if len(highlights) >= limit:
            break

    overview = "No grounded evidence found."
    if results:
        result_label = "result" if len(results) == 1 else "results"
        source_count = len(unique_sources)
        source_label = "source" if source_count == 1 else "sources"
        overview = f"Found {len(results)} grounded {result_label} across {source_count} {source_label}."

    return {
        "overview": overview,
        "highlight_count": len(highlights),
        "highlights": highlights,
    }


def _normalize_finding_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _finding_signal(finding_type: str, text: str) -> str:
    for pattern in _FINDING_PATTERNS[finding_type]:
        match = pattern.search(text)
        if match:
            return match.group(0)
    return ""


def build_grounded_findings_payload(
    results: list[dict[str, Any]],
    *,
    finding_type: str,
    limit: int = 5,
) -> dict[str, Any]:
    if finding_type not in _FINDING_PATTERNS:
        raise ValueError(f"Unsupported finding type: {finding_type}")

    items: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for hit in results:
        text = _normalize_finding_text(hit.get("snippet") or hit.get("reason") or "")
        if not text:
            continue
        signal = _finding_signal(finding_type, text)
        if not signal:
            continue
        citation = hit.get("citation") or ""
        unique_key = (citation, text)
        if unique_key in seen:
            continue
        seen.add(unique_key)
        metadata = hit.get("metadata", {})
        source_document = str(metadata.get("source") or hit.get("title") or "")
        items.append(
            {
                "type": finding_type,
                "signal": signal,
                "citation": citation,
                "source_document": source_document,
                "page": hit.get("page"),
                "object_type": hit.get("object_type") or "page",
                "score": hit.get("score"),
                "snippet": text,
                "reason": hit.get("reason") or "",
            }
        )
        if len(items) >= limit:
            break

    label = finding_type[:-1] if finding_type.endswith("s") else finding_type
    if items:
        overview = f"Found {len(items)} grounded {finding_type}."
    else:
        overview = f"No grounded {finding_type} found in the current evidence."

    return {
        "overview": overview,
        "item_count": len(items),
        "items": items,
        "focus": label,
    }


def build_all_grounded_findings_payload(results: list[dict[str, Any]], *, limit: int = 5) -> dict[str, Any]:
    return {
        finding_type: build_grounded_findings_payload(results, finding_type=finding_type, limit=limit)
        for finding_type in ("actions", "requirements", "risks", "deadlines")
    }


def build_grounded_review_payload(
    results: list[dict[str, Any]],
    *,
    comparison: list[dict[str, Any]] | None = None,
    summary: dict[str, Any] | None = None,
    findings: dict[str, Any] | None = None,
    support: dict[str, Any] | None = None,
) -> dict[str, Any]:
    resolved_comparison = comparison if comparison is not None else _build_comparison_payload(results)
    resolved_summary = summary if summary is not None else build_grounded_summary_payload(results)
    resolved_findings = findings if findings is not None else build_all_grounded_findings_payload(results)
    resolved_support = support or {}

    best = results[0] if results else {}
    finding_counts = {
        finding_type: int((resolved_findings.get(finding_type, {}) or {}).get("item_count", 0))
        for finding_type in ("actions", "requirements", "risks", "deadlines")
    }

    review_highlights: list[str] = []
    if resolved_summary.get("overview"):
        review_highlights.append(str(resolved_summary["overview"]))
    if resolved_support.get("label"):
        review_highlights.append(f"Support: {resolved_support['label']}")
    for finding_type, count in finding_counts.items():
        if count:
            review_highlights.append(f"{count} {finding_type}")

    return {
        "overview": "No grounded review available." if not results else "Grounded review assembled from the best supporting evidence.",
        "best_evidence": {
            "citation": best.get("citation") or "",
            "snippet": best.get("snippet") or "",
            "reason": best.get("reason") or "",
            "source_document": str(best.get("metadata", {}).get("source") or best.get("title") or ""),
            "page": best.get("page"),
            "object_type": best.get("object_type") or "page",
            "score": best.get("score"),
        },
        "support": resolved_support,
        "summary_overview": resolved_summary.get("overview") or "",
        "comparison_count": len(resolved_comparison),
        "finding_counts": finding_counts,
        "highlights": review_highlights,
    }


def hits_to_evidence_payload(query: str, hits: list[RetrievalHit]) -> dict[str, Any]:
    results = [_serialize_hit(hit) for hit in hits]
    comparison = _build_comparison_payload(results)
    summary = build_grounded_summary_payload(results)
    findings = build_all_grounded_findings_payload(results)
    return {
        "query": query,
        "results": results,
        "comparison": comparison,
        "summary": summary,
        "findings": findings,
        "review": build_grounded_review_payload(results, comparison=comparison, summary=summary, findings=findings),
    }


def hit_to_langchain_document(hit: RetrievalHit):
    try:
        from langchain_core.documents import Document as LangChainDocument
    except ImportError as exc:
        raise RuntimeError(
            "LangChain integration requires `langchain-core`. Install it with "
            "`pip install 'mare-retrieval[langchain]'` or `pip install langchain-core`."
        ) from exc

    return LangChainDocument(page_content=_hit_text(hit), metadata=_hit_metadata(hit))


def hit_to_llamaindex_node(hit: RetrievalHit):
    try:
        from llama_index.core.schema import NodeWithScore, TextNode
    except ImportError as exc:
        raise RuntimeError(
            "LlamaIndex integration requires `llama-index-core`. Install it with "
            "`pip install 'mare-retrieval[llamaindex]'` or `pip install llama-index-core`."
        ) from exc

    node = TextNode(text=_hit_text(hit), metadata=_hit_metadata(hit))
    return NodeWithScore(node=node, score=hit.score)


def create_langchain_retriever(app, top_k: int = 3):
    try:
        from langchain_core.retrievers import BaseRetriever
    except ImportError as exc:
        raise RuntimeError(
            "LangChain integration requires `langchain-core`. Install it with "
            "`pip install 'mare-retrieval[langchain]'` or `pip install langchain-core`."
        ) from exc

    try:
        from pydantic import ConfigDict
    except ImportError:  # pragma: no cover - optional dependency
        ConfigDict = None

    class LangChainMARERetriever(BaseRetriever):
        mare_app: Any
        top_k: int = 3

        if ConfigDict is not None:
            model_config = ConfigDict(arbitrary_types_allowed=True)
        else:  # pragma: no cover - compatibility shim
            class Config:
                arbitrary_types_allowed = True

        def _get_relevant_documents(self, query: str, *, run_manager=None):
            hits = self.mare_app.retrieve(query=query, top_k=self.top_k)
            return [hit_to_langchain_document(hit) for hit in hits]

        async def _aget_relevant_documents(self, query: str, *, run_manager=None):
            return self._get_relevant_documents(query, run_manager=run_manager)

    return LangChainMARERetriever(mare_app=app, top_k=top_k)


def create_langgraph_tool(app, top_k: int = 3, name: str = "mare_retrieve", description: str | None = None):
    return create_langchain_tool(app, top_k=top_k, name=name, description=description)


def create_langchain_tool(app, top_k: int = 3, name: str = "mare_retrieve", description: str | None = None):
    try:
        from langchain_core.tools import StructuredTool
    except ImportError as exc:
        raise RuntimeError("LangChain tool integration requires `langchain-core`. Install it with "
                           "`pip install 'mare-retrieval[langchain]'` or `pip install langchain-core`.") from exc

    tool_description = description or (
        "Retrieve evidence from documents with MARE. Returns structured page, snippet, "
        "highlight, and metadata for the most relevant results."
    )

    def _run(query: str) -> dict[str, Any]:
        hits = app.retrieve(query=query, top_k=top_k)
        return hits_to_evidence_payload(query, hits)

    return StructuredTool.from_function(
        func=_run,
        name=name,
        description=tool_description,
    )


def create_llamaindex_tool(app, top_k: int = 3, name: str = "mare_retrieve", description: str | None = None):
    try:
        from llama_index.core.tools import FunctionTool
    except ImportError as exc:
        raise RuntimeError(
            "LlamaIndex tool integration requires `llama-index-core`. Install it with "
            "`pip install 'mare-retrieval[llamaindex]'` or `pip install llama-index-core`."
        ) from exc

    tool_description = description or (
        "Retrieve grounded evidence from documents with MARE and return a structured evidence payload."
    )

    def _run(query: str) -> dict[str, Any]:
        hits = app.retrieve(query=query, top_k=top_k)
        return hits_to_evidence_payload(query, hits)

    return FunctionTool.from_defaults(fn=_run, name=name, description=tool_description)


def create_llamaindex_retriever(app, top_k: int = 3):
    try:
        from llama_index.core.base.base_retriever import BaseRetriever
        from llama_index.core.schema import QueryBundle
    except ImportError as exc:
        raise RuntimeError(
            "LlamaIndex integration requires `llama-index-core`. Install it with "
            "`pip install 'mare-retrieval[llamaindex]'` or `pip install llama-index-core`."
        ) from exc

    class LlamaIndexMARERetriever(BaseRetriever):
        def __init__(self, mare_app, top_k: int = 3):
            super().__init__()
            self.mare_app = mare_app
            self.top_k = top_k

        def _retrieve(self, query_bundle):
            if isinstance(query_bundle, QueryBundle):
                query = query_bundle.query_str
            else:
                query = getattr(query_bundle, "query_str", str(query_bundle))
            hits = self.mare_app.retrieve(query=query, top_k=self.top_k)
            return [hit_to_llamaindex_node(hit) for hit in hits]

    return LlamaIndexMARERetriever(app, top_k=top_k)
