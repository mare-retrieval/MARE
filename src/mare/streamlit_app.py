from __future__ import annotations

import tempfile
from pathlib import Path


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
    "Built-in lexical": {
        "value": "builtin",
        "description": "Uses MARE's default page and object-aware retrieval stack.",
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


def _render_candidate(st, hit, rank: int) -> None:
    st.markdown(
        f"""
        <div class="mare-card">
          <div class="mare-label">Candidate {rank}</div>
          <div class="mare-value">Page {hit.page}</div>
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


def _build_run_signature(uploaded_filename: str, query: str, top_k: int, stack_controls: dict) -> dict[str, object]:
    return {
        "filename": uploaded_filename,
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


def _build_runtime(parser_key: str, retriever_key: str, reranker_key: str, qdrant_url: str, qdrant_collection: str, qdrant_index_before_query: bool):
    from mare import (
        FAISSRetriever,
        FastEmbedReranker,
        HybridSemanticRetriever,
        MAREConfig,
        Modality,
        QdrantHybridRetriever,
        QdrantIndexer,
        SentenceTransformersRetriever,
        load_pdf,
    )

    retriever_factories = {}
    reranker = None

    if retriever_key == "sentence-transformers":
        retriever_factories[Modality.TEXT] = lambda documents: SentenceTransformersRetriever(documents)
    elif retriever_key == "hybrid-semantic":
        retriever_factories[Modality.TEXT] = lambda documents: HybridSemanticRetriever(documents)
    elif retriever_key == "faiss":
        retriever_factories[Modality.TEXT] = lambda documents: FAISSRetriever(documents)
    elif retriever_key == "qdrant":
        retriever_factories[Modality.TEXT] = lambda documents: QdrantHybridRetriever(
            documents,
            collection_name=qdrant_collection,
            url=qdrant_url,
            vector_name="text",
        )

    if reranker_key == "fastembed":
        reranker = FastEmbedReranker()

    config = MAREConfig(retriever_factories=retriever_factories, reranker=reranker)

    def _loader(pdf_path: Path, reuse: bool):
        return load_pdf(pdf_path=pdf_path, reuse=reuse, parser=parser_key, config=config)

    def _maybe_index(app):
        if retriever_key != "qdrant" or not qdrant_index_before_query:
            return None
        indexer = QdrantIndexer(
            collection_name=qdrant_collection,
            url=qdrant_url,
            vector_name="text",
        )
        indexed = indexer.index_documents(app.documents, recreate=True)
        return {"backend": "qdrant", "indexed_documents": indexed, "collection": qdrant_collection}

    return _loader, _maybe_index


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


def _run_query(st, uploaded_pdf, query: str, top_k: int, stack_controls: dict):
    if not query.strip():
        st.warning("Enter a question first.")
        return

    temp_dir = Path(tempfile.gettempdir()) / "mare_streamlit"
    temp_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = temp_dir / uploaded_pdf.name
    pdf_path.write_bytes(uploaded_pdf.getvalue())

    parser_key = stack_controls["parser"]["value"]
    retriever_key = stack_controls["retriever"]["value"]
    reranker_key = stack_controls["reranker"]["value"]
    output_mode = stack_controls["output"]["value"]

    loader, maybe_index = _build_runtime(
        parser_key=parser_key,
        retriever_key=retriever_key,
        reranker_key=reranker_key,
        qdrant_url=stack_controls["qdrant_url"],
        qdrant_collection=stack_controls["qdrant_collection"],
        qdrant_index_before_query=stack_controls["qdrant_index_before_query"],
    )

    try:
        with st.spinner("Ingesting PDF and retrieving best pages..."):
            app = loader(pdf_path=pdf_path, reuse=stack_controls["reuse_corpus"])
            indexing_summary = maybe_index(app)
            corpus_path = app.corpus_path
            explanation = app.explain(query=query, top_k=top_k)
            output_preview = _build_output_preview(app, query=query, top_k=top_k, output_mode=output_mode)
    except Exception as exc:  # noqa: BLE001
        st.error(str(exc))
        return

    stack_summary = {
        "parser": next(label for label, meta in PARSER_OPTIONS.items() if meta["value"] == parser_key),
        "retriever": next(label for label, meta in RETRIEVER_OPTIONS.items() if meta["value"] == retriever_key),
        "reranker": next(label for label, meta in RERANKER_OPTIONS.items() if meta["value"] == reranker_key),
        "output_mode": next(label for label, meta in OUTPUT_OPTIONS.items() if meta["value"] == output_mode),
        "summary": (
            f"This run used the {next(label for label, meta in PARSER_OPTIONS.items() if meta['value'] == parser_key)} parser, "
            f"{next(label for label, meta in RETRIEVER_OPTIONS.items() if meta['value'] == retriever_key)} retrieval, "
            f"and {next(label for label, meta in RERANKER_OPTIONS.items() if meta['value'] == reranker_key)} reranking."
        ),
        "indexing": indexing_summary,
    }
    run_signature = _build_run_signature(
        uploaded_filename=uploaded_pdf.name,
        query=query,
        top_k=top_k,
        stack_controls=stack_controls,
    )

    st.session_state["mare_result"] = {
        "query": query,
        "corpus_path": str(corpus_path),
        "explanation": explanation,
        "filename": uploaded_pdf.name,
        "app": app,
        "stack": stack_summary,
        "output_preview": output_preview,
        "run_signature": run_signature,
    }


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

    st.markdown(
        """
        <div class="mare-hero">
          <h1 style="margin:0 0 0.35rem 0;">MARE Playground</h1>
          <p style="margin:0; font-size:1.05rem; color:#334155;">
            Explore MARE as a PDF evidence layer for developers and agents: ask a question, inspect the exact page and snippet, and see the visual proof and structured output behind the result.
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
        st.write("1. Upload a PDF")
        st.write("2. Ask a concrete instruction question")
        st.write("3. Inspect the highlighted evidence, stack used, and agent-facing output shape")
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
                st.info("Recommended advanced option for most real PDFs. It preserves MARE's evidence-first lexical behavior and adds semantic retrieval on top.")

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
                qdrant_index_before_query = st.checkbox("Index current PDF into Qdrant before retrieval", value=False)
        else:
            parser_label = "Builtin PDF"
            retriever_label = "Built-in lexical"
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
        st.caption("The Streamlit app is the visual playground. The Python package is the deeper PDF evidence layer that developers and agents can call directly.")

    uploaded_pdf = st.file_uploader("Upload a PDF", type=["pdf"])
    query = st.text_input(
        "Ask a question about the document",
        key="mare_query_input",
        placeholder="Try: partially reinstall the set screws if they fall out",
        on_change=lambda: st.session_state.__setitem__("mare_submit_via_enter", True),
    )
    top_k = st.slider("How many results to show", min_value=1, max_value=5, value=3)
    st.caption("Press Enter in the question box or click Ask MARE.")
    submitted = st.button("Ask MARE")

    if uploaded_pdf is None:
        st.info("Upload a PDF to start. The demo will render pages, retrieve evidence, and show the stack used for the run.")
        return

    if submitted or st.session_state.get("mare_submit_via_enter"):
        st.session_state["mare_submit_via_enter"] = False
        _run_query(st, uploaded_pdf, query, top_k, stack_controls)

    result = st.session_state.get("mare_result")
    current_signature = _build_run_signature(
        uploaded_filename=uploaded_pdf.name,
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
              <div class="mare-label">Uploaded file</div>
              <div class="mare-value">{uploaded_pdf.name}</div>
              <p class="mare-mini" style="margin-top:0.8rem;">
                Ask a question to see the best matching page, the exact snippet, the highlighted evidence image, and the structured stack/output MARE would expose to code or agents.
              </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    explanation = result["explanation"]
    if not explanation.fused_results:
        st.error("No matching page found.")
        return

    best = explanation.fused_results[0]
    app = result.get("app")

    st.markdown(
        f"""
        <div class="mare-card" style="margin-bottom:1rem;">
          <div class="mare-label">Current question</div>
          <div class="mare-value">{result["query"]}</div>
          <p class="mare-mini" style="margin-top:0.6rem;">
            File: {result["filename"]} <br/>
            Corpus: {result["corpus_path"]}
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    metric_cols = st.columns(4)
    with metric_cols[0]:
        _render_metric_card(st, "Best Page", str(best.page))
    with metric_cols[1]:
        _render_metric_card(st, "Intent", explanation.plan.intent.replace("_", " "))
    with metric_cols[2]:
        _render_metric_card(st, "Modality", ", ".join(item.value for item in explanation.plan.selected_modalities))
    with metric_cols[3]:
        _render_metric_card(st, "Object", best.object_type or "page")

    left, right = st.columns([0.92, 1.08])

    with left:
        st.subheader("Answer Evidence")
        st.markdown(f"**Best page:** {best.page}")
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
        st.subheader("Highlighted Page")
        image_path = Path(best.highlight_image_path or best.page_image_path)
        if image_path.exists():
            caption = f"Highlighted page {best.page}" if best.highlight_image_path else f"Page {best.page}"
            st.image(str(image_path), caption=caption, width="stretch")
        else:
            st.warning("No page image available.")

    preview_left, preview_right = st.columns([0.7, 1.3])
    with preview_left:
        _render_object_preview(st, explanation)
    with preview_right:
        _render_stack_summary(st, result["stack"])

    st.markdown("")
    _render_page_objects(st, app.get_page_objects(best.doc_id, limit=6) if app else [])

    if len(explanation.fused_results) > 1:
        st.subheader("Other Candidate Pages")
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
