from __future__ import annotations

import sys

from mare.cli import main


def test_main_prints_help(capsys, monkeypatch) -> None:
    monkeypatch.setattr(sys, "argv", ["mare"])

    main()
    output = capsys.readouterr().out

    assert "Grounded answers over documents and folders, with proof." in output
    assert "mare start" in output
    assert "mare ui" in output
    assert "mare chat" in output


def test_main_dispatches_to_subcommand(monkeypatch) -> None:
    captured = {}

    class _FakeModule:
        @staticmethod
        def main():
            captured["argv"] = list(sys.argv)

    monkeypatch.setattr(sys, "argv", ["mare", "ask", "manual.pdf", "adapter"])
    monkeypatch.setitem(sys.modules, "mare.ask", _FakeModule)

    main()

    assert captured["argv"] == ["mare ask", "manual.pdf", "adapter"]


def test_main_dispatches_to_start(monkeypatch) -> None:
    captured = {}

    class _FakeModule:
        @staticmethod
        def main():
            captured["argv"] = list(sys.argv)

    monkeypatch.setattr(sys, "argv", ["mare", "start", "./docs"])
    monkeypatch.setitem(sys.modules, "mare.start", _FakeModule)

    main()

    assert captured["argv"] == ["mare start", "./docs"]
