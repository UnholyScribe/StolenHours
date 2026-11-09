"""Opens the game-styled editor in a native window (pywebview / Edge WebView2), or the browser as a fallback.

Portable rule: never assume Unholy's PC. If the native window can't start (missing WebView2,
broken pythonnet/.NET, Wine, etc.), fall back to the system browser and keep serving locally.
"""

from __future__ import annotations

import os
import time
import webbrowser
from pathlib import Path

from .. import deck, deps
from . import server


def _run_browser(url: str, srv) -> None:
    print(f"Stolen Hours editor (browser): {url}")
    print("Leave this process running; close the terminal / kill the exe to stop.")
    webbrowser.open(url)
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        pass
    finally:
        try:
            srv.shutdown()
        except Exception:
            pass


def _try_native(webview, url: str, srv) -> bool:
    """Try Edge WebView2 first (no pythonnet). Return True if the window ran to completion."""
    server.WINDOW = webview.create_window(
        "Stolen Hours · Fantasy Life i", url, width=1440, height=900,
        min_size=(1180, 760), background_color="#6cc7e8", text_select=False,
    )
    # edgechromium = WebView2. Avoid default winforms/pythonnet path (Luby crash).
    guis: list[str] = []
    wv_ok, _ = deps.webview2_installed()
    if wv_ok:
        guis.append("edgechromium")
    # Only try winforms if .NET looks present — otherwise pythonnet blows up (Luby's crash).
    net_ok, _ = deps.dotnet48_installed()
    if net_ok and os.name == "nt":
        guis.append("winforms")
    if not guis:
        print("no native UI backend available (need WebView2 or .NET 4.8); using browser")
        return False
    last_err: Exception | None = None
    for gui in guis:
        try:
            webview.start(gui=gui)
            return True
        except Exception as e:
            last_err = e
            print(f"native UI ({gui}) failed: {e}")
            continue
    if last_err:
        print(f"native UI unavailable: {last_err}")
    return False


def main(save_path: Path | None = None, browser: bool = False, port: int = 0) -> None:
    # --browser / STOLENHOURS_BROWSER=1 forces browser mode (support / CI).
    if "--browser" in sys_argv() or os.environ.get("STOLENHOURS_BROWSER", "").strip() in ("1", "true", "yes"):
        browser = True

    report = deps.check()
    deps.write_report(report)

    # Only hard blockers stop launch (no browser at all). Soft warnings (WebView2, game/save,
    # MOTW already cleared) must not eject the user into a "run a command / come back" loop —
    # the EXE should open and explain inside the UI.
    if report.blocking:
        choice = deps.gui_prompt_missing(report)
        if choice == "quit":
            return
        if choice == "install":
            if os.name == "nt":
                import ctypes
                ctypes.windll.user32.MessageBoxW(
                    None,
                    "Install what you need from the page that opened, then start "
                    "Stolen Hours again.\n\n"
                    f"Full checklist:\n{deps.write_report(report)}",
                    "Stolen Hours — come back when ready",
                    0x40,
                )
            return

    server.ensure_assets()
    srv, url = server.start(save_path, port)

    if deck.under_wine() and not os.environ.get("STOLENHOURS_WEBVIEW"):
        browser = True  # WebView2 rarely runs under Proton

    try:
        import webview
    except ImportError:
        webview = None

    if browser or webview is None:
        _run_browser(url, srv)
        return

    try:
        if _try_native(webview, url, srv):
            srv.shutdown()
            return
    except Exception as e:
        print(f"native window failed, falling back to browser: {e}")

    # Luby-class failure: pythonnet / WebView2 missing — still usable in browser.
    if os.name == "nt":
        import ctypes
        ctypes.windll.user32.MessageBoxW(
            None,
            "The built-in window couldn't start on this PC "
            "(often missing WebView2 or a .NET/UI library).\n\n"
            "Stolen Hours will open in your browser instead — same editor.\n\n"
            f"Details also in:\n{deps.write_report(report)}",
            "Stolen Hours",
            0x30,
        )
    _run_browser(url, srv)


def sys_argv() -> list[str]:
    import sys
    return list(sys.argv)
