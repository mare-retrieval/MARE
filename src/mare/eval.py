from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from mare.api import MAREApp
from mare.demo import load_documents


@dataclass
class EvalCase:
    query: str
    expected_doc_id: str | None = None
    expected_page: int | None = None
    expected_object_type: str | None = None
    expect_no_result: bool = False
    top_k: int = 3


@dataclass
class EvalCaseResult:
    query: str
    top_k: int
    returned_doc_id: str | None
    returned_page: int | None
    returned_object_type: str | None
    returned_score: float | None
    page_hit: bool
    doc_hit: bool
    object_hit: bool
    no_result_correct: bool


@dataclass
class EvalSummary:
    total_cases: int
    page_hits: int
    doc_hits: int
    object_hits: int
    no_result_correct: int

    @property
    def page_hit_rate(self) -> float:
        return round(self.page_hits / self.total_cases, 4) if self.total_cases else 0.0

    @property
    def doc_hit_rate(self) -> float:
        return round(self.doc_hits / self.total_cases, 4) if self.total_cases else 0.0

    @property
    def object_hit_rate(self) -> float:
        return round(self.object_hits / self.total_cases, 4) if self.total_cases else 0.0

    @property
    def no_result_accuracy(self) -> float:
        return round(self.no_result_correct / self.total_cases, 4) if self.total_cases else 0.0


def load_eval_cases(path: str | Path) -> list[EvalCase]:
    payload = json.loads(Path(path).read_text())
    raw_cases = payload.get("cases", payload)
    return [EvalCase(**case) for case in raw_cases]


def evaluate_cases(app: MAREApp, cases: list[EvalCase]) -> tuple[EvalSummary, list[EvalCaseResult]]:
    results: list[EvalCaseResult] = []

    for case in cases:
        hit = app.best_match(case.query, top_k=case.top_k)
        returned_doc_id = hit.doc_id if hit else None
        returned_page = hit.page if hit else None
        returned_object_type = hit.object_type if hit and hit.object_type else None
        returned_score = hit.score if hit else None

        no_result_correct = case.expect_no_result and hit is None
        doc_hit = case.expected_doc_id is not None and returned_doc_id == case.expected_doc_id
        page_hit = case.expected_page is not None and returned_page == case.expected_page
        object_hit = case.expected_object_type is not None and returned_object_type == case.expected_object_type

        if case.expect_no_result and hit is not None:
            doc_hit = False
            page_hit = False
            object_hit = False

        results.append(
            EvalCaseResult(
                query=case.query,
                top_k=case.top_k,
                returned_doc_id=returned_doc_id,
                returned_page=returned_page,
                returned_object_type=returned_object_type,
                returned_score=returned_score,
                page_hit=page_hit,
                doc_hit=doc_hit,
                object_hit=object_hit,
                no_result_correct=no_result_correct,
            )
        )

    summary = EvalSummary(
        total_cases=len(results),
        page_hits=sum(1 for item in results if item.page_hit),
        doc_hits=sum(1 for item in results if item.doc_hit),
        object_hits=sum(1 for item in results if item.object_hit),
        no_result_correct=sum(1 for item in results if item.no_result_correct),
    )
    return summary, results


def evaluate_corpus(corpus_path: str | Path, eval_path: str | Path) -> tuple[EvalSummary, list[EvalCaseResult]]:
    documents = load_documents(Path(corpus_path))
    app = MAREApp.from_documents(documents)
    cases = load_eval_cases(eval_path)
    return evaluate_cases(app, cases)


def _format_output(summary: EvalSummary, results: list[EvalCaseResult]) -> dict:
    return {
        "summary": {
            **asdict(summary),
            "page_hit_rate": summary.page_hit_rate,
            "doc_hit_rate": summary.doc_hit_rate,
            "object_hit_rate": summary.object_hit_rate,
            "no_result_accuracy": summary.no_result_accuracy,
        },
        "results": [asdict(result) for result in results],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a MARE evaluation harness over a corpus and benchmark cases")
    parser.add_argument("--corpus", required=True, help="Path to a MARE corpus JSON file")
    parser.add_argument("--eval", required=True, help="Path to an evaluation JSON file")
    args = parser.parse_args()

    summary, results = evaluate_corpus(args.corpus, args.eval)
    print(json.dumps(_format_output(summary, results), indent=2))


if __name__ == "__main__":
    main()
