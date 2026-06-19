from pathlib import Path

import pytest
import sys
import types

from mare.eval import (
    EvalCase,
    EvalSummary,
    _format_comparison_output,
    compare_stacks,
    create_app_for_stack,
    evaluate_cases,
    evaluate_corpus,
    load_eval_cases,
)
from mare.types import Document, DocumentObject, ObjectType


def _docs() -> list[Document]:
    return [
        Document(
            doc_id="paper-hyde-p3",
            title="HyDE",
            page=3,
            text="HyDE uses hypothetical document generation and positional encoding context.",
            image_caption="Architecture diagram with retrieval pipeline.",
            layout_hints="figure",
            objects=[
                DocumentObject(
                    object_id="paper-hyde-p3:figure:1",
                    doc_id="paper-hyde-p3",
                    page=3,
                    object_type=ObjectType.FIGURE,
                    content="Figure 1 shows the retrieval architecture diagram.",
                    metadata={"label": "Figure 1"},
                )
            ],
            metadata={"signals": "figure"},
        ),
        Document(
            doc_id="paper-benchmark-p7",
            title="Benchmark",
            page=7,
            text="Table 2 compares retrieval models across recall and nDCG.",
            layout_hints="table",
            objects=[
                DocumentObject(
                    object_id="paper-benchmark-p7:table:1",
                    doc_id="paper-benchmark-p7",
                    page=7,
                    object_type=ObjectType.TABLE,
                    content="Table 2 compares retrieval models across recall and nDCG.",
                    metadata={"label": "Table 2"},
                )
            ],
            metadata={"signals": "table comparison"},
        ),
    ]


def test_load_eval_cases_reads_cases(tmp_path: Path) -> None:
    eval_file = tmp_path / "cases.json"
    eval_file.write_text(
        """
        {
          "cases": [
            {"query": "show me the diagram", "expected_page": 3, "expected_object_type": "figure"}
          ]
        }
        """
    )

    cases = load_eval_cases(eval_file)

    assert len(cases) == 1
    assert cases[0].query == "show me the diagram"
    assert cases[0].expected_page == 3


def test_evaluate_cases_reports_hits_and_no_result_accuracy() -> None:
    from mare import MAREApp

    app = MAREApp.from_documents(_docs())
    cases = [
        EvalCase(query="what is positional encoding", expected_doc_id="paper-hyde-p3", expected_page=3),
        EvalCase(query="show me the architecture diagram", expected_doc_id="paper-hyde-p3", expected_page=3, expected_object_type="figure"),
        EvalCase(query="quantum casserole banana waterfall", expect_no_result=True),
    ]

    summary, results = evaluate_cases(app, cases)

    assert summary.total_cases == 3
    assert summary.doc_hits >= 1
    assert summary.page_hits >= 1
    assert summary.object_hits >= 1
    assert len(results) == 3
    assert results[2].no_result_correct is True


def test_evaluate_corpus_runs_end_to_end(tmp_path: Path) -> None:
    corpus = tmp_path / "sample_corpus.json"
    corpus.write_text(Path("examples/sample_corpus.json").read_text())
    eval_file = tmp_path / "eval_cases.json"
    eval_file.write_text(Path("examples/eval_cases.json").read_text())

    summary, results = evaluate_corpus(corpus, eval_file)

    assert summary.total_cases == 4
    assert len(results) == 4


def test_create_app_for_stack_supports_builtin() -> None:
    app = create_app_for_stack(_docs(), "builtin")

    best = app.best_match("what is positional encoding")
    assert best is not None
    assert best.doc_id == "paper-hyde-p3"


def test_create_app_for_stack_supports_fastembed(monkeypatch) -> None:
    class _FakeTextEmbedding:
        def __init__(self, model_name: str) -> None:
            self.model_name = model_name

        def embed(self, texts):
            vectors = []
            for text in texts:
                lowered = text.lower()
                if "positional encoding" in lowered:
                    vectors.append([1.0, 0.0])
                elif "architecture diagram" in lowered:
                    vectors.append([0.0, 1.0])
                else:
                    vectors.append([0.5, 0.5])
            return vectors

    fake_fastembed = types.ModuleType("fastembed")
    fake_fastembed.TextEmbedding = _FakeTextEmbedding
    monkeypatch.setitem(sys.modules, "fastembed", fake_fastembed)

    app = create_app_for_stack(_docs(), "fastembed")
    best = app.best_match("what is positional encoding")

    assert best is not None
    assert best.doc_id == "paper-hyde-p3"
    assert "FastEmbed semantic match" in best.reason


def test_create_app_for_stack_supports_colpali_visual_without_page_images() -> None:
    app = create_app_for_stack(_docs(), "colpali-visual")

    with pytest.raises(RuntimeError, match="needs rendered PDF page images"):
        app.best_match("positional encoding")


def test_compare_stacks_returns_reports_for_multiple_modes(tmp_path: Path, monkeypatch) -> None:
    class _FakeSentenceTransformer:
        def __init__(self, model_name: str) -> None:
            self.model_name = model_name

        def encode(self, texts, **kwargs):
            vectors = []
            for text in texts:
                lowered = text.lower()
                if "positional encoding" in lowered:
                    vectors.append([1.0, 0.0])
                elif "architecture diagram" in lowered or "figure 1" in lowered:
                    vectors.append([0.0, 1.0])
                else:
                    vectors.append([0.5, 0.5])
            return vectors

    fake_st_module = types.ModuleType("sentence_transformers")
    fake_st_module.SentenceTransformer = _FakeSentenceTransformer
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake_st_module)

    class _FakeTextEmbedding:
        def __init__(self, model_name: str) -> None:
            self.model_name = model_name

        def embed(self, texts):
            return _FakeSentenceTransformer("bge-small").encode(texts)

    fake_fastembed = types.ModuleType("fastembed")
    fake_fastembed.TextEmbedding = _FakeTextEmbedding
    monkeypatch.setitem(sys.modules, "fastembed", fake_fastembed)

    corpus = tmp_path / "sample_corpus.json"
    corpus.write_text(Path("examples/sample_corpus.json").read_text())
    eval_file = tmp_path / "eval_cases.json"
    eval_file.write_text(Path("examples/eval_cases.json").read_text())

    reports = compare_stacks(corpus, eval_file, ["builtin", "fastembed", "hybrid-semantic"])

    assert set(reports) == {"builtin", "fastembed", "hybrid-semantic"}
    assert reports["builtin"][0].total_cases == 4
    assert reports["fastembed"][0].total_cases == 4
    assert reports["hybrid-semantic"][0].total_cases == 4


def test_format_comparison_output_recommends_best_stack() -> None:
    reports = {
        "builtin": (
            EvalSummary(total_cases=4, page_hits=2, doc_hits=2, object_hits=1, no_result_correct=1),
            [],
        ),
        "fastembed": (
            EvalSummary(total_cases=4, page_hits=3, doc_hits=3, object_hits=2, no_result_correct=1),
            [],
        ),
    }

    output = _format_comparison_output(reports)

    assert output["recommendation"]["best_stack"] == "fastembed"
    assert output["recommendation"]["ranking"][0]["stack"] == "fastembed"
    assert output["recommendation"]["ranking"][0]["score"] > output["recommendation"]["ranking"][1]["score"]
    assert "comparison" in output
