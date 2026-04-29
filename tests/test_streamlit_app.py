from mare.streamlit_app import _build_run_signature, _result_matches_signature


def _stack_controls(**overrides):
    controls = {
        "mode": "Advanced",
        "parser": {"value": "builtin"},
        "retriever": {"value": "builtin"},
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
