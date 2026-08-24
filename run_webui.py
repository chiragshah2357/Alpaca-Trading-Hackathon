"""Launch the live app UI (README §4 UI).

    python run_webui.py            # http://127.0.0.1:8787  (mock unless ALPACA_* set)
    WEBUI_PORT=9000 python run_webui.py
"""
from __future__ import annotations

import os

from webui.server import serve

if __name__ == "__main__":
    serve(host=os.getenv("WEBUI_HOST", "127.0.0.1"), port=int(os.getenv("WEBUI_PORT", "8787")))
