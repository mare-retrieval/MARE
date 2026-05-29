import json
from types import SimpleNamespace
from pathlib import Path

from mare.streamlit_app import (
    STARTER_PROMPTS,
    _append_ui_session_history,
    _build_run_signature,
    _clear_ui_session_history,
    _load_ui_session_history,
    _render_grounded_findings,
    _render_getting_started,
    _render_review_snapshot,
    _resolve_retriever_choice,
    _result_matches_signature,
    _render_upload_empty_state,
)


def _stack_controls(**overrides):
    controls = {
        "mode": "Advanced",
        "parser": {"value": "builtin"},
        "retriever": {"value": "smart"},
        "reranker": {"value": "none"},
        "output": {"value": "mare"},
        "reuse_corpus": False,
        "qdrant_url": "http://localhost:6333",
        "qdrant_collection": "mare-docs",
        "qdrant_index_before_query": False,
    }
    controls.update(overrides)
    return controls


def test_run_signature_changes_when_stack_changes() -> None:
    baseline = _build_run_signature(["manual.pdf"], "how do I connect the AC adapter", 3, _stack_controls())
    changed = _build_run_signature(
        ["manual.pdf"],
        "how do I connect the AC adapter",
        3,
        _stack_controls(retriever={"value": "sentence-transformers"}),
    )

    assert baseline != changed


def test_smart_retriever_prefers_hybrid_when_sentence_transformers_is_available(monkeypatch) -> None:
    monkeypatch.setattr("mare.extensions.recommended_retriever_key", lambda: "hybrid-semantic")

    resolved, note = _resolve_retriever_choice("smart")

    assert resolved == "hybrid-semantic"
    assert "Hybrid semantic" in note


def test_smart_retriever_falls_back_to_builtin_without_sentence_transformers(monkeypatch) -> None:
    monkeypatch.setattr("mare.extensions.recommended_retriever_key", lambda: "builtin")

    resolved, note = _resolve_retriever_choice("smart")

    assert resolved == "builtin"
    assert "fell back" in note


def test_result_matches_signature_only_for_current_inputs() -> None:
    signature = _build_run_signature(["manual.pdf"], "configure wake on lan", 2, _stack_controls())
    result = {"run_signature": signature}

    assert _result_matches_signature(result, signature) is True

    different_signature = _build_run_signature(["manual.pdf"], "configure wake on lan", 4, _stack_controls())
    assert _result_matches_signature(result, different_signature) is False


def test_run_signature_changes_when_uploaded_file_set_changes() -> None:
    baseline = _build_run_signature(["manual-a.pdf"], "where is wake on lan discussed", 3, _stack_controls())
    changed = _build_run_signature(["manual-a.pdf", "manual-b.pdf"], "where is wake on lan discussed", 3, _stack_controls())

    assert baseline != changed


def test_ui_session_history_append_persists_recent_run(tmp_path: Path) -> None:
    history_path = tmp_path / "ui-history.json"
    explanation = SimpleNamespace(
        plan=SimpleNamespace(intent="semantic_lookup"),
        fused_results=[
            SimpleNamespace(
                title="Manual",
                page=10,
                metadata={"source": "manual.pdf"},
                object_type="procedure",
                snippet="Connect the AC adapter to the laptop.",
            )
        ],
    )
    stack = {
        "parser": "Builtin PDF",
        "retriever": "Smart default (Recommended)",
        "reranker": "None",
        "output_mode": "MARE evidence",
    }

    history = _append_ui_session_history(
        filenames=["manual.pdf"],
        query="how do I connect the AC adapter",
        explanation=explanation,
        stack=stack,
        path=history_path,
    )

    payload = json.loads(history_path.read_text())
    assert len(history["entries"]) == 1
    assert payload["entries"][0]["query"] == "how do I connect the AC adapter"
    assert payload["entries"][0]["citation"] == "manual.pdf | page 10"
    assert payload["entries"][0]["stack"]["parser"] == "Builtin PDF"


def test_ui_session_history_clear_removes_entries(tmp_path: Path) -> None:
    history_path = tmp_path / "ui-history.json"
    history_path.write_text(json.dumps({"created_at": "2026-01-01T00:00:00", "updated_at": "2026-01-01T00:00:00", "entries": [{"query": "test"}]}))

    history = _clear_ui_session_history(history_path)
    reloaded = _load_ui_session_history(history_path)

    assert history["entries"] == []
    assert reloaded["entries"] == []


def test_render_getting_started_shows_starter_prompts() -> None:
    calls = []

    class _FakeStreamlit:
        @staticmethod
        def markdown(body, unsafe_allow_html=False):
            calls.append((body, unsafe_allow_html))

    _render_getting_started(_FakeStreamlit())

    assert calls
    body, unsafe_allow_html = calls[0]
    assert unsafe_allow_html is True
    assert "Start Here" in body
    assert STARTER_PROMPTS[0] in body
    assert STARTER_PROMPTS[-1] in body


def test_render_upload_empty_state_mentions_example_folder() -> None:
    calls = []

    class _FakeStreamlit:
        @staticmethod
        def info(body):
            calls.append(("info", body))

        @staticmethod
        def markdown(body, unsafe_allow_html=False):
            calls.append(("markdown", body, unsafe_allow_html))

        @staticmethod
        def caption(body):
            calls.append(("caption", body))

    _render_upload_empty_state(_FakeStreamlit())

    assert any(call[0] == "info" and "Upload one or more documents" in call[1] for call in calls)
    assert any(call[0] == "caption" and "examples/mixed_docs" in call[1] for call in calls)


def test_render_grounded_findings_shows_action_items() -> None:
    calls = []

    class _Expander:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    class _FakeStreamlit:
        @staticmethod
        def subheader(body):
            calls.append(("subheader", body))

        @staticmethod
        def expander(label, expanded=False):
            calls.append(("expander", label, expanded))
            return _Expander()

        @staticmethod
        def caption(body):
            calls.append(("caption", body))

        @staticmethod
        def markdown(body, unsafe_allow_html=False):
            calls.append(("markdown", body, unsafe_allow_html))

    findings = {
        "actions": {
            "overview": "Found 1 grounded actions.",
            "items": [
                {
                    "snippet": "Submit the signed acknowledgement within 5 days of receipt.",
                    "citation": "policy.docx | page 2",
                    "signal": "Submit",
                    "score": 0.78,
                    "reason": "Matched policy action wording",
                }
            ],
        },
        "requirements": {"overview": "No grounded requirements found in the current evidence.", "items": []},
        "risks": {"overview": "No grounded risks found in the current evidence.", "items": []},
        "deadlines": {"overview": "No grounded deadlines found in the current evidence.", "items": []},
    }

    _render_grounded_findings(_FakeStreamlit(), findings)

    assert any(call[0] == "subheader" and call[1] == "Grounded Findings" for call in calls)
    assert any(call[0] == "expander" and call[1] == "Actions (1)" and call[2] is True for call in calls)
    assert any(call[0] == "markdown" and "policy.docx | page 2" in call[1] for call in calls)


def test_render_grounded_findings_handles_empty_payload() -> None:
    calls = []

    class _FakeStreamlit:
        @staticmethod
        def subheader(body):
            calls.append(("subheader", body))

        @staticmethod
        def caption(body):
            calls.append(("caption", body))

    _render_grounded_findings(_FakeStreamlit(), {})

    assert ("subheader", "Grounded Findings") in calls
    assert ("caption", "No grounded findings are available for this run.") in calls


def test_render_review_snapshot_shows_review_overview() -> None:
    calls = []

    class _FakeStreamlit:
        @staticmethod
        def subheader(body):
            calls.append(("subheader", body))

        @staticmethod
        def caption(body):
            calls.append(("caption", body))

        @staticmethod
        def markdown(body, unsafe_allow_html=False):
            calls.append(("markdown", body, unsafe_allow_html))

    review = {
        "overview": "Grounded review assembled from the best supporting evidence.",
        "best_evidence": {"citation": "manual.pdf | page 10"},
        "support": {"label": "Strong support"},
        "finding_counts": {"actions": 2, "requirements": 1, "risks": 0, "deadlines": 0},
        "highlights": ["Found 2 grounded results across 1 source.", "Support: Strong support"],
    }

    _render_review_snapshot(_FakeStreamlit(), review)

    assert ("subheader", "Document Review") in calls
    assert any(call[0] == "markdown" and "manual.pdf | page 10" in call[1] for call in calls)
    assert any(call[0] == "markdown" and "Review Highlight 1" in call[1] for call in calls)
