from __future__ import annotations

import sys
from pathlib import Path


def main() -> None:
    try:
        from streamlit.web import cli as stcli
    except ImportError as exc:
        raise RuntimeError(
            "MARE UI requires Streamlit. Install it with `pip install \"mare-retrieval[ui]\"`."
        ) from exc

    app_path = Path(__file__).with_name("streamlit_app.py")
    sys.argv = [
        "streamlit",
        "run",
        str(app_path),
        "--server.fileWatcherType",
        "none",
    ]
    raise SystemExit(stcli.main())


if __name__ == "__main__":
    main()
