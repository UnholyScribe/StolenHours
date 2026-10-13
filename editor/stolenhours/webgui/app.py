"""Opens the game-styled editor in a native window (pywebview / Edge WebView2), or the browser as a fallback."""

from __future__ import annotations

import os
import time
import webbrowser
from pathlib import Path

from .. import deck
from . import server


def main(save_path: Path | None = None, browser: bool = False, port: int = 0) -> None:
    server.ensure_assets()
    srv, url = server.start(save_path, port)
    try:
        import webview
    except ImportError:
        webview = None
    if deck.under_wine() and not os.environ.get("STOLENHOURS_WEBVIEW"):
        browser = True  # WebView2 rarely runs under Proton; pywebview would fall back to the old IE engine
    if browser or webview is None:
        print(f"Stolen Hours editor: {url}  (Ctrl+C to stop)")
        webbrowser.open(url)
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            pass
        return
    server.WINDOW = webview.create_window("Stolen Hours · Fantasy Life i", url, width=1440, height=900,
                                          min_size=(1180, 760), background_color="#6cc7e8", text_select=False)
    webview.start()
    srv.shutdown()
