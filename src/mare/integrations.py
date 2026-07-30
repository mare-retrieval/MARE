from __future__ import annotations

import hashlib
import json
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

_CONFLICT_SIGNAL_GROUPS: tuple[tuple[str, tuple[re.Pattern[str], ...]], ...] = (
    (
        "requirement_vs_optional",
        (
            re.compile(r"\b(must|shall|required|required to|mandatory|need to|needs to)\b", re.IGNORECASE),
            re.compile(r"\b(optional|may|can|recommended|if needed|when needed)\b", re.IGNORECASE),
        ),
    ),
    (
        "allow_vs_avoid",
        (
            re.compile(r"\b(do not|don't|avoid|never|prohibited|not allowed)\b", re.IGNORECASE),
            re.compile(r"\b(use|enable|install|connect|submit|required to|must)\b", re.IGNORECASE),
        ),
    ),
    (
        "timing_order",
        (
            re.compile(r"\b(before|prior to|first)\b", re.IGNORECASE),
            re.compile(r"\b(after|following|then|later)\b", re.IGNORECASE),
        ),
    ),
)


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
    provenance = build_evidence_provenance(hit)
    metadata = dict(hit.metadata)
    metadata.update(
        {
            "evidence_id": provenance["evidence_id"],
            "provenance": provenance,
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


def _first_metadata_value(metadata: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = metadata.get(key)
        if value is None:
            continue
        normalized = str(value).strip()
        if normalized:
            return normalized
    return ""


def _stable_json(value: Any) -> str:
    if value in ("", None):
        return ""
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return ""
        try:
            return json.dumps(json.loads(stripped), sort_keys=True, separators=(",", ":"))
        except json.JSONDecodeError:
            return stripped
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _source_hash(*, doc_id: str, title: str, metadata: dict[str, Any]) -> str:
    explicit_hash = _first_metadata_value(metadata, "document_hash", "doc_hash", "source_hash", "sha256")
    if explicit_hash:
        return explicit_hash
    source = _first_metadata_value(metadata, "source", "source_document", "path")
    stable_source = source or f"{doc_id}:{title}"
    return hashlib.sha256(stable_source.encode("utf-8")).hexdigest()


def _table_cell_coordinates(metadata: dict[str, Any]) -> dict[str, str]:
    return {
        key: value
        for key, value in {
            "row": _first_metadata_value(metadata, "row", "row_index", "table_row"),
            "column": _first_metadata_value(metadata, "column", "col", "column_index", "table_column"),
            "cell": _first_metadata_value(metadata, "cell", "cell_ref", "cell_reference"),
        }.items()
        if value
    }


def build_evidence_provenance(hit: RetrievalHit) -> dict[str, Any]:
    metadata = dict(hit.metadata)
    source = _first_metadata_value(metadata, "source", "source_document", "path")
    document_hash = _source_hash(doc_id=hit.doc_id, title=hit.title, metadata=metadata)
    bbox = _stable_json(_first_metadata_value(metadata, "bbox", "bounding_box", "region_bbox"))
    table_cell = _table_cell_coordinates(metadata)
    extraction_method = _first_metadata_value(
        metadata,
        "extraction_method",
        "parser",
        "ocr_engine",
        "visual_retriever",
    )
    ocr_confidence = _first_metadata_value(metadata, "ocr_confidence", "confidence")
    rendered_crop_path = _first_metadata_value(metadata, "crop_path", "rendered_crop_path", "evidence_crop_path")
    if not rendered_crop_path:
        rendered_crop_path = hit.highlight_image_path or hit.page_image_path

    id_parts = [
        document_hash,
        str(hit.page),
        hit.object_id or "",
        hit.object_type or "",
        bbox,
        _stable_json(table_cell),
        extraction_method,
        ocr_confidence,
    ]
    evidence_id = "mare-evidence-" + hashlib.sha256("|".join(id_parts).encode("utf-8")).hexdigest()[:24]
    return {
        "evidence_id": evidence_id,
        "document_hash": document_hash,
        "source_document": source or hit.title,
        "page": hit.page,
        "object_id": hit.object_id,
        "object_type": hit.object_type or "page",
        "bounding_box": bbox,
        "table_cell": table_cell,
        "cell_level": bool(table_cell),
        "extraction_method": extraction_method,
        "ocr_confidence": ocr_confidence,
        "page_image_path": hit.page_image_path,
        "rendered_crop_path": rendered_crop_path,
        "highlight_image_path": hit.highlight_image_path,
    }


def _serialize_hit(hit: RetrievalHit) -> dict[str, Any]:
    provenance = build_evidence_provenance(hit)
    return {
        "evidence_id": provenance["evidence_id"],
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
        "provenance": provenance,
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


def build_evidence_brief_payload(
    query: str,
    results: list[dict[str, Any]],
    *,
    support: dict[str, Any] | None = None,
    limit: int = 3,
) -> dict[str, Any]:
    """Build a deterministic trust brief for humans and agent clients."""
    resolved_support = support or _infer_support_from_results(results)
    best = results[0] if results else {}
    unique_sources = _unique_source_labels(results)
    source_diversity = _source_diversity_payload(results, unique_sources)
    conflict_hints = _conflict_hints(results)
    evidence_quality = _evidence_quality_payload(
        results=results,
        support=resolved_support,
        source_diversity=source_diversity,
        conflict_hints=conflict_hints,
    )
    available_proof_assets = [
        name
        for name, value in (
            ("snippet", best.get("snippet")),
            ("citation", best.get("citation")),
            ("provenance", best.get("evidence_id") or best.get("provenance")),
            ("page_image", best.get("page_image_path")),
            ("highlight", best.get("highlight_image_path")),
        )
        if value
    ]
    gaps = _evidence_gaps(results, resolved_support, unique_sources, conflict_hints=conflict_hints)
    next_questions = _next_evidence_questions(query=query, results=results, gaps=gaps, limit=limit)
    research_plan = _build_research_plan(
        query=query,
        results=results,
        support=resolved_support,
        source_diversity=source_diversity,
        gaps=gaps,
        next_questions=next_questions,
        conflict_hints=conflict_hints,
        limit=limit,
    )

    return {
        "overview": _evidence_brief_overview(results, resolved_support, unique_sources),
        "support": resolved_support,
        "source_count": len(unique_sources),
        "source_documents": unique_sources,
        "source_diversity": source_diversity,
        "evidence_quality": evidence_quality,
        "top_provenance": best.get("provenance") or {},
        "conflict_hints": conflict_hints,
        "available_proof_assets": available_proof_assets,
        "evidence_gaps": gaps,
        "next_questions": next_questions,
        "research_plan": research_plan,
    }


def _infer_support_from_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    if not results:
        return {
            "status": "none",
            "label": "No support",
            "message": "No grounded evidence was found for this query.",
            "best_score": None,
            "plan_confidence": None,
        }

    best_score = results[0].get("score")
    score = float(best_score) if isinstance(best_score, (int, float)) else 0.0
    if score >= 0.85:
        status = "strong"
        label = "Strong support"
        message = "Grounded evidence looks strong for this answer."
    elif score >= 0.65:
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
        "best_score": score,
        "plan_confidence": None,
    }


def _unique_source_labels(results: list[dict[str, Any]]) -> list[str]:
    sources: list[str] = []
    seen: set[str] = set()
    for hit in results:
        metadata = hit.get("metadata", {})
        source = str(metadata.get("source") or hit.get("title") or "").strip()
        if not source:
            continue
        label = Path(source).name
        if label in seen:
            continue
        seen.add(label)
        sources.append(label)
    return sources


def _source_label(hit: dict[str, Any]) -> str:
    metadata = hit.get("metadata", {})
    source = str(metadata.get("source") or hit.get("title") or "").strip()
    return Path(source).name if source else ""


def _source_diversity_payload(results: list[dict[str, Any]], sources: list[str]) -> dict[str, Any]:
    if not results:
        return {
            "status": "none",
            "label": "No source coverage",
            "message": "No sources were retrieved.",
            "source_count": 0,
            "result_count": 0,
            "ratio": 0.0,
        }

    source_count = len(sources)
    result_count = len(results)
    ratio = source_count / max(result_count, 1)
    if source_count >= 3 or (source_count >= 2 and ratio >= 0.5):
        status = "broad"
        label = "Broad source coverage"
        message = "Evidence is spread across multiple sources."
    elif source_count == 2:
        status = "mixed"
        label = "Mixed source coverage"
        message = "Evidence includes more than one source, but coverage is still narrow."
    elif source_count == 1:
        status = "single_source"
        label = "Single-source coverage"
        message = "Evidence is concentrated in one source."
    else:
        status = "unknown"
        label = "Unknown source coverage"
        message = "Source coverage could not be determined from the retrieved evidence."

    return {
        "status": status,
        "label": label,
        "message": message,
        "source_count": source_count,
        "result_count": result_count,
        "ratio": round(ratio, 4),
    }


def _evidence_quality_payload(
    *,
    results: list[dict[str, Any]],
    support: dict[str, Any],
    source_diversity: dict[str, Any],
    conflict_hints: list[dict[str, Any]],
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    if not results:
        checks.append(
            {
                "name": "retrieval",
                "status": "fail",
                "message": "No grounded evidence was retrieved.",
            }
        )
        return {
            "status": "poor",
            "label": "Poor evidence quality",
            "message": "No retrieved evidence is available to inspect.",
            "passed_checks": 0,
            "check_count": len(checks),
            "checks": checks,
        }

    best = results[0]
    support_status = str(support.get("status") or "unknown")
    source_status = str(source_diversity.get("status") or "unknown")
    best_score = support.get("best_score")
    score = float(best_score) if isinstance(best_score, (int, float)) else None

    checks.append(
        {
            "name": "top_score",
            "status": "pass" if support_status in {"strong", "moderate"} else "warn",
            "message": (
                f"Top evidence score is {score:.2f}."
                if score is not None
                else "Top evidence score is unavailable."
            ),
            "value": score,
        }
    )
    checks.append(
        {
            "name": "exact_snippet",
            "status": "pass" if best.get("snippet") else "fail",
            "message": "Top evidence includes an exact snippet."
            if best.get("snippet")
            else "Top evidence is missing an exact snippet.",
        }
    )
    checks.append(
        {
            "name": "citation",
            "status": "pass" if best.get("citation") else "fail",
            "message": "Top evidence includes an inspectable citation."
            if best.get("citation")
            else "Top evidence is missing an inspectable citation.",
        }
    )
    checks.append(
        {
            "name": "visual_proof",
            "status": "pass" if best.get("highlight_image_path") else "warn",
            "message": "Top evidence includes highlighted visual proof."
            if best.get("highlight_image_path")
            else "Top evidence has no highlighted visual proof.",
        }
    )
    provenance = best.get("provenance") or {}
    evidence_id = best.get("evidence_id") or provenance.get("evidence_id")
    checks.append(
        {
            "name": "stable_provenance",
            "status": "pass" if evidence_id else "warn",
            "message": "Top evidence includes a stable provenance ID."
            if evidence_id
            else "Top evidence is missing a stable provenance ID.",
            "value": evidence_id or "",
        }
    )
    is_table = str(best.get("object_type") or "").lower() == "table"
    has_cell = bool((provenance.get("table_cell") or {})) or bool(provenance.get("cell_level"))
    checks.append(
        {
            "name": "table_cell_provenance",
            "status": "pass" if not is_table or has_cell else "warn",
            "message": "Top table evidence includes cell-level coordinates."
            if is_table and has_cell
            else "Top table evidence is page/table-level, not cell-level."
            if is_table
            else "Top evidence is not table evidence.",
            "value": has_cell,
        }
    )
    checks.append(
        {
            "name": "source_coverage",
            "status": "pass" if source_status == "broad" else "warn",
            "message": source_diversity.get("message") or "Source coverage could not be determined.",
            "value": source_diversity.get("source_count"),
        }
    )
    checks.append(
        {
            "name": "conflict_signals",
            "status": "warn" if conflict_hints else "pass",
            "message": "Potential conflict signals were detected."
            if conflict_hints
            else "No obvious conflict signals detected.",
            "value": len(conflict_hints),
        }
    )

    passed = sum(1 for check in checks if check["status"] == "pass")
    failed = sum(1 for check in checks if check["status"] == "fail")
    warned = sum(1 for check in checks if check["status"] == "warn")

    if failed:
        status = "poor"
        label = "Poor evidence quality"
    elif support_status == "strong" and passed >= 4 and not conflict_hints:
        status = "high"
        label = "High evidence quality"
    elif support_status in {"strong", "moderate"} and warned <= 3:
        status = "usable"
        label = "Usable evidence quality"
    else:
        status = "limited"
        label = "Limited evidence quality"

    if status == "high":
        message = "The top evidence has strong support and enough proof signals to answer with citations."
    elif status == "usable":
        message = "The evidence is usable, but at least one proof or coverage signal should be inspected."
    elif status == "limited":
        message = "The evidence has useful pieces, but support or coverage is not strong enough to trust blindly."
    else:
        message = "The evidence is missing core proof needed for a trustworthy answer."

    return {
        "status": status,
        "label": label,
        "message": message,
        "passed_checks": passed,
        "warning_checks": warned,
        "failed_checks": failed,
        "check_count": len(checks),
        "checks": checks,
    }


def _conflict_hints(results: list[dict[str, Any]], *, limit: int = 3) -> list[dict[str, Any]]:
    hints: list[dict[str, Any]] = []
    for group_name, patterns in _CONFLICT_SIGNAL_GROUPS:
        matches_by_pattern: list[list[dict[str, str]]] = []
        for pattern in patterns:
            matches: list[dict[str, str]] = []
            for hit in results:
                text = _normalize_finding_text(hit.get("snippet") or hit.get("reason") or "")
                match = pattern.search(text)
                if not match:
                    continue
                matches.append(
                    {
                        "signal": match.group(0),
                        "citation": hit.get("citation") or "",
                        "source_document": _source_label(hit),
                        "snippet": text,
                    }
                )
            matches_by_pattern.append(matches)

        if all(matches_by_pattern):
            hints.append(
                {
                    "type": group_name,
                    "message": _conflict_hint_message(group_name),
                    "signals": [matches[0] for matches in matches_by_pattern],
                }
            )
        if len(hints) >= limit:
            break
    return hints


def _conflict_hint_message(group_name: str) -> str:
    messages = {
        "requirement_vs_optional": "Retrieved evidence mixes requirement and optional language; compare the cited sources before acting.",
        "allow_vs_avoid": "Retrieved evidence may mix action and avoidance language; inspect the cited snippets for scope.",
        "timing_order": "Retrieved evidence may include different timing or ordering language; verify the sequence.",
    }
    return messages.get(group_name, "Retrieved evidence may contain conflicting signals; inspect the cited snippets.")


def _evidence_gaps(
    results: list[dict[str, Any]],
    support: dict[str, Any],
    sources: list[str],
    *,
    conflict_hints: list[dict[str, Any]] | None = None,
) -> list[str]:
    if not results:
        return ["No grounded evidence was retrieved."]

    gaps: list[str] = []
    if support.get("status") in {"weak", "none"}:
        gaps.append("Support is weak; ask a narrower question or increase top-k.")
    if len(sources) <= 1 and len(results) > 1:
        gaps.append("Evidence comes from one source; compare related documents if available.")
    if conflict_hints:
        gaps.append("Potentially conflicting evidence signals were detected; inspect the cited snippets before acting.")

    best = results[0]
    if not best.get("highlight_image_path"):
        gaps.append("No highlighted visual proof is available for the top result.")
    if not best.get("snippet"):
        gaps.append("No exact snippet is available for the top result.")
    provenance = best.get("provenance") or {}
    if (best.get("object_type") or "").lower() == "table" and not (
        provenance.get("cell_level") or provenance.get("table_cell")
    ):
        gaps.append("Top table evidence is not cell-level; verify table-cell coordinates before mapping into a spreadsheet.")

    if not gaps:
        gaps.append("No obvious evidence gaps detected in the retrieved results.")
    return gaps


def _next_evidence_questions(
    *,
    query: str,
    results: list[dict[str, Any]],
    gaps: list[str],
    limit: int,
) -> list[str]:
    if not results:
        base_query = query.strip() or "this topic"
        return [
            f"Which document discusses {base_query}?",
            f"What exact section or page supports {base_query}?",
        ][:limit]

    suggestions: list[str] = []
    best = results[0]
    source = Path(str(best.get("metadata", {}).get("source") or best.get("title") or "the top source")).name
    object_type = best.get("object_type") or "page"
    if any("one source" in gap for gap in gaps):
        suggestions.append(f"Compare this answer against other documents besides {source}.")
    if any("weak" in gap.lower() for gap in gaps):
        suggestions.append(f"Find stronger evidence for: {query.strip()}")
    suggestions.append(f"Show the exact {object_type} evidence from {source}.")
    suggestions.append(f"What actions, requirements, risks, or deadlines are supported by this evidence?")

    deduped: list[str] = []
    for item in suggestions:
        if item not in deduped:
            deduped.append(item)
        if len(deduped) >= limit:
            break
    return deduped


def _build_research_plan(
    *,
    query: str,
    results: list[dict[str, Any]],
    support: dict[str, Any],
    source_diversity: dict[str, Any],
    gaps: list[str],
    next_questions: list[str],
    conflict_hints: list[dict[str, Any]],
    limit: int,
) -> dict[str, Any]:
    """Build deterministic next retrieval moves for agentic document workflows."""
    support_status = str(support.get("status") or "unknown")
    source_status = str(source_diversity.get("status") or "unknown")
    if not results:
        status = "needs_evidence"
        rationale = "No grounded evidence was retrieved, so the next step is source discovery."
    elif support_status in {"weak", "none"}:
        status = "needs_stronger_support"
        rationale = "Initial support is weak, so alternate evidence-seeking queries should run before answering."
    elif conflict_hints:
        status = "needs_conflict_check"
        rationale = "Potential conflict signals were found, so compare the cited evidence before acting."
    elif source_status in {"single_source", "mixed"} and len(results) > 1:
        status = "needs_source_check"
        rationale = "Evidence is useful but source coverage is narrow, so compare related documents if available."
    else:
        status = "ready"
        rationale = "Evidence is sufficient for a grounded answer, while preserving citations for inspection."

    steps: list[dict[str, Any]] = []
    base_query = " ".join(query.split()) or "this topic"
    if status == "needs_evidence":
        steps.append(
            {
                "action": "discover_sources",
                "query": f"which document discusses {base_query}",
                "reason": "Find candidate sources before making a claim.",
            }
        )
        steps.append(
            {
                "action": "retrieve_exact_support",
                "query": f"exact section or page supporting {base_query}",
                "reason": "Move from broad source discovery to inspectable proof.",
            }
        )
    else:
        if support_status in {"weak", "none"}:
            steps.append(
                {
                    "action": "retrieve_stronger_support",
                    "query": f"exact evidence for {base_query}",
                    "reason": "Weak support needs a narrower evidence query.",
                }
            )
        if source_status in {"single_source", "mixed"}:
            source = _source_label(results[0]) if results else ""
            source_suffix = f" besides {source}" if source else ""
            steps.append(
                {
                    "action": "compare_sources",
                    "query": f"compare supporting evidence for {base_query}{source_suffix}",
                    "reason": "Narrow source coverage should be checked against related documents.",
                }
            )
        if conflict_hints:
            steps.append(
                {
                    "action": "resolve_conflicts",
                    "query": f"conflicting evidence about {base_query}",
                    "reason": "Conflict signals require scoped comparison before acting.",
                }
            )
        if not steps:
            best = results[0] if results else {}
            object_type = best.get("object_type") or "page"
            source = _source_label(best) or "the top source"
            steps.append(
                {
                    "action": "answer_with_citations",
                    "query": base_query,
                    "reason": f"Use the cited {object_type} evidence from {source}.",
                }
            )

    for question in next_questions:
        if len(steps) >= limit:
            break
        normalized = " ".join(str(question).split())
        if not normalized:
            continue
        if any(step.get("query") == normalized for step in steps):
            continue
        steps.append(
            {
                "action": "follow_up",
                "query": normalized,
                "reason": "Evidence Brief follow-up question.",
            }
        )

    if not steps:
        steps.append(
            {
                "action": "inspect_evidence",
                "query": base_query,
                "reason": gaps[0] if gaps else "Inspect the retrieved citations before acting.",
            }
        )

    return {
        "status": status,
        "rationale": rationale,
        "step_count": len(steps[:limit]),
        "steps": steps[:limit],
    }


def _evidence_brief_overview(results: list[dict[str, Any]], support: dict[str, Any], sources: list[str]) -> str:
    if not results:
        return "No evidence brief available because no grounded results were retrieved."
    label = support.get("label") or "Support unknown"
    source_count = len(sources)
    source_label = "source" if source_count == 1 else "sources"
    return f"{label} from {len(results)} retrieved result{'s' if len(results) != 1 else ''} across {source_count} {source_label}."


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
    evidence_brief: dict[str, Any] | None = None,
) -> dict[str, Any]:
    resolved_comparison = comparison if comparison is not None else _build_comparison_payload(results)
    resolved_summary = summary if summary is not None else build_grounded_summary_payload(results)
    resolved_findings = findings if findings is not None else build_all_grounded_findings_payload(results)
    resolved_support = support or {}
    resolved_evidence_brief = evidence_brief if evidence_brief is not None else build_evidence_brief_payload(
        "",
        results,
        support=resolved_support,
    )

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
        "evidence_brief": resolved_evidence_brief,
        "summary_overview": resolved_summary.get("overview") or "",
        "comparison_count": len(resolved_comparison),
        "finding_counts": finding_counts,
        "highlights": review_highlights,
    }


def build_agent_contract_payload(evidence_brief: dict[str, Any]) -> dict[str, Any]:
    """Build a compact action contract for agents using MARE evidence payloads."""
    support = evidence_brief.get("support") or {}
    source_diversity = evidence_brief.get("source_diversity") or {}
    evidence_quality = evidence_brief.get("evidence_quality") or {}
    research_plan = evidence_brief.get("research_plan") or {}
    support_status = str(support.get("status") or "unknown")
    evidence_quality_status = str(evidence_quality.get("status") or "unknown")
    research_status = str(research_plan.get("status") or "unknown")
    conflict_hints = evidence_brief.get("conflict_hints") or []
    gaps = evidence_brief.get("evidence_gaps") or []

    stop_reasons: list[str] = []
    if support_status in {"weak", "none"}:
        stop_reasons.append("support_not_sufficient")
    if evidence_quality_status == "poor":
        stop_reasons.append("evidence_quality_poor")
    if conflict_hints:
        stop_reasons.append("conflict_hints_present")
    if research_status in {"needs_evidence", "needs_stronger_support", "needs_conflict_check"}:
        stop_reasons.append(research_status)

    if research_status == "needs_evidence":
        recommended_action = "discover_sources"
    elif support_status in {"weak", "none"}:
        recommended_action = "retrieve_stronger_support"
    elif evidence_quality_status == "poor":
        recommended_action = "inspect_evidence"
    elif conflict_hints:
        recommended_action = "resolve_conflicts"
    elif research_status == "needs_source_check":
        recommended_action = "compare_sources"
    else:
        recommended_action = "answer_with_citations"

    return {
        "schema_version": "mare.agent_contract.v1",
        "support_status": support_status,
        "evidence_quality_status": evidence_quality_status,
        "source_coverage_status": source_diversity.get("status") or "unknown",
        "research_status": research_status,
        "recommended_action": recommended_action,
        "may_answer": not stop_reasons and recommended_action == "answer_with_citations",
        "stop_reasons": stop_reasons,
        "research_plan": research_plan,
        "evidence_gaps": gaps,
    }


def hits_to_evidence_payload(query: str, hits: list[RetrievalHit]) -> dict[str, Any]:
    results = [_serialize_hit(hit) for hit in hits]
    comparison = _build_comparison_payload(results)
    summary = build_grounded_summary_payload(results)
    findings = build_all_grounded_findings_payload(results)
    evidence_brief = build_evidence_brief_payload(query, results)
    agent_contract = build_agent_contract_payload(evidence_brief)
    return {
        "query": query,
        "results": results,
        "comparison": comparison,
        "summary": summary,
        "findings": findings,
        "evidence_brief": evidence_brief,
        "agent_contract": agent_contract,
        "review": build_grounded_review_payload(
            results,
            comparison=comparison,
            summary=summary,
            findings=findings,
            evidence_brief=evidence_brief,
        ),
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
