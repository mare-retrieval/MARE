from __future__ import annotations

import datetime as dt
import json
import tempfile
from pathlib import Path

from mare.integrations import build_grounded_summary_payload, format_evidence_citation, hits_to_evidence_payload


PARSER_OPTIONS = {
    "Builtin PDF": {
        "value": "builtin",
        "description": "Fast default parser for normal PDFs with extractable text.",
        "extra": "core",
    },
    "Docling": {
        "value": "docling",
        "description": "Richer OCR/layout/table extraction for stronger document structure.",
        "extra": "mare-retrieval[docling]",
    },
    "Unstructured": {
        "value": "unstructured",
        "description": "Element-level parsing for chunk and object extraction.",
        "extra": "mare-retrieval[unstructured]",
    },
    "PaddleOCR": {
        "value": "paddleocr",
        "description": "OCR-first path for scanned PDFs and image-heavy pages.",
        "extra": "mare-retrieval[paddleocr]",
    },
    "Surya": {
        "value": "surya",
        "description": "OCR plus layout-aware parsing for harder scanned documents.",
        "extra": "mare-retrieval[surya]",
    },
}

RETRIEVER_OPTIONS = {
    "Smart default (Recommended)": {
        "value": "smart",
        "description": "Automatically prefers FastEmbed or hybrid semantic retrieval when available and falls back to MARE's built-in evidence retrieval otherwise.",
        "extra": "core",
    },
    "Built-in lexical": {
        "value": "builtin",
        "description": "Uses MARE's strongest default page and object-aware retrieval stack.",
        "extra": "core",
    },
    "Sentence Transformers": {
        "value": "sentence-transformers",
        "description": "Drop-in semantic retrieval with Hugging Face models.",
        "extra": "mare-retrieval[sentence-transformers]",
    },
    "Hybrid semantic + lexical": {
        "value": "hybrid-semantic",
        "description": "Recommended advanced mode: keeps MARE's lexical/object-aware evidence behavior and adds semantic lift.",
        "extra": "mare-retrieval[sentence-transformers]",
    },
    "FastEmbed semantic": {
        "value": "fastembed",
        "description": "Lightweight ONNX semantic retrieval using Qdrant/FastEmbed embeddings.",
        "extra": "mare-retrieval[fastembed]",
    },
    "ColPali visual (Experimental)": {
        "value": "colpali-visual",
        "description": "Page-image retrieval for visually rich PDFs using ColPali/ColQwen-style models.",
        "extra": "mare-retrieval[colpali]",
    },
    "FAISS local vector": {
        "value": "faiss",
        "description": "Stronger local vector search without running an external service.",
        "extra": "mare-retrieval[faiss]",
    },
    "Qdrant service": {
        "value": "qdrant",
        "description": "Production-style vector backend with optional indexing into a running Qdrant instance.",
        "extra": "mare-retrieval[integrations]",
    },
}

RERANKER_OPTIONS = {
    "None": {
        "value": "none",
        "description": "Return fused retrieval results directly.",
        "extra": "core",
    },
    "FastEmbed": {
        "value": "fastembed",
        "description": "Open-source cross-encoder reranking for better top-result quality.",
        "extra": "mare-retrieval[fastembed]",
    },
}

OUTPUT_OPTIONS = {
    "MARE evidence": {
        "value": "mare",
        "description": "Default page/snippet/highlight evidence view.",
        "extra": "core",
    },
    "LangChain preview": {
        "value": "langchain",
        "description": "Preview the result shape as LangChain documents.",
        "extra": "mare-retrieval[langchain]",
    },
    "LangGraph tool": {
        "value": "langgraph",
        "description": "Preview the structured evidence payload an agent tool would receive.",
        "extra": "mare-retrieval[langgraph]",
    },
    "LlamaIndex preview": {
        "value": "llamaindex",
        "description": "Preview the result shape as LlamaIndex nodes.",
        "extra": "mare-retrieval[llamaindex]",
    },
}

STARTER_PROMPTS = [
    "how do I connect the AC adapter",
    "show me the onboarding steps",
    "compare the setup instructions across these docs",
]


def _ui_session_history_path() -> Path:
    return Path("generated/ui_sessions/playground-history.json")


def _load_ui_session_history(path: Path | None = None) -> dict:
    history_path = path or _ui_session_history_path()
    if not history_path.exists():
        timestamp = dt.datetime.now().isoformat(timespec="seconds")
        return {"created_at": timestamp, "updated_at": timestamp, "entries": []}
    try:
        payload = json.loads(history_path.read_text())
    except (OSError, json.JSONDecodeError):
        timestamp = dt.datetime.now().isoformat(timespec="seconds")
        return {"created_at": timestamp, "updated_at": timestamp, "entries": []}
    if not isinstance(payload, dict):
        timestamp = dt.datetime.now().isoformat(timespec="seconds")
        return {"created_at": timestamp, "updated_at": timestamp, "entries": []}
    payload.setdefault("created_at", dt.datetime.now().isoformat(timespec="seconds"))
    payload.setdefault("entries", [])
    if not isinstance(payload["entries"], list):
        payload["entries"] = []
    payload["updated_at"] = dt.datetime.now().isoformat(timespec="seconds")
    return payload


def _save_ui_session_history(history: dict, path: Path | None = None) -> None:
    history_path = path or _ui_session_history_path()
    history_path.parent.mkdir(parents=True, exist_ok=True)
    history["updated_at"] = dt.datetime.now().isoformat(timespec="seconds")
    history_path.write_text(json.dumps(history, indent=2) + "\n")


def _build_ui_history_entry(*, filenames: list[str], query: str, explanation, stack: dict) -> dict:
    best = explanation.fused_results[0] if explanation.fused_results else None
    return {
        "timestamp": dt.datetime.now().isoformat(timespec="seconds"),
        "query": query,
        "filenames": filenames,
        "source_count": len(filenames),
        "citation": (
            format_evidence_citation(title=best.title, page=best.page, metadata=best.metadata)
            if best
            else ""
        ),
        "source_document": _source_label(best) if best else "",
        "object_type": (best.object_type or "page") if best else "",
        "snippet": (best.snippet or "") if best else "",
        "intent": explanation.plan.intent,
        "stack": {
            "parser": stack["parser"],
            "retriever": stack["retriever"],
            "reranker": stack["reranker"],
            "output_mode": stack["output_mode"],
        },
    }


def _append_ui_session_history(*, filenames: list[str], query: str, explanation, stack: dict, path: Path | None = None) -> dict:
    history = _load_ui_session_history(path)
    history["entries"].append(_build_ui_history_entry(filenames=filenames, query=query, explanation=explanation, stack=stack))
    history["entries"] = history["entries"][-20:]
    _save_ui_session_history(history, path)
    return history


def _clear_ui_session_history(path: Path | None = None) -> dict:
    history = _load_ui_session_history(path)
    history["entries"] = []
    _save_ui_session_history(history, path)
    return history


def _require_streamlit():
    try:
        import streamlit as st
    except ImportError as exc:
        raise RuntimeError(
            "streamlit is required for the visual demo. Install it with `pip install -e '.[ui]'` "
            "or `pip install streamlit`."
        ) from exc
    return st


def _inject_styles(st) -> None:
    st.markdown(
        """
        <style>
        .block-container {
            padding-top: 2rem;
            padding-bottom: 2rem;
            max-width: 1200px;
        }
        .mare-hero {
            padding: 1.25rem 1.4rem;
            border: 1px solid #dbe4ea;
            border-radius: 18px;
            background: linear-gradient(135deg, #f8fafc 0%, #eef6ff 100%);
            margin-bottom: 1rem;
        }
        .mare-hero h1 {
            color: #0f172a;
            font-size: 2rem;
            line-height: 1.1;
        }
        .mare-hero p {
            color: #334155;
        }
        .mare-card {
            padding: 1rem 1.1rem;
            border: 1px solid #e5e7eb;
            border-radius: 16px;
            background: #ffffff;
            box-shadow: 0 1px 2px rgba(15, 23, 42, 0.06);
        }
        .mare-label {
            font-size: 0.82rem;
            text-transform: uppercase;
            letter-spacing: 0.04em;
            color: #64748b;
            margin-bottom: 0.3rem;
        }
        .mare-value {
            font-size: 1.05rem;
            color: #0f172a;
            font-weight: 600;
        }
        .mare-snippet {
            font-size: 1rem;
            line-height: 1.55;
            color: #111827;
            background: #fff9db;
            border-left: 4px solid #f59e0b;
            padding: 0.9rem 1rem;
            border-radius: 10px;
        }
        .mare-mini {
            font-size: 0.9rem;
            color: #475569;
        }
        .mare-badge {
            display: inline-block;
            padding: 0.2rem 0.55rem;
            border-radius: 999px;
            background: #eef2ff;
            color: #3730a3;
            font-size: 0.8rem;
            font-weight: 600;
            margin-right: 0.4rem;
            margin-top: 0.25rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_metric_card(st, label: str, value: str) -> None:
    st.markdown(
        f"""
        <div class="mare-card">
          <div class="mare-label">{label}</div>
          <div class="mare-value">{value}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_getting_started(st) -> None:
    prompt_badges = "".join(f"<span class='mare-badge'>{prompt}</span>" for prompt in STARTER_PROMPTS)
    st.markdown(
        f"""
        <div class="mare-card" style="margin-bottom:1rem;">
          <div class="mare-label">Start Here</div>
          <div class="mare-value">Upload documents, then ask one concrete question.</div>
          <p class="mare-mini" style="margin-top:0.7rem;">
            MARE works best when you point it at a document or folder and ask for something inspectable:
            a setup step, a comparison, a summary, or the exact source behind an answer.
          </p>
          <p class="mare-mini" style="margin-top:0.7rem;">
            Recommended sources: PDFs, DOCX, Markdown, and text files. PDFs currently have the strongest visual proof flow.
          </p>
          <div style="margin-top:0.6rem;">{prompt_badges}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_upload_empty_state(st) -> None:
    st.info("Upload one or more documents to start. PDFs, Word docs, Markdown, and text files work best right now.")
    st.markdown(
        """
        <div class="mare-card" style="margin-top:0.8rem;">
          <div class="mare-label">Best First Run</div>
          <div class="mare-value">Use a small folder of related documents and ask one concrete question.</div>
          <p class="mare-mini" style="margin-top:0.7rem;">
            Good first questions ask for a step, a comparison, or a grounded summary.
            MARE will return the best citation, snippet, and any available visual proof.
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption("Starter prompts: " + " | ".join(STARTER_PROMPTS))
    st.caption("Bundled example in the repo: `examples/mixed_docs`")


def _render_candidate(st, hit, rank: int) -> None:
    st.markdown(
        f"""
        <div class="mare-card">
          <div class="mare-label">Candidate {rank}</div>
          <div class="mare-value">Page {hit.page}</div>
          <p class="mare-mini"><strong>Source document:</strong> {_source_label(hit)}</p>
          <p class="mare-mini"><strong>Object type:</strong> {hit.object_type or 'page'}</p>
          <p class="mare-mini"><strong>Score:</strong> {hit.score}</p>
          <p class="mare-mini"><strong>Reason:</strong> {hit.reason}</p>
          <p class="mare-mini"><strong>Snippet:</strong> {hit.snippet or '[no snippet available]'}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_object_preview(st, explanation) -> None:
    best = explanation.fused_results[0]
    object_type = best.object_type or "page"
    st.markdown(
        f"""
        <div class="mare-card">
          <div class="mare-label">Retrieved Object</div>
          <div class="mare-value">{object_type}</div>
          <p class="mare-mini" style="margin-top:0.7rem;">
            This is the evidence unit MARE believes best answers the query before mapping back to the page.
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_page_objects(st, objects) -> None:
    if not objects:
        st.info("No extracted objects were found for this page yet.")
        return

    st.subheader("Objects On This Page")
    for obj in objects:
        metadata_parts = []
        if obj.metadata.get("label"):
            metadata_parts.append(f"label: {obj.metadata['label']}")
        if obj.metadata.get("region_hint"):
            metadata_parts.append(f"region: {obj.metadata['region_hint']}")
        if obj.metadata.get("columns_estimate"):
            metadata_parts.append(f"columns: {obj.metadata['columns_estimate']}")
        metadata_line = " | ".join(metadata_parts)
        st.markdown(
            f"""
            <div class="mare-card" style="margin-bottom:0.8rem;">
              <div class="mare-label">{obj.object_type.value}</div>
              <div class="mare-value">{obj.object_id.split(':')[-1]}</div>
              <p class="mare-mini" style="margin-top:0.4rem;"><strong>{metadata_line or 'no extra metadata yet'}</strong></p>
              <p class="mare-mini" style="margin-top:0.6rem;">{obj.content}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )


def _option_labels(options: dict[str, dict]) -> list[str]:
    return list(options.keys())


def _selected_option_payload(options: dict[str, dict], label: str) -> dict:
    return options[label]


def _source_label(hit) -> str:
    source = hit.metadata.get("source", "") if hit.metadata else ""
    if source:
        return Path(source).name
    return hit.title


def _build_run_signature(uploaded_filenames: list[str], query: str, top_k: int, stack_controls: dict) -> dict[str, object]:
    return {
        "filenames": sorted(uploaded_filenames),
        "file_count": len(uploaded_filenames),
        "query": query.strip(),
        "top_k": top_k,
        "mode": stack_controls["mode"],
        "parser": stack_controls["parser"]["value"],
        "retriever": stack_controls["retriever"]["value"],
        "reranker": stack_controls["reranker"]["value"],
        "output": stack_controls["output"]["value"],
        "reuse_corpus": bool(stack_controls["reuse_corpus"]),
        "qdrant_url": stack_controls["qdrant_url"],
        "qdrant_collection": stack_controls["qdrant_collection"],
        "qdrant_index_before_query": bool(stack_controls["qdrant_index_before_query"]),
    }


def _result_matches_signature(result: dict | None, run_signature: dict[str, object]) -> bool:
    if not result:
        return False
    return result.get("run_signature") == run_signature


def _render_stack_summary(st, stack: dict) -> None:
    st.markdown(
        f"""
        <div class="mare-card">
          <div class="mare-label">Stack Used</div>
          <div style="margin-top:0.25rem;">
            <span class="mare-badge">Parser: {stack['parser']}</span>
            <span class="mare-badge">Retriever: {stack['retriever']}</span>
            <span class="mare-badge">Reranker: {stack['reranker']}</span>
            <span class="mare-badge">Output: {stack['output_mode']}</span>
          </div>
          <p class="mare-mini" style="margin-top:0.85rem;">{stack['summary']}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_recent_runs(st, history: dict) -> None:
    entries = history.get("entries", [])
    st.markdown("**Recent runs**")
    if not entries:
        st.caption("No saved UI runs yet.")
        return
    for entry in reversed(entries[-5:]):
        source_label = ", ".join(entry.get("filenames", [])[:2])
        if entry.get("source_count", 0) > 2:
            source_label += " …"
        st.markdown(
            f"""
            <div class="mare-card" style="margin-bottom:0.75rem;">
              <div class="mare-label">{entry.get('timestamp', '')}</div>
              <div class="mare-value">{entry.get('query', '')}</div>
              <p class="mare-mini" style="margin-top:0.55rem;"><strong>Sources:</strong> {source_label or '[none]'}</p>
              <p class="mare-mini"><strong>Citation:</strong> {entry.get('citation', '') or '[no citation available]'}</p>
              <p class="mare-mini"><strong>Stack:</strong> {entry.get('stack', {}).get('parser', '')} / {entry.get('stack', {}).get('retriever', '')}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )


def _render_grounded_summary(st, summary: dict) -> None:
    st.subheader("Grounded Summary")
    overview = summary.get("overview") or "No grounded evidence found."
    st.markdown(
        f"""
        <div class="mare-card" style="margin-bottom:0.9rem;">
          <div class="mare-label">Overview</div>
          <div class="mare-value">{overview}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    highlights = summary.get("highlights") or []
    if not highlights:
        st.caption("No grounded summary highlights are available for this run.")
        return
    for index, item in enumerate(highlights, start=1):
        st.markdown(
            f"""
            <div class="mare-card" style="margin-bottom:0.75rem;">
              <div class="mare-label">Highlight {index}</div>
              <div class="mare-value">{item.get('citation') or '[no citation available]'}</div>
              <p class="mare-mini" style="margin-top:0.55rem;"><strong>Snippet:</strong> {item.get('snippet') or '[no snippet available]'}</p>
              <p class="mare-mini"><strong>Reason:</strong> {item.get('reason') or '[no reason available]'}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )


def _render_grounded_findings(st, findings: dict) -> None:
    st.subheader("Grounded Findings")
    if not findings:
        st.caption("No grounded findings are available for this run.")
        return

    for finding_type in ("actions", "requirements", "risks", "deadlines"):
        payload = findings.get(finding_type, {})
        items = payload.get("items") or []
        label = finding_type.title()
        with st.expander(f"{label} ({len(items)})", expanded=(finding_type == "actions" and bool(items))):
            st.caption(payload.get("overview") or f"No grounded {finding_type} found.")
            if not items:
                continue
            for index, item in enumerate(items, start=1):
                score = item.get("score")
                score_label = f"{score:.3f}" if isinstance(score, (int, float)) else "n/a"
                st.markdown(
                    f"""
                    <div class="mare-card" style="margin-bottom:0.75rem;">
                      <div class="mare-label">{label[:-1] if label.endswith('s') else label} {index}</div>
                      <div class="mare-value">{item.get('snippet') or '[no snippet available]'}</div>
                      <p class="mare-mini" style="margin-top:0.55rem;"><strong>Citation:</strong> {item.get('citation') or '[no citation available]'}</p>
                      <p class="mare-mini"><strong>Signal:</strong> {item.get('signal') or '[no signal]'}</p>
                      <p class="mare-mini"><strong>Score:</strong> {score_label}</p>
                      <p class="mare-mini"><strong>Reason:</strong> {item.get('reason') or '[no reason available]'}</p>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )


def _render_evidence_brief(st, evidence_brief: dict) -> None:
    st.subheader("Evidence Brief")
    if not evidence_brief:
        st.caption("No evidence brief is available for this run.")
        return

    support = evidence_brief.get("support") or {}
    source_diversity = evidence_brief.get("source_diversity") or {}
    sources = evidence_brief.get("source_documents") or []
    proof_assets = evidence_brief.get("available_proof_assets") or []
    st.markdown(
        f"""
        <div class="mare-card" style="margin-bottom:0.9rem;">
          <div class="mare-label">Trust Snapshot</div>
          <div class="mare-value">{evidence_brief.get('overview') or 'No evidence brief available.'}</div>
          <p class="mare-mini" style="margin-top:0.55rem;"><strong>Support:</strong> {support.get('label') or '[unknown]'}</p>
          <p class="mare-mini"><strong>Source coverage:</strong> {source_diversity.get('label') or '[unknown]'}</p>
          <p class="mare-mini"><strong>Sources:</strong> {', '.join(sources) if sources else '[none]'}</p>
          <p class="mare-mini"><strong>Proof assets:</strong> {', '.join(proof_assets) if proof_assets else '[none]'}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    cols = st.columns(2)
    with cols[0]:
        st.markdown("**Evidence gaps**")
        for item in evidence_brief.get("evidence_gaps") or []:
            st.caption(item)
    with cols[1]:
        st.markdown("**Next questions**")
        for item in evidence_brief.get("next_questions") or []:
            st.caption(item)
    conflict_hints = evidence_brief.get("conflict_hints") or []
    if conflict_hints:
        st.markdown("**Conflict hints**")
        for item in conflict_hints:
            st.caption(item.get("message") or "Potentially conflicting evidence signals were detected.")


def _render_review_snapshot(st, review: dict) -> None:
    st.subheader("Document Review")
    if not review:
        st.caption("No grounded review is available for this run.")
        return

    best = review.get("best_evidence", {})
    support = review.get("support") or {}
    finding_counts = review.get("finding_counts") or {}
    st.markdown(
        f"""
        <div class="mare-card" style="margin-bottom:1rem;">
          <div class="mare-label">Review Overview</div>
          <div class="mare-value">{review.get('overview') or 'No grounded review available.'}</div>
          <p class="mare-mini" style="margin-top:0.7rem;"><strong>Support:</strong> {support.get('label') or '[no support label]'}</p>
          <p class="mare-mini"><strong>Primary citation:</strong> {best.get('citation') or '[no citation available]'}</p>
          <p class="mare-mini"><strong>Findings:</strong> actions={finding_counts.get('actions', 0)}, requirements={finding_counts.get('requirements', 0)}, risks={finding_counts.get('risks', 0)}, deadlines={finding_counts.get('deadlines', 0)}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    highlights = review.get("highlights") or []
    if highlights:
        for index, item in enumerate(highlights, start=1):
            st.markdown(
                f"""
                <div class="mare-card" style="margin-bottom:0.75rem;">
                  <div class="mare-label">Review Highlight {index}</div>
                  <div class="mare-value">{item}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def _resolved_image_path(*candidates: str) -> Path | None:
    for candidate in candidates:
        if not candidate:
            continue
        path = Path(candidate)
        if path.is_file():
            return path
    return None


def _resolve_retriever_choice(retriever_key: str) -> tuple[str, str]:
    from mare.extensions import recommended_retriever_key

    if retriever_key != "smart":
        return retriever_key, ""
    recommended_key = recommended_retriever_key()
    if recommended_key == "fastembed":
        return "fastembed", "Smart default promoted to FastEmbed semantic retrieval."
    if recommended_key == "hybrid-semantic":
        return "hybrid-semantic", "Smart default promoted to Hybrid semantic + lexical retrieval."
    return "builtin", "Smart default fell back to Built-in lexical retrieval because FastEmbed and sentence-transformers are not installed."


def _retriever_label_for_value(value: str) -> str:
    return next(label for label, meta in RETRIEVER_OPTIONS.items() if meta["value"] == value)


def _build_runtime(parser_key: str, retriever_key: str, reranker_key: str, qdrant_url: str, qdrant_collection: str, qdrant_index_before_query: bool):
    from mare.api import MAREApp, load_document
    from mare.extensions import (
        ColPaliVisualRetriever,
        FAISSRetriever,
        FastEmbedReranker,
        FastEmbedRetriever,
        HybridSemanticRetriever,
        MAREConfig,
        QdrantHybridRetriever,
        QdrantIndexer,
        SentenceTransformersRetriever,
    )
    from mare.types import Modality

    retriever_factories = {}
    reranker = None
    resolved_retriever_key, retriever_resolution_note = _resolve_retriever_choice(retriever_key)

    if resolved_retriever_key == "sentence-transformers":
        retriever_factories[Modality.TEXT] = lambda documents: SentenceTransformersRetriever(documents)
    elif resolved_retriever_key == "hybrid-semantic":
        retriever_factories[Modality.TEXT] = lambda documents: HybridSemanticRetriever(documents)
    elif resolved_retriever_key == "fastembed":
        retriever_factories[Modality.TEXT] = lambda documents: FastEmbedRetriever(documents)
    elif resolved_retriever_key == "colpali-visual":
        retriever_factories[Modality.TEXT] = lambda documents: ColPaliVisualRetriever(documents)
    elif resolved_retriever_key == "faiss":
        retriever_factories[Modality.TEXT] = lambda documents: FAISSRetriever(documents)
    elif resolved_retriever_key == "qdrant":
        retriever_factories[Modality.TEXT] = lambda documents: QdrantHybridRetriever(
            documents,
            collection_name=qdrant_collection,
            url=qdrant_url,
            vector_name="text",
        )

    if reranker_key == "fastembed":
        reranker = FastEmbedReranker()

    config = MAREConfig(
        retriever_factories=retriever_factories,
        reranker=reranker,
        retriever_label=_retriever_label_for_value(resolved_retriever_key),
        retriever_resolution_note=retriever_resolution_note,
    )

    def _loader(source_paths: list[Path], reuse: bool):
        apps = [load_document(source_path=source_path, reuse=reuse, parser=parser_key, config=config) for source_path in source_paths]
        if len(apps) == 1:
            return apps[0]
        corpus_paths = [app.corpus_path for app in apps if app.corpus_path is not None]
        multi_app = MAREApp.from_corpora(corpus_paths, config=config)
        multi_app.source_documents = [source_path for source_path in source_paths]
        multi_app.source_pdfs = [source_path for source_path in source_paths]
        return multi_app

    def _maybe_index(app):
        if resolved_retriever_key != "qdrant" or not qdrant_index_before_query:
            return None
        indexer = QdrantIndexer(
            collection_name=qdrant_collection,
            url=qdrant_url,
            vector_name="text",
        )
        indexed = indexer.index_documents(app.documents, recreate=True)
        return {"backend": "qdrant", "indexed_documents": indexed, "collection": qdrant_collection}

    runtime_details = {
        "configured_retriever": retriever_key,
        "resolved_retriever": resolved_retriever_key,
        "retriever_resolution_note": retriever_resolution_note,
    }

    return _loader, _maybe_index, runtime_details


def _build_output_preview(app, query: str, top_k: int, output_mode: str):
    if output_mode == "mare":
        return None
    if output_mode == "langchain":
        retriever = app.as_langchain_retriever(top_k=top_k)
        return {
            "framework": "langchain",
            "results": [
                {"page_content": doc.page_content, "metadata": doc.metadata}
                for doc in retriever.invoke(query)
            ],
        }
    if output_mode == "langgraph":
        tool = app.as_langgraph_tool(top_k=top_k)
        return {
            "framework": "langgraph",
            "tool_name": getattr(tool, "name", "mare_retrieve"),
            "result": tool.invoke({"query": query}),
        }
    if output_mode == "llamaindex":
        from llama_index.core.schema import QueryBundle

        retriever = app.as_llamaindex_retriever(top_k=top_k)
        nodes = retriever.retrieve(QueryBundle(query))
        return {
            "framework": "llamaindex",
            "results": [
                {
                    "score": node.score,
                    "text": getattr(node.node, "text", ""),
                    "metadata": getattr(node.node, "metadata", {}),
                }
                for node in nodes
            ],
        }
    return None


def _run_query(st, uploaded_files, query: str, top_k: int, stack_controls: dict):
    if not query.strip():
        st.warning("Enter a question first.")
        return

    temp_dir = Path(tempfile.gettempdir()) / "mare_streamlit"
    temp_dir.mkdir(parents=True, exist_ok=True)
    uploaded_sources = uploaded_files if isinstance(uploaded_files, list) else [uploaded_files]
    source_paths: list[Path] = []
    for item in uploaded_sources:
        source_path = temp_dir / item.name
        source_path.write_bytes(item.getvalue())
        source_paths.append(source_path)

    parser_key = stack_controls["parser"]["value"]
    retriever_key = stack_controls["retriever"]["value"]
    reranker_key = stack_controls["reranker"]["value"]
    output_mode = stack_controls["output"]["value"]

    loader, maybe_index, runtime_details = _build_runtime(
        parser_key=parser_key,
        retriever_key=retriever_key,
        reranker_key=reranker_key,
        qdrant_url=stack_controls["qdrant_url"],
        qdrant_collection=stack_controls["qdrant_collection"],
        qdrant_index_before_query=stack_controls["qdrant_index_before_query"],
    )

    try:
        with st.spinner("Ingesting documents and retrieving best evidence..."):
            app = loader(source_paths=source_paths, reuse=stack_controls["reuse_corpus"])
            indexing_summary = maybe_index(app)
            corpus_path = app.corpus_path
            explanation = app.explain(query=query, top_k=top_k)
            output_preview = _build_output_preview(app, query=query, top_k=top_k, output_mode=output_mode)
    except Exception as exc:  # noqa: BLE001
        st.error(str(exc))
        return

    stack_summary = {
        "parser": next(label for label, meta in PARSER_OPTIONS.items() if meta["value"] == parser_key),
        "retriever": _retriever_label_for_value(retriever_key),
        "resolved_retriever": _retriever_label_for_value(runtime_details["resolved_retriever"]),
        "reranker": next(label for label, meta in RERANKER_OPTIONS.items() if meta["value"] == reranker_key),
        "output_mode": next(label for label, meta in OUTPUT_OPTIONS.items() if meta["value"] == output_mode),
        "summary": (
            f"This run used the {next(label for label, meta in PARSER_OPTIONS.items() if meta['value'] == parser_key)} parser, "
            f"{_retriever_label_for_value(runtime_details['resolved_retriever'])} retrieval, "
            f"and {next(label for label, meta in RERANKER_OPTIONS.items() if meta['value'] == reranker_key)} reranking "
            f"across {len(source_paths)} document{'s' if len(source_paths) != 1 else ''}."
        ),
        "indexing": indexing_summary,
        "retriever_resolution_note": runtime_details["retriever_resolution_note"],
    }
    run_signature = _build_run_signature(
        uploaded_filenames=[item.name for item in uploaded_sources],
        query=query,
        top_k=top_k,
        stack_controls=stack_controls,
    )
    evidence_payload = hits_to_evidence_payload(query=query, hits=explanation.fused_results)

    st.session_state["mare_result"] = {
        "query": query,
        "corpus_path": str(corpus_path) if corpus_path else "",
        "corpus_paths": [str(path) for path in app.corpus_paths],
        "explanation": explanation,
        "grounded_summary": evidence_payload.get("summary", {"overview": "No grounded evidence found.", "highlight_count": 0, "highlights": []}),
        "grounded_findings": evidence_payload.get("findings", {}),
        "evidence_brief": evidence_payload.get("evidence_brief", {}),
        "grounded_review": evidence_payload.get("review", {}),
        "filenames": [item.name for item in uploaded_sources],
        "app": app,
        "stack": stack_summary,
        "output_preview": output_preview,
        "run_signature": run_signature,
    }
    st.session_state["mare_ui_history"] = _append_ui_session_history(
        filenames=[item.name for item in uploaded_sources],
        query=query,
        explanation=explanation,
        stack=stack_summary,
    )


def main() -> None:
    st = _require_streamlit()

    st.set_page_config(page_title="MARE Demo", layout="wide")
    _inject_styles(st)

    if "mare_result" not in st.session_state:
        st.session_state["mare_result"] = None
    if "mare_query_input" not in st.session_state:
        st.session_state["mare_query_input"] = ""
    if "mare_submit_via_enter" not in st.session_state:
        st.session_state["mare_submit_via_enter"] = False
    if "mare_ui_history" not in st.session_state:
        st.session_state["mare_ui_history"] = _load_ui_session_history()

    st.markdown(
        """
        <div class="mare-hero">
          <h1 style="margin:0 0 0.35rem 0;">MARE Playground</h1>
          <p style="margin:0; font-size:1.05rem; color:#334155;">
            Explore MARE as a grounded document evidence layer for developers and agents: ask a question, inspect the exact evidence, and see the structured output behind the result.
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.sidebar:
        st.header("MARE Playground")
        mode = st.radio(
            "Mode",
            ["Basic", "Advanced"],
            index=0,
            help="Basic keeps the UI simple. Advanced exposes parser, retriever, reranker, and framework output choices.",
        )

        st.markdown("**How To Test**")
        st.write("1. Upload one or more documents")
        st.write("2. Ask a concrete instruction question")
        st.write("3. Inspect the citation, any available visual proof, and the agent-facing output shape")
        st.caption("Recommended starting point: `Basic` mode, which uses the built-in parser and a smart retrieval default that prefers hybrid evidence retrieval when available.")
        st.markdown("**Good test prompts**")
        st.code("partially reinstall the set screws if they fall out", language="text")
        st.code("how do I connect the AC adapter", language="text")
        st.code("show me the comparison table", language="text")

        if mode == "Advanced":
            st.markdown("---")
            st.subheader("Stack Controls")
            parser_label = st.selectbox("Parser", _option_labels(PARSER_OPTIONS), index=0)
            parser_meta = _selected_option_payload(PARSER_OPTIONS, parser_label)
            st.caption(f"{parser_meta['description']} Install: `{parser_meta['extra']}`")

            retriever_label = st.selectbox("Retriever", _option_labels(RETRIEVER_OPTIONS), index=0)
            retriever_meta = _selected_option_payload(RETRIEVER_OPTIONS, retriever_label)
            st.caption(f"{retriever_meta['description']} Install: `{retriever_meta['extra']}`")
            if retriever_meta["value"] == "hybrid-semantic":
                st.info("Recommended advanced option for most real documents. It preserves MARE's evidence-first lexical behavior and adds semantic retrieval on top.")

            reranker_label = st.selectbox("Reranker", _option_labels(RERANKER_OPTIONS), index=0)
            reranker_meta = _selected_option_payload(RERANKER_OPTIONS, reranker_label)
            st.caption(f"{reranker_meta['description']} Install: `{reranker_meta['extra']}`")

            output_label = st.selectbox("Output Preview", _option_labels(OUTPUT_OPTIONS), index=0)
            output_meta = _selected_option_payload(OUTPUT_OPTIONS, output_label)
            st.caption(f"{output_meta['description']} Install: `{output_meta['extra']}`")

            reuse_corpus = st.checkbox("Reuse ingested corpus if available", value=False)

            qdrant_url = "http://localhost:6333"
            qdrant_collection = "mare-docs"
            qdrant_index_before_query = False
            if retriever_meta["value"] == "qdrant":
                qdrant_url = st.text_input("Qdrant URL", value="http://localhost:6333")
                qdrant_collection = st.text_input("Qdrant collection", value="mare-docs")
                qdrant_index_before_query = st.checkbox("Index current documents into Qdrant before retrieval", value=False)
        else:
            parser_label = "Builtin PDF"
            retriever_label = "Smart default (Recommended)"
            reranker_label = "None"
            output_label = "MARE evidence"
            reuse_corpus = False
            qdrant_url = "http://localhost:6333"
            qdrant_collection = "mare-docs"
            qdrant_index_before_query = False

        stack_controls = {
            "parser": _selected_option_payload(PARSER_OPTIONS, parser_label),
            "retriever": _selected_option_payload(RETRIEVER_OPTIONS, retriever_label),
            "reranker": _selected_option_payload(RERANKER_OPTIONS, reranker_label),
            "output": _selected_option_payload(OUTPUT_OPTIONS, output_label),
            "reuse_corpus": reuse_corpus,
            "qdrant_url": qdrant_url,
            "qdrant_collection": qdrant_collection,
            "qdrant_index_before_query": qdrant_index_before_query,
            "mode": mode,
        }

        st.markdown("---")
        st.caption("The Streamlit app is the visual playground. The Python package is the deeper document evidence layer that developers and agents can call directly.")
        if mode == "Basic":
            resolved_retriever_key, retriever_resolution_note = _resolve_retriever_choice("smart")
            st.success(
                f"Using the recommended default stack: built-in parser + {_retriever_label_for_value(resolved_retriever_key)}."
            )
            if retriever_resolution_note:
                st.caption(retriever_resolution_note)
        st.markdown("---")
        _render_recent_runs(st, st.session_state["mare_ui_history"])
        if st.button("Clear recent runs"):
            st.session_state["mare_ui_history"] = _clear_ui_session_history()
            st.success("Cleared saved UI run history.")

    _render_getting_started(st)
    uploaded_pdf = st.file_uploader("Upload one or more documents", type=["pdf", "md", "markdown", "txt", "docx"], accept_multiple_files=True)
    query = st.text_input(
        "Ask a question about the documents",
        key="mare_query_input",
        placeholder=f"Try: {STARTER_PROMPTS[1]}",
        on_change=lambda: st.session_state.__setitem__("mare_submit_via_enter", True),
    )
    top_k = st.slider("How many results to show", min_value=1, max_value=5, value=3)
    st.caption("Press Enter in the question box or click Ask MARE.")
    submitted = st.button("Ask MARE")

    if not uploaded_pdf:
        _render_upload_empty_state(st)
        return

    if submitted or st.session_state.get("mare_submit_via_enter"):
        st.session_state["mare_submit_via_enter"] = False
        _run_query(st, uploaded_pdf, query, top_k, stack_controls)

    result = st.session_state.get("mare_result")
    current_signature = _build_run_signature(
        uploaded_filenames=[item.name for item in uploaded_pdf],
        query=query,
        top_k=top_k,
        stack_controls=stack_controls,
    )
    result_is_current = _result_matches_signature(result, current_signature)

    if result and not result_is_current:
        st.warning(
            "The current file, query, or stack controls changed since the last run. Click `Ask MARE` to refresh the evidence with the current settings."
        )
        st.markdown(
            """
            <div class="mare-card" style="margin-bottom:1rem;">
              <div class="mare-label">Current configuration changed</div>
              <div class="mare-value">Result hidden until rerun</div>
              <p class="mare-mini" style="margin-top:0.7rem;">
                This avoids showing evidence from an older parser, retriever, reranker, or query after you change the controls.
              </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        result = None

    if not result:
        st.markdown(
            f"""
            <div class="mare-card">
              <div class="mare-label">Uploaded documents</div>
              <div class="mare-value">{", ".join(item.name for item in uploaded_pdf[:3])}{' …' if len(uploaded_pdf) > 3 else ''}</div>
              <p class="mare-mini" style="margin-top:0.8rem;">
                Ask a question to see the best matching evidence, the exact snippet, any available visual proof, and the structured stack/output MARE would expose to code or agents.
              </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    explanation = result["explanation"]
    if not explanation.fused_results:
        st.error("No matching evidence found.")
        return

    best = explanation.fused_results[0]
    app = result.get("app")

    st.markdown(
        f"""
        <div class="mare-card" style="margin-bottom:1rem;">
          <div class="mare-label">Current question</div>
          <div class="mare-value">{result["query"]}</div>
          <p class="mare-mini" style="margin-top:0.6rem;">
            Documents: {", ".join(result["filenames"][:3])}{' …' if len(result["filenames"]) > 3 else ''} <br/>
            Corpora: {len(result.get("corpus_paths") or ([result["corpus_path"]] if result["corpus_path"] else []))}
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    metric_cols = st.columns(4)
    with metric_cols[0]:
        _render_metric_card(st, "Best page/region", str(best.page))
    with metric_cols[1]:
        _render_metric_card(st, "Intent", explanation.plan.intent.replace("_", " "))
    with metric_cols[2]:
        _render_metric_card(st, "Source document", _source_label(best))
    with metric_cols[3]:
        _render_metric_card(st, "Object", best.object_type or "page")

    left, right = st.columns([0.92, 1.08])

    with left:
        st.subheader("Answer Evidence")
        st.markdown(f"**Source document:** {_source_label(best)}")
        st.markdown(f"**Citation:** {format_evidence_citation(title=best.title, page=best.page, metadata=best.metadata)}")
        st.markdown(f"**Best page/region:** {best.page}")
        st.markdown(f"**Score:** {best.score}")
        st.markdown(f"**Object type:** {best.object_type or 'page'}")
        st.markdown(f"**Why it matched:** {best.reason}")
        st.markdown("**Snippet**")
        st.markdown(
            f"<div class='mare-snippet'>{best.snippet or '[no snippet available]'}</div>",
            unsafe_allow_html=True,
        )
        st.markdown("")
        st.markdown(
            f"""
            <div class="mare-card">
              <div class="mare-label">Evidence assets</div>
              <p class="mare-mini"><strong>Page image:</strong> {best.page_image_path or '[no page image available]'}</p>
              <p class="mare-mini"><strong>Highlighted image:</strong> {best.highlight_image_path or '[no highlight available]'}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with right:
        st.subheader("Visual Proof")
        image_path = _resolved_image_path(best.highlight_image_path, best.page_image_path)
        if image_path is not None:
            caption = f"Highlighted page {best.page}" if best.highlight_image_path else f"Page {best.page}"
            st.image(str(image_path), caption=caption, width="stretch")
        else:
            st.info("No page image is available for this result. Use the citation and snippet as the primary proof.")

    preview_left, preview_right = st.columns([0.7, 1.3])
    with preview_left:
        _render_object_preview(st, explanation)
    with preview_right:
        _render_stack_summary(st, result["stack"])

    st.markdown("")
    _render_evidence_brief(st, result.get("evidence_brief") or {})

    st.markdown("")
    _render_review_snapshot(st, result.get("grounded_review") or {})

    st.markdown("")
    _render_grounded_summary(st, result.get("grounded_summary") or {"overview": "No grounded evidence found.", "highlight_count": 0, "highlights": []})

    st.markdown("")
    _render_grounded_findings(st, result.get("grounded_findings") or {})

    st.markdown("")
    _render_page_objects(st, app.get_page_objects(best.doc_id, limit=6) if app else [])

    if len(explanation.fused_results) > 1:
        st.subheader("Other Evidence")
        candidate_cols = st.columns(min(3, len(explanation.fused_results) - 1))
        for idx, hit in enumerate(explanation.fused_results[1:], start=2):
            col = candidate_cols[(idx - 2) % len(candidate_cols)]
            with col:
                _render_candidate(st, hit, idx)

    output_preview = result.get("output_preview")
    if output_preview:
        with st.expander("Framework Output Preview"):
            st.json(output_preview)

    with st.expander("Debug details"):
        st.write(
            {
                "intent": explanation.plan.intent,
                "selected_modalities": [item.value for item in explanation.plan.selected_modalities],
                "discarded_modalities": [item.value for item in explanation.plan.discarded_modalities],
                "confidence": explanation.plan.confidence,
                "rationale": explanation.plan.rationale,
                "corpus": result["corpus_path"],
                "stack": result["stack"],
            }
        )


if __name__ == "__main__":
    main()
