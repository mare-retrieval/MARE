from __future__ import annotations

import tempfile
from pathlib import Path


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
          <p class="mare-mini"><strong>Score:</strong> {hit.score}</p>
          <p class="mare-mini"><strong>Reason:</strong> {hit.reason}</p>
          <p class="mare-mini"><strong>Snippet:</strong> {hit.snippet or '[no snippet available]'}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _run_query(st, uploaded_pdf, query: str, top_k: int):
    from mare.ask import ask_pdf

    if not query.strip():
        st.warning("Enter a question first.")
        return

    temp_dir = Path(tempfile.gettempdir()) / "mare_streamlit"
    temp_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = temp_dir / uploaded_pdf.name
    pdf_path.write_bytes(uploaded_pdf.getvalue())

    with st.spinner("Ingesting PDF and retrieving best pages..."):
        corpus_path, explanation = ask_pdf(pdf_path=pdf_path, query=query, top_k=top_k, reuse=False)

    st.session_state["mare_result"] = {
        "query": query,
        "corpus_path": str(corpus_path),
        "explanation": explanation,
        "filename": uploaded_pdf.name,
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
          <h1 style="margin:0 0 0.35rem 0;">MARE</h1>
          <p style="margin:0; font-size:1.05rem; color:#334155;">
            Ask a document a question and inspect the exact page, snippet, and visual evidence.
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.sidebar:
        st.header("How To Test")
        st.write("1. Upload a PDF")
        st.write("2. Ask a concrete instruction question")
        st.write("3. Inspect the highlighted evidence")
        st.markdown("**Good test prompts**")
        st.code("partially reinstall the set screws if they fall out", language="text")
        st.code("what does MagSafe 3 refer to", language="text")
        st.code("show me the comparison table", language="text")

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
        st.info("Upload a PDF to start. The demo will render pages, retrieve evidence, and show the best page visually.")
        return

    if submitted or st.session_state.get("mare_submit_via_enter"):
        st.session_state["mare_submit_via_enter"] = False
        _run_query(st, uploaded_pdf, query, top_k)

    result = st.session_state.get("mare_result")
    if not result:
        st.markdown(
            f"""
            <div class="mare-card">
              <div class="mare-label">Uploaded file</div>
              <div class="mare-value">{uploaded_pdf.name}</div>
              <p class="mare-mini" style="margin-top:0.8rem;">
                Ask a question to see the best matching page, the exact snippet, and a highlighted evidence image.
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
        _render_metric_card(st, "Confidence", f"{explanation.plan.confidence:.2f}")

    left, right = st.columns([0.92, 1.08])

    with left:
        st.subheader("Answer Evidence")
        st.markdown(f"**Best page:** {best.page}")
        st.markdown(f"**Score:** {best.score}")
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
            st.image(str(image_path), caption=caption, use_column_width=True)
        else:
            st.warning("No page image available.")

    if len(explanation.fused_results) > 1:
        st.subheader("Other Candidate Pages")
        candidate_cols = st.columns(min(3, len(explanation.fused_results) - 1))
        for idx, hit in enumerate(explanation.fused_results[1:], start=2):
            col = candidate_cols[(idx - 2) % len(candidate_cols)]
            with col:
                _render_candidate(st, hit, idx)

    with st.expander("Debug details"):
        st.write(
            {
                "intent": explanation.plan.intent,
                "selected_modalities": [item.value for item in explanation.plan.selected_modalities],
                "discarded_modalities": [item.value for item in explanation.plan.discarded_modalities],
                "confidence": explanation.plan.confidence,
                "rationale": explanation.plan.rationale,
                "corpus": result["corpus_path"],
            }
        )


if __name__ == "__main__":
    main()
