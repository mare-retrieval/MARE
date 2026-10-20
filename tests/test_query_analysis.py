from mare.query_analysis import decompose_query


def test_decompose_query_splits_explicit_compound_questions() -> None:
    assert decompose_query("What is required and how do I submit it?", limit=3) == [
        "What is required",
        "how do I submit it",
    ]


def test_decompose_query_preserves_ordinary_conjunctions() -> None:
    assert decompose_query("Show tables and figures for onboarding", limit=3) == []


def test_decompose_query_supports_comparisons() -> None:
    assert decompose_query("Compare policy A versus policy B", limit=3) == ["policy A", "policy B"]
