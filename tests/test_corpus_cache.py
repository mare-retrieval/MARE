from __future__ import annotations

import json
import os
from pathlib import Path

from mare.api import MAREApp, fingerprint_path


class _CountingParser:
    name = "counting"

    def __init__(self) -> None:
        self.calls = 0

    def ingest(self, source_path: Path, output_path: Path) -> Path:
        self.calls += 1
        text = source_path.read_text()
        output_path.write_text(
            json.dumps(
                {
                    "documents": [
                        {
                            "doc_id": "doc-p1",
                            "title": source_path.stem,
                            "page": 1,
                            "text": text,
                            "image_caption": "",
                            "layout_hints": "",
                            "page_image_path": "",
                            "metadata": {"source": str(source_path)},
                        }
                    ]
                }
            )
        )
        return output_path


def _load(source: Path, corpus: Path, parser: _CountingParser, reuse) -> MAREApp:
    return MAREApp.from_document(source, output_path=corpus, reuse=reuse, parser=parser)


def test_auto_reuse_skips_ingest_while_source_is_unchanged(tmp_path: Path) -> None:
    source = tmp_path / "guide.md"
    source.write_text("Connect the adapter.")
    corpus = tmp_path / "generated" / "guide.json"
    parser = _CountingParser()

    _load(source, corpus, parser, "auto")
    _load(source, corpus, parser, "auto")

    assert parser.calls == 1
    assert fingerprint_path(corpus).exists()


def test_auto_reuse_reingests_when_source_changes(tmp_path: Path) -> None:
    source = tmp_path / "guide.md"
    source.write_text("Connect the adapter.")
    corpus = tmp_path / "generated" / "guide.json"
    parser = _CountingParser()

    _load(source, corpus, parser, True)
    source.write_text("Hold the reset pin for ten seconds.")
    app = _load(source, corpus, parser, True)

    assert parser.calls == 2
    assert "reset pin" in app.documents[0].text


def test_touched_but_identical_source_is_reused(tmp_path: Path) -> None:
    source = tmp_path / "guide.md"
    source.write_text("Connect the adapter.")
    corpus = tmp_path / "generated" / "guide.json"
    parser = _CountingParser()

    _load(source, corpus, parser, "auto")
    stat = source.stat()
    os.utime(source, ns=(stat.st_atime_ns, stat.st_mtime_ns + 5_000_000_000))
    _load(source, corpus, parser, "auto")

    assert parser.calls == 1


def test_legacy_corpus_without_fingerprint_is_rebuilt(tmp_path: Path) -> None:
    source = tmp_path / "guide.md"
    source.write_text("Connect the adapter.")
    corpus = tmp_path / "generated" / "guide.json"
    corpus.parent.mkdir()
    corpus.write_text(json.dumps({"documents": []}))
    parser = _CountingParser()

    _load(source, corpus, parser, True)

    assert parser.calls == 1


def test_reuse_false_always_reingests(tmp_path: Path) -> None:
    source = tmp_path / "guide.md"
    source.write_text("Connect the adapter.")
    corpus = tmp_path / "generated" / "guide.json"
    parser = _CountingParser()

    _load(source, corpus, parser, False)
    _load(source, corpus, parser, False)

    assert parser.calls == 2


def test_folder_discovery_skips_mare_output_directory(tmp_path: Path, monkeypatch) -> None:
    from mare.chat import _discover_folder_inputs

    monkeypatch.chdir(tmp_path)
    (tmp_path / "guide.md").write_text("# guide")
    (tmp_path / "generated").mkdir()
    (tmp_path / "generated" / "guide.json").write_text(json.dumps({"documents": []}))

    documents, corpora = _discover_folder_inputs(tmp_path)
    assert documents == [str(tmp_path / "guide.md")]
    assert corpora == []

    _, explicit_corpora = _discover_folder_inputs(tmp_path / "generated")
    assert explicit_corpora == [str(tmp_path / "generated" / "guide.json")]
