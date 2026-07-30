from __future__ import annotations

from pathlib import Path

import json

from mare.chat import _build_app_from_args, _discover_folder_inputs, build_session_store, run_chat
from mare.extensions import MAREConfig
from mare.types import Modality, QueryPlan, RetrievalExplanation, RetrievalHit


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
        return {"page_count": 1, "object_counts": {"procedure": 1}}

    def search_objects(self, query: str, object_type: str | None = None, limit: int = 5):
        if query == "no matches":
            return []
        return [
            {
                "page": 10,
                "title": "Manual",
                "object_type": object_type or "procedure",
                "content": "1 Connect the AC adapter to the laptop.",
                "metadata": {"step": "1", "heading": "Connecting the AC adapter"},
            },
            {
                "page": 10,
                "title": "Manual",
                "object_type": object_type or "procedure",
                "content": "2 Plug the adapter into a power outlet.",
                "metadata": {"step": "2", "heading": "Connecting the AC adapter"},
            },
        ][:limit]

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
                    title="Manual",
                    page=11,
                    modality=Modality.TEXT,
                    score=0.72,
                    reason="Matched setup instruction wording.",
                    snippet="Plug the adapter into the wall outlet before use.",
                    page_image_path="generated/manual/page-11.png",
                    highlight_image_path="generated/manual/highlight-11.png",
                    object_id="doc-2:procedure:1",
                    object_type="procedure",
                    metadata={"source": "manual.pdf"},
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


def test_discover_folder_inputs(tmp_path: Path) -> None:
    (tmp_path / "manual.pdf").write_text("pdf")
    (tmp_path / "guide.md").write_text("# guide")
    (tmp_path / "notes.docx").write_text("placeholder")
    (tmp_path / "manual.json").write_text("{}")

    pdfs, corpora = _discover_folder_inputs(tmp_path)

    assert pdfs == [str(tmp_path / "guide.md"), str(tmp_path / "manual.pdf"), str(tmp_path / "notes.docx")]
    assert corpora == []


def test_discover_folder_inputs_supports_include_patterns(tmp_path: Path) -> None:
    (tmp_path / "guide.md").write_text("# guide")
    (tmp_path / "manual.pdf").write_text("pdf")
    (tmp_path / "notes.docx").write_text("placeholder")

    pdfs, corpora = _discover_folder_inputs(tmp_path, include=["*.md", "*.docx"])

    assert pdfs == [str(tmp_path / "guide.md"), str(tmp_path / "notes.docx")]
    assert corpora == []


def test_discover_folder_inputs_supports_exclude_patterns(tmp_path: Path) -> None:
    (tmp_path / "guide.md").write_text("# guide")
    (tmp_path / "manual.pdf").write_text("pdf")
    nested = tmp_path / "archive"
    nested.mkdir()
    (nested / "old-notes.txt").write_text("ignore me")

    pdfs, corpora = _discover_folder_inputs(tmp_path, exclude=["archive/*", "*.pdf"])

    assert pdfs == [str(tmp_path / "guide.md")]
    assert corpora == []


def test_discover_folder_inputs_recurses_and_filters_for_real_corpora(tmp_path: Path) -> None:
    nested = tmp_path / "docs" / "nested"
    nested.mkdir(parents=True)
    (nested / "manual.PDF").write_text("pdf")
    (nested / "notes.json").write_text('{"foo": "bar"}')
    (nested / "manual.json").write_text(
        '{"source_pdf": "manual.pdf", "documents": [{"doc_id": "doc-1", "page": 1, "text": "hello"}]}'
    )

    pdfs, corpora = _discover_folder_inputs(tmp_path)

    assert pdfs == [str(nested / "manual.PDF")]
    assert corpora == [str(nested / "manual.json")]


def test_build_app_from_folder_uses_discovered_inputs(monkeypatch, tmp_path: Path) -> None:
    (tmp_path / "manual.pdf").write_text("pdf")
    fake_app = _FakeApp()
    monkeypatch.setattr("mare.chat._load_app", lambda **kwargs: fake_app)

    app = _build_app_from_args(
        folder=str(tmp_path),
        documents=[],
        corpora=[],
        include=[],
        exclude=[],
        reuse=True,
        parser="builtin",
    )

    assert app is fake_app


def test_build_app_from_args_passes_retriever_config(monkeypatch) -> None:
    fake_app = _FakeApp()
    seen = {}

    def _fake_load_app(**kwargs):
        seen.update(kwargs)
        return fake_app

    monkeypatch.setattr("mare.chat._load_app", _fake_load_app)
    config = MAREConfig(retriever_label="FastEmbed semantic")

    app = _build_app_from_args(
        folder=None,
        documents=["manual.md"],
        corpora=[],
        include=[],
        exclude=[],
        reuse=True,
        parser="builtin",
        config=config,
    )

    assert app is fake_app
    assert seen["config"] is config


def test_run_chat_answers_question_and_exits(monkeypatch, capsys) -> None:
    answers = iter(["how do I connect the AC adapter", ":quit"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))

    run_chat(_FakeApp(), top_k=3, page_limit=3, object_limit=5)
    output = capsys.readouterr().out

    assert "MARE Chat" in output
    assert "Loaded documents: manual.md" in output
    assert "Intent: semantic_lookup" in output
    assert "Retriever: Hybrid semantic + lexical" in output
    assert "Confidence: 0.800" in output
    assert "Support: Strong support" in output
    assert "Agent action: compare_sources" in output
    assert "Best page: 10" in output
    assert "Citation: manual.pdf | page 10" in output
    assert "Score: 0.950" in output
    assert "Highlight:" in output
    assert "Other evidence" in output


def test_run_chat_prints_retriever_setup_errors_and_continues(monkeypatch, capsys) -> None:
    answers = iter(["show me the diagram", ":quit"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))

    run_chat(_BrokenRetrieverApp(), top_k=3, page_limit=3, object_limit=5)
    output = capsys.readouterr().out

    assert "ColPali visual retrieval needs rendered PDF page images in the corpus." in output
    assert "Traceback" not in output


def test_run_chat_supports_json_and_sources(monkeypatch, capsys) -> None:
    answers = iter([":sources", ":json how do I connect the AC adapter", ":quit"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))

    run_chat(_FakeApp(), top_k=3, page_limit=3, object_limit=5)
    output = capsys.readouterr().out

    assert "Sources" in output
    assert "Documents: manual.md" in output
    assert "\"workflow\": \"agent-evidence\"" in output


def test_run_chat_supports_steps_command(monkeypatch, capsys) -> None:
    answers = iter([":steps connect the adapter", ":quit"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))

    run_chat(_FakeApp(), top_k=3, page_limit=3, object_limit=5)
    output = capsys.readouterr().out

    assert "Step query: connect the adapter" in output
    assert "Steps" in output
    assert "1. 1 Connect the AC adapter to the laptop." in output
    assert "Citation: page 10 | Manual | Connecting the AC adapter | step 1" in output


def test_run_chat_steps_command_handles_no_matches(monkeypatch, capsys) -> None:
    answers = iter([":steps no matches", ":quit"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))

    run_chat(_FakeApp(), top_k=3, page_limit=3, object_limit=5)
    output = capsys.readouterr().out

    assert "Steps: No matching procedure evidence found." in output


def test_run_chat_supports_compare_command(monkeypatch, capsys) -> None:
    answers = iter([":compare connect the adapter", ":quit"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))

    run_chat(_FakeApp(), top_k=3, page_limit=3, object_limit=5)
    output = capsys.readouterr().out

    assert "Compare query: connect the adapter" in output
    assert "Comparison" in output
    assert "1. manual.pdf | page 10 | procedure | score=0.950" in output
    assert "2. manual.pdf | page 11 | procedure | score=0.720" in output
    assert "Reason: Matched setup instruction wording." in output


def test_run_chat_supports_contract_command(monkeypatch, capsys) -> None:
    answers = iter([":contract connect the adapter", ":quit"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))

    run_chat(_FakeApp(), top_k=3, page_limit=3, object_limit=5)
    output = capsys.readouterr().out

    assert "Agent contract query: connect the adapter" in output
    assert "Schema: mare.agent_contract.v1" in output
    assert "May answer: no" in output
    assert "Recommended action: compare_sources" in output
    assert "Research status: needs_source_check" in output
    assert "Research step 1: compare_sources | compare supporting evidence for connect the adapter besides manual.pdf" in output


def test_run_chat_compare_command_handles_no_matches(monkeypatch, capsys) -> None:
    class _NoMatchApp(_FakeApp):
        def explain(self, query: str, top_k: int = 3):
            return RetrievalExplanation(
                plan=QueryPlan(
                    query=query,
                    selected_modalities=[Modality.TEXT],
                    discarded_modalities=[Modality.IMAGE, Modality.LAYOUT],
                    confidence=0.2,
                    intent="semantic_lookup",
                    rationale="test",
                ),
                per_modality_results={},
                fused_results=[],
            )

    answers = iter([":compare no matches", ":quit"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))

    run_chat(_NoMatchApp(), top_k=3, page_limit=3, object_limit=5)
    output = capsys.readouterr().out

    assert "Compare: No matching evidence found." in output


def test_run_chat_supports_summary_command(monkeypatch, capsys) -> None:
    answers = iter([":summary connect the adapter", ":quit"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))

    run_chat(_FakeApp(), top_k=3, page_limit=3, object_limit=5)
    output = capsys.readouterr().out

    assert "Summary query: connect the adapter" in output
    assert "Grounded summary" in output
    assert "Overview: Found 2 grounded results across 1 source." in output
    assert "1. Connect the AC adapter to the laptop." in output
    assert "Citation: manual.pdf | page 10" in output
    assert "Reason: Matched text terms: adapter" in output


def test_run_chat_summary_command_handles_no_matches(monkeypatch, capsys) -> None:
    class _NoMatchApp(_FakeApp):
        def explain(self, query: str, top_k: int = 3):
            return RetrievalExplanation(
                plan=QueryPlan(
                    query=query,
                    selected_modalities=[Modality.TEXT],
                    discarded_modalities=[Modality.IMAGE, Modality.LAYOUT],
                    confidence=0.2,
                    intent="semantic_lookup",
                    rationale="test",
                ),
                per_modality_results={},
                fused_results=[],
            )

    answers = iter([":summary no matches", ":quit"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))

    run_chat(_NoMatchApp(), top_k=3, page_limit=3, object_limit=5)
    output = capsys.readouterr().out

    assert "Summary: No matching evidence found." in output


def test_run_chat_supports_actions_command(monkeypatch, capsys) -> None:
    answers = iter([":actions connect the adapter", ":quit"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))

    run_chat(_FakeApp(), top_k=3, page_limit=3, object_limit=5)
    output = capsys.readouterr().out

    assert "Actions query: connect the adapter" in output
    assert "Found 2 grounded actions." in output
    assert "Citation: manual.pdf | page 10" in output


def test_run_chat_supports_deadlines_command(monkeypatch, capsys) -> None:
    class _DeadlineApp(_FakeApp):
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
                        doc_id="doc-3",
                        title="Policy",
                        page=4,
                        modality=Modality.TEXT,
                        score=0.84,
                        reason="Matched due-date language in the policy.",
                        snippet="Submit the signed acknowledgement by March 15, 2026.",
                        page_image_path="generated/policy/page-4.png",
                        highlight_image_path="generated/policy/highlight-4.png",
                        object_id="doc-3:section:1",
                        object_type="section",
                        metadata={"source": "policy.docx"},
                    ),
                ],
            )

    answers = iter([":deadlines onboarding acknowledgement", ":quit"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))

    run_chat(_DeadlineApp(), top_k=3, page_limit=3, object_limit=5)
    output = capsys.readouterr().out

    assert "Deadlines query: onboarding acknowledgement" in output
    assert "Found 1 grounded deadlines." in output
    assert "Signal: by March" in output


def test_run_chat_supports_review_command(monkeypatch, capsys) -> None:
    answers = iter([":review connect the adapter", ":quit"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))

    run_chat(_FakeApp(), top_k=3, page_limit=3, object_limit=5)
    output = capsys.readouterr().out

    assert "Review query: connect the adapter" in output
    assert "Grounded review assembled from the best supporting evidence." in output
    assert "Primary citation: manual.pdf | page 10" in output
    assert "Findings: actions=2, requirements=0, risks=0, deadlines=1" in output


def test_run_chat_supports_brief_command(monkeypatch, capsys) -> None:
    answers = iter([":brief connect the adapter", ":quit"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))

    run_chat(_FakeApp(), top_k=3, page_limit=3, object_limit=5)
    output = capsys.readouterr().out

    assert "Evidence brief query: connect the adapter" in output
    assert "Strong support from 2 retrieved results across 1 source." in output
    assert "Sources: manual.pdf" in output
    assert "Source coverage: Single-source coverage" in output
    assert "Proof assets: snippet, citation, page_image, highlight" in output
    assert "Next question 1:" in output


def test_run_chat_shows_and_saves_evidence_rescue(monkeypatch, capsys, tmp_path: Path) -> None:
    answers = iter(["what onboarding items are required", ":history", ":quit"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))
    session_file = tmp_path / "chat-session.json"
    session_store = build_session_store(
        _WeakThenRescuedApp(),
        session_file=str(session_file),
        session_name="onboarding-session",
    )

    run_chat(_WeakThenRescuedApp(), top_k=3, page_limit=3, object_limit=5, session_store=session_store)
    output = capsys.readouterr().out
    payload = json.loads(session_file.read_text())

    assert "Support: Strong support" in output
    assert "Agent action: answer_with_citations" in output
    assert 'Evidence rescue: improved via "exact evidence for what onboarding items are required" (Strong support)' in output
    assert "The onboarding checklist requires completing payroll forms before system access." in output
    assert payload["entries"][0]["top_result"]["support"] == "Strong support"
    assert payload["entries"][0]["top_result"]["evidence_quality"] == "High evidence quality"
    assert payload["entries"][0]["top_result"]["evidence_quality_status"] == "high"
    assert payload["entries"][0]["top_result"]["agent_action"] == "answer_with_citations"
    assert payload["entries"][0]["top_result"]["evidence_rescue"] == "improved"
    assert "Evidence quality: High evidence quality" in output
    assert "Evidence rescue: improved" in output


def test_run_chat_saves_and_shows_session_history(monkeypatch, capsys, tmp_path: Path) -> None:
    answers = iter(["how do I connect the AC adapter", ":history", ":quit"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))
    session_file = tmp_path / "chat-session.json"
    session_store = build_session_store(_FakeApp(), session_file=str(session_file), session_name="manual-session")

    run_chat(_FakeApp(), top_k=3, page_limit=3, object_limit=5, session_store=session_store)
    output = capsys.readouterr().out

    payload = json.loads(session_file.read_text())
    assert payload["session_name"] == "manual-session"
    assert len(payload["entries"]) == 1
    assert payload["entries"][0]["type"] == "ask"
    assert payload["entries"][0]["query"] == "how do I connect the AC adapter"
    assert payload["entries"][0]["top_result"]["citation"] == "manual.pdf | page 10"
    assert payload["entries"][0]["top_result"]["evidence_quality"] == "High evidence quality"
    assert payload["entries"][0]["top_result"]["agent_action"] == "compare_sources"
    assert "Session history: manual-session" in output
    assert "Recent entries" in output
    assert "[ask] how do I connect the AC adapter" in output
    assert "Evidence quality: High evidence quality" in output
    assert "Agent action: compare_sources" in output


def test_run_chat_can_clear_session_history(monkeypatch, capsys, tmp_path: Path) -> None:
    answers = iter(["how do I connect the AC adapter", ":clear-history", ":history", ":quit"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))
    session_file = tmp_path / "chat-session.json"
    session_store = build_session_store(_FakeApp(), session_file=str(session_file), session_name="manual-session")

    run_chat(_FakeApp(), top_k=3, page_limit=3, object_limit=5, session_store=session_store)
    output = capsys.readouterr().out

    payload = json.loads(session_file.read_text())
    assert payload["entries"] == []
    assert "Session history cleared." in output
    assert "Entries: none" in output
