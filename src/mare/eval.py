from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from mare.api import MAREApp
from mare.demo import load_documents
from mare.extensions import (
    SUPPORTED_RETRIEVER_STACKS,
    config_for_retriever_stack,
)
from mare.integrations import hits_to_evidence_payload


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
    expect_no_result: bool
    returned_doc_id: str | None
    returned_page: int | None
    returned_object_type: str | None
    returned_score: float | None
    page_hit: bool
    doc_hit: bool
    object_hit: bool
    no_result_correct: bool
    support_status: str = "unknown"
    evidence_quality_status: str = "unknown"
    proof_asset_count: int = 0


@dataclass
class EvalSummary:
    total_cases: int
    page_hits: int
    doc_hits: int
    object_hits: int
    no_result_correct: int
    answerable_cases: int = 0
    high_quality: int = 0
    usable_or_high_quality: int = 0

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

    @property
    def high_quality_rate(self) -> float:
        return round(self.high_quality / self.answerable_cases, 4) if self.answerable_cases else 0.0

    @property
    def usable_quality_rate(self) -> float:
        return round(self.usable_or_high_quality / self.answerable_cases, 4) if self.answerable_cases else 0.0


SUPPORTED_STACKS = tuple(stack for stack in SUPPORTED_RETRIEVER_STACKS if stack != "smart")


def load_eval_cases(path: str | Path) -> list[EvalCase]:
    payload = json.loads(Path(path).read_text())
    raw_cases = payload.get("cases", payload)
    return [EvalCase(**case) for case in raw_cases]


def create_app_for_stack(documents, stack: str) -> MAREApp:
    if stack in SUPPORTED_STACKS:
        return MAREApp.from_documents(documents, config=config_for_retriever_stack(stack))
    raise ValueError(f"Unsupported stack '{stack}'. Expected one of: {', '.join(SUPPORTED_STACKS)}")


def evaluate_cases(app: MAREApp, cases: list[EvalCase]) -> tuple[EvalSummary, list[EvalCaseResult]]:
    results: list[EvalCaseResult] = []

    for case in cases:
        hits = app.retrieve(case.query, top_k=case.top_k)
        hit = hits[0] if hits else None
        evidence_payload = hits_to_evidence_payload(case.query, hits)
        evidence_brief = evidence_payload.get("evidence_brief") or {}
        support = evidence_brief.get("support") or {}
        evidence_quality = evidence_brief.get("evidence_quality") or {}
        returned_doc_id = hit.doc_id if hit else None
        returned_page = hit.page if hit else None
        returned_object_type = hit.object_type if hit and hit.object_type else None
        returned_score = hit.score if hit else None
        support_status = str(support.get("status") or "unknown")
        evidence_quality_status = str(evidence_quality.get("status") or "unknown")
        proof_asset_count = len(evidence_brief.get("available_proof_assets") or [])

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
                expect_no_result=case.expect_no_result,
                returned_doc_id=returned_doc_id,
                returned_page=returned_page,
                returned_object_type=returned_object_type,
                returned_score=returned_score,
                page_hit=page_hit,
                doc_hit=doc_hit,
                object_hit=object_hit,
                no_result_correct=no_result_correct,
                support_status=support_status,
                evidence_quality_status=evidence_quality_status,
                proof_asset_count=proof_asset_count,
            )
        )

    answerable_results = [item for item in results if not item.expect_no_result]
    summary = EvalSummary(
        total_cases=len(results),
        page_hits=sum(1 for item in results if item.page_hit),
        doc_hits=sum(1 for item in results if item.doc_hit),
        object_hits=sum(1 for item in results if item.object_hit),
        no_result_correct=sum(1 for item in results if item.no_result_correct),
        answerable_cases=len(answerable_results),
        high_quality=sum(1 for item in answerable_results if item.evidence_quality_status == "high"),
        usable_or_high_quality=sum(
            1 for item in answerable_results if item.evidence_quality_status in {"high", "usable"}
        ),
    )
    return summary, results


def evaluate_corpus(corpus_path: str | Path, eval_path: str | Path) -> tuple[EvalSummary, list[EvalCaseResult]]:
    documents = load_documents(Path(corpus_path))
    app = MAREApp.from_documents(documents)
    cases = load_eval_cases(eval_path)
    return evaluate_cases(app, cases)


def compare_stacks(
    corpus_path: str | Path,
    eval_path: str | Path,
    stacks: list[str],
) -> dict[str, tuple[EvalSummary, list[EvalCaseResult]]]:
    documents = load_documents(Path(corpus_path))
    cases = load_eval_cases(eval_path)
    reports: dict[str, tuple[EvalSummary, list[EvalCaseResult]]] = {}
    for stack in stacks:
        app = create_app_for_stack(documents, stack)
        reports[stack] = evaluate_cases(app, cases)
    return reports


def _format_output(summary: EvalSummary, results: list[EvalCaseResult]) -> dict:
    return {
        "summary": {
            **asdict(summary),
            "page_hit_rate": summary.page_hit_rate,
            "doc_hit_rate": summary.doc_hit_rate,
            "object_hit_rate": summary.object_hit_rate,
            "no_result_accuracy": summary.no_result_accuracy,
            "high_quality_rate": summary.high_quality_rate,
            "usable_quality_rate": summary.usable_quality_rate,
        },
        "results": [asdict(result) for result in results],
    }


def _summary_metrics(summary: EvalSummary) -> dict[str, int | float]:
    return {
        "total_cases": summary.total_cases,
        "page_hit_rate": summary.page_hit_rate,
        "doc_hit_rate": summary.doc_hit_rate,
        "object_hit_rate": summary.object_hit_rate,
        "no_result_accuracy": summary.no_result_accuracy,
        "high_quality_rate": summary.high_quality_rate,
        "usable_quality_rate": summary.usable_quality_rate,
    }


def _comparison_recommendation(reports: dict[str, tuple[EvalSummary, list[EvalCaseResult]]]) -> dict:
    if not reports:
        return {
            "best_stack": "",
            "reason": "No stacks were evaluated.",
            "ranking": [],
        }

    ranking = []
    for stack, (summary, _) in reports.items():
        score = round(
            (0.3 * summary.page_hit_rate)
            + (0.25 * summary.doc_hit_rate)
            + (0.15 * summary.object_hit_rate)
            + (0.15 * summary.usable_quality_rate)
            + (0.1 * summary.high_quality_rate)
            + (0.05 * summary.no_result_accuracy),
            4,
        )
        ranking.append(
            {
                "stack": stack,
                "score": score,
                **_summary_metrics(summary),
            }
        )

    ranking.sort(
        key=lambda item: (
            item["score"],
            item["page_hit_rate"],
            item["doc_hit_rate"],
            item["object_hit_rate"],
            item["usable_quality_rate"],
            item["high_quality_rate"],
            item["no_result_accuracy"],
        ),
        reverse=True,
    )
    best = ranking[0]
    return {
        "best_stack": best["stack"],
        "reason": (
            f"{best['stack']} had the strongest weighted evidence score "
            f"({best['score']}) across page, document, object, evidence-quality, and no-result checks."
        ),
        "ranking": ranking,
    }


def _format_comparison_output(reports: dict[str, tuple[EvalSummary, list[EvalCaseResult]]]) -> dict:
    return {
        "recommendation": _comparison_recommendation(reports),
        "comparison": {
            stack: {
                "summary": {
                    **asdict(summary),
                    "page_hit_rate": summary.page_hit_rate,
                    "doc_hit_rate": summary.doc_hit_rate,
                    "object_hit_rate": summary.object_hit_rate,
                    "no_result_accuracy": summary.no_result_accuracy,
                    "high_quality_rate": summary.high_quality_rate,
                    "usable_quality_rate": summary.usable_quality_rate,
                },
                "results": [asdict(result) for result in results],
            }
            for stack, (summary, results) in reports.items()
        }
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a MARE evaluation harness over a corpus and benchmark cases")
    parser.add_argument("--corpus", required=True, help="Path to a MARE corpus JSON file")
    parser.add_argument("--eval", required=True, help="Path to an evaluation JSON file")
    parser.add_argument(
        "--stack",
        action="append",
        dest="stacks",
        choices=SUPPORTED_STACKS,
        help="Evaluate a specific retrieval stack. Repeat to compare multiple stacks.",
    )
    args = parser.parse_args()

    if args.stacks:
        try:
            reports = compare_stacks(args.corpus, args.eval, args.stacks)
        except RuntimeError as exc:
            raise SystemExit(str(exc)) from exc
        print(json.dumps(_format_comparison_output(reports), indent=2))
        return

    summary, results = evaluate_corpus(args.corpus, args.eval)
    print(json.dumps(_format_output(summary, results), indent=2))


if __name__ == "__main__":
    main()
