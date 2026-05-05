from __future__ import annotations

import sys
from pathlib import Path

from mare.ui import main


def test_main_invokes_streamlit_cli(monkeypatch) -> None:
    captured = {}

    class _FakeCLI:
        @staticmethod
        def main():
            captured["argv"] = list(sys.argv)
            return 0

    fake_web = type("StreamlitWeb", (), {"cli": _FakeCLI})()
    fake_streamlit = type("Streamlit", (), {"web": fake_web})()
    monkeypatch.setitem(sys.modules, "streamlit.web.cli", _FakeCLI)
    monkeypatch.setitem(sys.modules, "streamlit.web", fake_web)
    monkeypatch.setitem(sys.modules, "streamlit", fake_streamlit)

    try:
        main()
    except SystemExit as exc:
        assert exc.code == 0
    else:
        raise AssertionError("Expected ui.main() to exit through streamlit CLI.")

    assert captured["argv"][0] == "streamlit"
    assert captured["argv"][1] == "run"
    assert Path(captured["argv"][2]).name == "streamlit_app.py"
    assert "--server.fileWatcherType" in captured["argv"]
    assert "none" in captured["argv"]
