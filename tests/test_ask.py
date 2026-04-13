from pathlib import Path

from mare.ask import _default_output_path, _print_answer_block, ask_pdf
from mare.types import Modality, QueryPlan, RetrievalExplanation, RetrievalHit


def test_default_output_path_uses_generated_folder() -> None:
    output = _default_output_path(Path("manual.pdf"))
    assert output == Path("generated/manual.json")


def test_print_answer_block_shows_best_hit(capsys) -> None:
    explanation = RetrievalExplanation(
        plan=QueryPlan(
            query="what is MagSafe 3",
            selected_modalities=[Modality.TEXT],
            discarded_modalities=[Modality.IMAGE, Modality.LAYOUT],
            confidence=0.7,
            intent="semantic_lookup",
            rationale="test",
        ),
        per_modality_results={},
        fused_results=[
            RetrievalHit(
                doc_id="doc-1",
                title="Title",
                page=2,
                modality=Modality.TEXT,
                score=0.9,
                reason="Matched text terms: magsafe",
                snippet="Important: Partially reinstall the set screws if they fall out.",
                page_image_path="generated/doc/page-2.png",
            )
        ],
    )

    _print_answer_block("what is MagSafe 3", Path("generated/manual.json"), explanation)
    output = capsys.readouterr().out

    assert "Best Match" in output
    assert "Page: 2" in output
    assert "generated/doc/page-2.png" in output


def test_ask_pdf_reuses_existing_corpus(tmp_path: Path, monkeypatch) -> None:
    pdf_path = tmp_path / "manual.pdf"
    pdf_path.write_text("placeholder")
    corpus_path = tmp_path / "generated" / "manual.json"
    corpus_path.parent.mkdir(parents=True, exist_ok=True)
    corpus_path.write_text(
        '{"documents":[{"doc_id":"1","title":"Manual","page":1,"text":"set screws instructions","image_caption":"","layout_hints":"","page_image_path":"generated/manual/page-1.png","metadata":{}}]}'
    )

    monkeypatch.setattr("mare.ask._default_output_path", lambda _path: corpus_path)

    explanation = RetrievalExplanation(
        plan=QueryPlan(
            query="set screws",
            selected_modalities=[Modality.TEXT],
            discarded_modalities=[Modality.IMAGE, Modality.LAYOUT],
            confidence=0.7,
            intent="semantic_lookup",
            rationale="test",
        ),
        per_modality_results={},
        fused_results=[
            RetrievalHit(
                doc_id="1",
                title="Manual",
                page=1,
                modality=Modality.TEXT,
                score=0.8,
                reason="Matched text terms: set, screws",
                snippet="set screws instructions",
                page_image_path="generated/manual/page-1.png",
            )
        ],
    )

    class _FakeApp:
        def __init__(self) -> None:
            self.corpus_path = corpus_path

        def explain(self, query: str, top_k: int = 3):
            return explanation

    monkeypatch.setattr("mare.ask.load_pdf", lambda *args, **kwargs: _FakeApp())

    output_path, explanation = ask_pdf(pdf_path=pdf_path, query="set screws", reuse=True)

    assert output_path == corpus_path
    assert explanation.fused_results[0].page == 1
