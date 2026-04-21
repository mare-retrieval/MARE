from pathlib import Path

from mare.eval import EvalCase, evaluate_cases, evaluate_corpus, load_eval_cases
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
