from pathlib import Path

from mare import MAREApp, load_corpora, load_corpus, load_document
from mare.extensions import MAREConfig
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


def test_load_corpora_combines_multiple_json_corpora(tmp_path: Path) -> None:
    corpus_a = tmp_path / "manual-a.json"
    corpus_b = tmp_path / "manual-b.json"
    corpus_a.write_text(
        '{"documents":[{"doc_id":"a-1","title":"Manual A","page":1,"text":"Wake on LAN feature setup.","image_caption":"","layout_hints":"","page_image_path":"generated/a/page-1.png","metadata":{"source":"manual-a.pdf"}}]}'
    )
    corpus_b.write_text(
        '{"documents":[{"doc_id":"b-4","title":"Manual B","page":4,"text":"Use the torque driver to reinstall the board.","image_caption":"","layout_hints":"","page_image_path":"generated/b/page-4.png","metadata":{"source":"manual-b.pdf"}}]}'
    )

    app = load_corpora([corpus_a, corpus_b])

    assert len(app.documents) == 2
    assert len(app.corpus_paths) == 2
    assert app.best_match("torque driver").doc_id == "b-4"
    summary = app.describe_corpus(page_limit=2, object_limit=1)
    assert summary["corpus_count"] == 2
    assert len(summary["corpus_paths"]) == 2


def test_load_document_supports_markdown_input(tmp_path: Path) -> None:
    source = tmp_path / "guide.md"
    source.write_text("# Setup\n1. Connect the adapter.\n2. Restart the laptop.\n")

    app = load_document(source)

    assert app.source_document == source
    assert app.source_documents == [source]
    assert app.describe_corpus()["source_document"] == str(source)
    assert app.best_match("connect the adapter").page == 1
    procedure_objects = app.search_objects("connect the adapter", object_type="procedure", limit=5)
    assert procedure_objects
    assert procedure_objects[0]["metadata"]["heading"] == "Setup"


def test_load_document_uses_resolved_runtime_config_by_default(monkeypatch) -> None:
    resolved_config = MAREConfig()
    captured: dict[str, object] = {}

    monkeypatch.setattr("mare.api.resolve_runtime_config", lambda config=None: resolved_config)

    def _fake_from_document(**kwargs):
        captured.update(kwargs)
        return "app"

    monkeypatch.setattr("mare.api.MAREApp.from_document", _fake_from_document)

    result = load_document("guide.md")

    assert result == "app"
    assert captured["config"] is resolved_config


def test_load_document_preserves_explicit_config(monkeypatch) -> None:
    explicit_config = MAREConfig()
    captured: dict[str, object] = {}

    monkeypatch.setattr("mare.api.resolve_runtime_config", lambda config=None: config)

    def _fake_from_document(**kwargs):
        captured.update(kwargs)
        return "app"

    monkeypatch.setattr("mare.api.MAREApp.from_document", _fake_from_document)

    result = load_document("guide.md", config=explicit_config)

    assert result == "app"
    assert captured["config"] is explicit_config
