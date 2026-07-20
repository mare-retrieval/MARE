from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from mare.types import Modality, QueryPlan, RetrievalExplanation, RetrievalHit
from mare.extensions import MAREConfig
from mare.workflow import (
    _build_workflow_payload,
    _default_output_path,
    _discover_folder_inputs,
    _load_app,
    _print_agent_contract,
    _print_evidence_brief,
    _print_findings,
    _print_review,
    _print_pretty,
    build_history_store,
    main,
)


class _FakeApp:
    def __init__(self) -> None:
        self.corpus_path = Path("generated/manual.json")
        self.corpus_paths = [self.corpus_path]
        self.source_document = Path("manual.md")
        self.source_documents = [self.source_document]
        self.source_pdf = Path("manual.pdf")
        self.source_pdfs = [self.source_pdf]
        self.documents = [object()]
        self.config = MAREConfig(
            retriever_label="Hybrid semantic + lexical",
            retriever_resolution_note="Defaulted to Hybrid semantic + lexical retrieval because sentence-transformers is available.",
        )

    def describe_corpus(self, page_limit: int = 3, object_limit: int = 5):
        return {
            "page_count": 1,
            "object_counts": {"procedure": 1},
        }

    def search_objects(self, query: str, object_type: str | None = None, limit: int = 5):
        return [
            {
                "page": 10,
                "object_type": object_type or "procedure",
                "content": "Connect the AC adapter to the laptop.",
            }
        ]

    def explain(self, query: str, top_k: int = 3):
        return RetrievalExplanation(
            plan=QueryPlan(
                query=query,
                selected_modalities=[Modality.TEXT],
                discarded_modalities=[Modality.IMAGE, Modality.LAYOUT],
                confidence=0.8,
                intent="semantic_lookup",
                rationale="test",
            ),
            per_modality_results={},
            fused_results=[
                RetrievalHit(
                    doc_id="doc-1",
                    title="Manual",
                    page=10,
                    modality=Modality.TEXT,
                    score=0.95,
                    reason="Matched text terms: adapter",
                    snippet="Connect the AC adapter to the laptop.",
                    page_image_path="generated/manual/page-10.png",
                    highlight_image_path="generated/manual/highlight-10.png",
                    object_id="doc-1:procedure:1",
                    object_type="procedure",
                    metadata={"source": "manual.pdf"},
                ),
                RetrievalHit(
                    doc_id="doc-2",
                    title="Guide",
                    page=12,
                    modality=Modality.TEXT,
                    score=0.72,
                    reason="Matched related setup wording in the onboarding guide.",
                    snippet="Plug the AC adapter into the wall outlet before powering on.",
                    page_image_path="generated/guide/page-12.png",
                    highlight_image_path="generated/guide/highlight-12.png",
                    object_id="doc-2:procedure:1",
                    object_type="procedure",
                    metadata={"source": "guide.docx"},
                ),
            ],
        )


class _WeakThenRescuedApp(_FakeApp):
    def explain(self, query: str, top_k: int = 3):
        if query.startswith("exact evidence for"):
            score = 0.91
            snippet = "The onboarding checklist requires completing payroll forms before system access."
            reason = "Matched exact evidence for onboarding checklist requirements."
        else:
            score = 0.32
            snippet = "Onboarding information appears in this packet."
            reason = "Matched broad onboarding wording."

        return RetrievalExplanation(
            plan=QueryPlan(
                query=query,
                selected_modalities=[Modality.TEXT],
                discarded_modalities=[Modality.IMAGE, Modality.LAYOUT],
                confidence=0.8,
                intent="semantic_lookup",
                rationale="test",
            ),
            per_modality_results={},
            fused_results=[
                RetrievalHit(
                    doc_id="doc-1",
                    title="Onboarding",
                    page=3,
                    modality=Modality.TEXT,
                    score=score,
                    reason=reason,
                    snippet=snippet,
                    object_id="doc-1:section:1",
                    object_type="section",
                    metadata={"source": "employee-onboarding.docx"},
                ),
            ],
        )


class _BrokenRetrieverApp(_FakeApp):
    def explain(self, query: str, top_k: int = 3):
        raise RuntimeError("ColPali visual retrieval needs rendered PDF page images in the corpus.")


def test_default_output_path_uses_generated_folder() -> None:
    output = _default_output_path(Path("manual.pdf"))
    assert output == Path("generated/manual.json")


def test_discover_folder_inputs_supports_include_and_exclude(tmp_path: Path) -> None:
    (tmp_path / "guide.md").write_text("# guide")
    (tmp_path / "manual.pdf").write_text("pdf")
    nested = tmp_path / "archive"
    nested.mkdir()
    (nested / "notes.txt").write_text("ignore me")

    documents, corpora = _discover_folder_inputs(tmp_path, include=["*.md", "*.txt"], exclude=["archive/*"])

    assert documents == [str(tmp_path / "guide.md")]
    assert corpora == []


def test_load_app_uses_single_document_fast_path(monkeypatch) -> None:
    fake_app = _FakeApp()
    monkeypatch.setattr("mare.workflow.load_document", lambda **kwargs: fake_app)

    app = _load_app(documents=["manual.md"], corpora=[], reuse=True, parser="builtin")

    assert app is fake_app


def test_load_app_supports_folder_with_include_and_exclude(monkeypatch, tmp_path: Path) -> None:
    (tmp_path / "guide.md").write_text("# guide")
    (tmp_path / "manual.pdf").write_text("pdf")
    fake_app = _FakeApp()
    monkeypatch.setattr("mare.workflow.load_document", lambda **kwargs: fake_app)

    app = _load_app(
        documents=[],
        corpora=[],
        folder=str(tmp_path),
        include=["*.md"],
        exclude=["*.pdf"],
        reuse=True,
        parser="builtin",
    )

    assert app is fake_app


def test_load_app_combines_pdfs_and_corpora(monkeypatch) -> None:
    fake_pdf_app = _FakeApp()
    fake_pdf_app.corpus_path = Path("generated/manual-a.json")
    fake_multi_app = _FakeApp()
    fake_multi_app.corpus_paths = [Path("generated/manual-a.json"), Path("generated/manual-b.json")]
    monkeypatch.setattr("mare.workflow.load_document", lambda **kwargs: fake_pdf_app)
    monkeypatch.setattr("mare.workflow.load_corpora", lambda paths, config=None: fake_multi_app)

    app = _load_app(
        documents=["manual-a.md"],
        corpora=["generated/manual-b.json"],
        reuse=True,
        parser="builtin",
    )

    assert app is fake_multi_app


def test_load_app_passes_retriever_config_to_corpus_loader(monkeypatch) -> None:
    fake_app = _FakeApp()
    seen = {}

    def _fake_load_corpus(path, config=None):
        seen["config"] = config
        return fake_app

    monkeypatch.setattr("mare.workflow.load_corpus", _fake_load_corpus)
    config = MAREConfig(retriever_label="FastEmbed semantic")

    app = _load_app(documents=[], corpora=["generated/manual.json"], reuse=True, parser="builtin", config=config)

    assert app is fake_app
    assert seen["config"] is config


def test_workflow_main_exits_cleanly_on_retriever_setup_error(monkeypatch) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        ["mare-workflow", "--document", "manual.md", "--query", "show me the diagram"],
    )
    monkeypatch.setattr("mare.workflow._load_app", lambda **kwargs: _BrokenRetrieverApp())

    with pytest.raises(SystemExit, match="needs rendered PDF page images"):
        main()


def test_build_workflow_payload_returns_agent_shape() -> None:
    payload = _build_workflow_payload(
        _FakeApp(),
        query="connect the adapter",
        object_query="adapter",
        object_type="procedure",
        top_k=3,
        page_limit=3,
        object_limit=5,
    )

    assert payload["workflow"] == "agent-evidence"
    assert payload["steps"]["query_corpus"]["results"][0]["page"] == 10
    assert payload["steps"]["search_objects"]["results"][0]["object_type"] == "procedure"
    assert payload["steps"]["query_corpus"]["comparison"][0]["citation"] == "manual.pdf | page 10"
    assert payload["steps"]["query_corpus"]["comparison"][1]["citation"] == "guide.docx | page 12"
    assert payload["steps"]["query_corpus"]["summary"]["overview"] == "Found 2 grounded results across 2 sources."
    assert payload["steps"]["query_corpus"]["findings"]["actions"]["item_count"] == 2
    assert payload["steps"]["query_corpus"]["review"]["best_evidence"]["citation"] == "manual.pdf | page 10"
    assert payload["steps"]["query_corpus"]["retriever"]["label"] == "Hybrid semantic + lexical"
    assert payload["steps"]["query_corpus"]["support"]["status"] == "strong"
    assert payload["steps"]["query_corpus"]["evidence_brief"]["source_count"] == 2
    assert payload["steps"]["query_corpus"]["evidence_brief"]["research_plan"]["status"] == "ready"
    assert payload["steps"]["query_corpus"]["agent_contract"]["may_answer"] is True
    assert payload["steps"]["query_corpus"]["agent_contract"]["recommended_action"] == "answer_with_citations"
    assert payload["steps"]["query_corpus"]["review"]["evidence_brief"]["support"]["status"] == "strong"
    assert payload["steps"]["query_corpus"]["evidence_rescue"]["attempted"] is False
    assert payload["steps"]["query_corpus"]["evidence_rescue"]["attempts"] == []


def test_build_workflow_payload_rescues_weak_evidence() -> None:
    payload = _build_workflow_payload(
        _WeakThenRescuedApp(),
        query="what onboarding items are required",
        object_query="onboarding required",
        object_type="section",
        top_k=3,
        page_limit=3,
        object_limit=5,
    )
    query_step = payload["steps"]["query_corpus"]

    assert query_step["support"]["status"] == "strong"
    assert query_step["retrieval_query"] == "exact evidence for what onboarding items are required"
    assert query_step["results"][0]["snippet"] == "The onboarding checklist requires completing payroll forms before system access."
    assert query_step["evidence_rescue"]["attempted"] is True
    assert query_step["evidence_rescue"]["improved"] is True
    assert query_step["evidence_rescue"]["best_query"] == "exact evidence for what onboarding items are required"
    assert query_step["evidence_rescue"]["attempts"][0]["query"] == "exact evidence for what onboarding items are required"
    assert query_step["evidence_rescue"]["attempts"][0]["improved"] is True
    assert query_step["evidence_rescue"]["attempts"][0]["top_citation"] == "employee-onboarding.docx | page 3"
    assert query_step["agent_contract"]["may_answer"] is True
    assert query_step["agent_contract"]["recommended_action"] == "answer_with_citations"


def test_print_pretty_shows_human_friendly_summary(capsys) -> None:
    payload = _build_workflow_payload(
        _FakeApp(),
        query="connect the adapter",
        object_query="adapter",
        object_type="procedure",
        top_k=3,
        page_limit=3,
        object_limit=5,
    )

    _print_pretty(payload)
    output = capsys.readouterr().out

    assert "MARE Agent Workflow" in output
    assert "Documents: manual.md" in output
    assert "Grounded Retrieval" in output
    assert "Retriever: Hybrid semantic + lexical" in output
    assert "Support: Strong support" in output
    assert "Evidence brief: Strong support from 2 retrieved results across 2 sources." in output
    assert "Agent action: answer_with_citations" in output
    assert "Research plan: ready" in output
    assert "Next question:" in output
    assert "Summary: Found 2 grounded results across 2 sources." in output
    assert "Citation: manual.pdf | page 10" in output
    assert "Highlight:" in output
    assert "Comparison View" in output
    assert "2. guide.docx | page 12 | procedure | score=0.720" in output


def test_print_findings_shows_actions_view(capsys) -> None:
    payload = _build_workflow_payload(
        _FakeApp(),
        query="connect the adapter",
        object_query="adapter",
        object_type="procedure",
        top_k=3,
        page_limit=3,
        object_limit=5,
    )

    _print_findings(payload, "actions")
    output = capsys.readouterr().out

    assert "Actions query: connect the adapter" in output
    assert "Found 2 grounded actions." in output
    assert "Citation: manual.pdf | page 10" in output


def test_print_review_shows_review_view(capsys) -> None:
    payload = _build_workflow_payload(
        _FakeApp(),
        query="connect the adapter",
        object_query="adapter",
        object_type="procedure",
        top_k=3,
        page_limit=3,
        object_limit=5,
    )

    _print_review(payload)
    output = capsys.readouterr().out

    assert "Review query: connect the adapter" in output
    assert "Grounded review assembled from the best supporting evidence." in output
    assert "Primary citation: manual.pdf | page 10" in output
    assert "Evidence brief: Strong support from 2 retrieved results across 2 sources." in output
    assert "Next question 1:" in output
    assert "Findings: actions=2, requirements=0, risks=0, deadlines=1" in output


def test_print_evidence_brief_shows_trust_view(capsys) -> None:
    payload = _build_workflow_payload(
        _FakeApp(),
        query="connect the adapter",
        object_query="adapter",
        object_type="procedure",
        top_k=3,
        page_limit=3,
        object_limit=5,
    )

    _print_evidence_brief(payload)
    output = capsys.readouterr().out

    assert "Evidence brief query: connect the adapter" in output
    assert "Strong support from 2 retrieved results across 2 sources." in output
    assert "Sources: manual.pdf, guide.docx" in output
    assert "Source coverage: Broad source coverage" in output
    assert "Proof assets: snippet, citation, page_image, highlight" in output
    assert "Agent action: answer_with_citations" in output
    assert "Research plan: ready" in output
    assert "Research step 1: answer_with_citations | connect the adapter" in output
    assert "Next question 1:" in output


def test_print_agent_contract_shows_compact_action_view(capsys) -> None:
    payload = _build_workflow_payload(
        _FakeApp(),
        query="connect the adapter",
        object_query="adapter",
        object_type="procedure",
        top_k=3,
        page_limit=3,
        object_limit=5,
    )

    _print_agent_contract(payload)
    output = capsys.readouterr().out

    assert "Agent contract query: connect the adapter" in output
    assert "Schema: mare.agent_contract.v1" in output
    assert "May answer: yes" in output
    assert "Recommended action: answer_with_citations" in output
    assert "Research status: ready" in output
    assert "Stop reasons: [none]" in output
    assert "Research step 1: answer_with_citations | connect the adapter" in output


def test_workflow_history_store_persists_runs(tmp_path: Path) -> None:
    payload = _build_workflow_payload(
        _FakeApp(),
        query="connect the adapter",
        object_query="adapter",
        object_type="procedure",
        top_k=3,
        page_limit=3,
        object_limit=5,
    )
    history_path = tmp_path / "workflow-history.json"
    history_store = build_history_store(_FakeApp(), history_file=str(history_path), history_name="ops-review")

    history_store.append(payload=payload, output_format="pretty", object_query="adapter", object_type="procedure")

    saved = json.loads(history_path.read_text())
    assert saved["history_name"] == "ops-review"
    assert len(saved["runs"]) == 1
    assert saved["runs"][0]["query"] == "connect the adapter"
    assert saved["runs"][0]["agent_action"] == "answer_with_citations"
    assert saved["runs"][0]["top_result"]["citation"] == "manual.pdf | page 10"
    assert saved["runs"][0]["top_result"]["object_type"] == "procedure"


def test_workflow_history_store_uses_default_slug() -> None:
    history_store = build_history_store(_FakeApp())

    assert history_store.path == Path("generated/workflow_runs/manual-workflow.json")
