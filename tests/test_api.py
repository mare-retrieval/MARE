from pathlib import Path

from mare import MAREApp, load_corpus
from mare.types import Document


def test_mare_app_from_documents_returns_best_match() -> None:
    app = MAREApp.from_documents(
        [
            Document(
                doc_id="1",
                title="Manual",
                page=1,
                text="Use the torque driver to partially reinstall the set screws.",
                page_image_path="generated/manual/page-1.png",
            )
        ]
    )

    hit = app.best_match("partially reinstall the set screws")

    assert hit is not None
    assert hit.page == 1
    assert "set screws" in hit.snippet.lower()


def test_load_corpus_wraps_existing_json(tmp_path: Path) -> None:
    corpus = tmp_path / "manual.json"
    corpus.write_text(
        '{"documents":[{"doc_id":"1","title":"Manual","page":2,"text":"Important: Partially reinstall the set screws if they fall out.","image_caption":"","layout_hints":"","page_image_path":"generated/manual/page-2.png","metadata":{}}]}'
    )

    app = load_corpus(corpus)

    assert app.corpus_path == corpus
    assert app.best_match("set screws").page == 2
