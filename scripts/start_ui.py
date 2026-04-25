from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
    deps_path = project_root / ".tmp" / "pydeps"
    app_path = project_root / "ui" / "app.py"

    sys.path.insert(0, str(deps_path))
    from streamlit.web import cli as streamlit_cli

    sys.argv = [
        "streamlit",
        "run",
        str(app_path),
        "--server.headless",
        "true",
        "--server.port",
        "8501",
        "--server.address",
        "127.0.0.1",
    ]
    return streamlit_cli.main()


if __name__ == "__main__":
    raise SystemExit(main())
