from __future__ import annotations

from pathlib import Path

from mare.types import Modality, QueryPlan, RetrievalExplanation, RetrievalHit
from mare.workflow import _build_workflow_payload, _default_output_path, _load_app, _print_pretty


class _FakeApp:
    def __init__(self) -> None:
        self.corpus_path = Path("generated/manual.json")
        self.corpus_paths = [self.corpus_path]
        self.source_pdf = Path("manual.pdf")
        self.source_pdfs = [self.source_pdf]
        self.documents = [object()]

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
                )
            ],
        )


def test_default_output_path_uses_generated_folder() -> None:
    output = _default_output_path(Path("manual.pdf"))
    assert output == Path("generated/manual.json")


def test_load_app_uses_single_pdf_fast_path(monkeypatch) -> None:
    fake_app = _FakeApp()
    monkeypatch.setattr("mare.workflow.load_pdf", lambda **kwargs: fake_app)

    app = _load_app(pdfs=["manual.pdf"], corpora=[], reuse=True, parser="builtin")

    assert app is fake_app


def test_load_app_combines_pdfs_and_corpora(monkeypatch) -> None:
    fake_pdf_app = _FakeApp()
    fake_pdf_app.corpus_path = Path("generated/manual-a.json")
    fake_multi_app = _FakeApp()
    fake_multi_app.corpus_paths = [Path("generated/manual-a.json"), Path("generated/manual-b.json")]
    monkeypatch.setattr("mare.workflow.load_pdf", lambda **kwargs: fake_pdf_app)
    monkeypatch.setattr("mare.workflow.load_corpora", lambda paths: fake_multi_app)

    app = _load_app(
        pdfs=["manual-a.pdf"],
        corpora=["generated/manual-b.json"],
        reuse=True,
        parser="builtin",
    )

    assert app is fake_multi_app


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
    assert "Grounded Retrieval" in output
    assert "Highlight:" in output
