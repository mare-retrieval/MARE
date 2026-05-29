from __future__ import annotations

from pathlib import Path

import pytest

from mare.start import main


def test_start_without_path_uses_demo_plan(capsys) -> None:
    main([])
    output = capsys.readouterr().out

    assert "bundled mixed-document example" in output
    assert "mare chat --folder examples/mixed_docs" in output


def test_start_for_folder_recommends_chat(capsys, tmp_path: Path) -> None:
    folder = tmp_path / "docs"
    folder.mkdir()
    (folder / "guide.md").write_text("# Setup\nUse the adapter.")
    (folder / "notes.txt").write_text("Onboarding steps")

    main([str(folder)])
    output = capsys.readouterr().out

    assert f"Folder: {folder.as_posix()}" in output
    assert "Supported documents found: 2" in output
    assert f"mare chat --folder {folder.as_posix()}" in output


def test_start_for_pdf_recommends_ask(capsys, tmp_path: Path) -> None:
    document = tmp_path / "manual.pdf"
    document.write_text("placeholder")

    main([str(document)])
    output = capsys.readouterr().out

    assert f"Document: {document.as_posix()}" in output
    assert f'mare ask {document.as_posix()} "what are the key setup steps"' in output


def test_start_for_non_pdf_document_recommends_workflow(capsys, tmp_path: Path) -> None:
    document = tmp_path / "manual.md"
    document.write_text("# Setup")

    main([str(document)])
    output = capsys.readouterr().out

    assert f'Document: {document.as_posix()}' in output
    assert f'mare workflow --document {document.as_posix()} --query "what are the key setup steps"' in output


def test_start_for_missing_path_exits() -> None:
    with pytest.raises(SystemExit, match="Path not found"):
        main(["./does-not-exist"])
