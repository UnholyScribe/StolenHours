"""Entry point for the built StolenHours.exe (windowed, so errors go to a log and a message box).

Portable: discovers Steam/game/saves on the user's machine; never embeds Unholy's paths or keys.
"""

import os
import sys
import traceback
from pathlib import Path


def selftest() -> None:
    """Read-only check of everything a fresh machine needs; report in %LOCALAPPDATA%\\StolenHours\\selftest.txt."""
    from stolenhours import container, deps, paths, savefile, steam
    lines = [
        f"steam roots: {steam.find_steam_roots()}",
        f"game: {steam.find_game_dirs()}",
        f"saves: {[str(s.path) for s in steam.find_saves()]}",
        f"key file used: {paths.KEY_FILE.exists()}",
    ]
    report = deps.check()
    lines += ["", "=== setup check ===", report.summary_text()]
    try:
        sf = savefile.SaveFile.load(paths.default_save_path())
        lines += [f"loaded: {sf.path}", f"key from game: {container._found_key is not None}",
                  f"roundtrip byte-exact: {container.roundtrip_exact(sf.raw, sf.key)}", "OK"]
    except Exception as e:
        lines += [f"save load: {e}"]
    out = paths.USER_DATA / "selftest.txt"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    deps.write_report(report)


def main() -> None:
    try:
        # GitHub zip → Windows MOTW blocks _internal DLLs. Clear it silently so double-click works
        # (no Unblock-File / Run.cmd required).
        if getattr(sys, "frozen", False) and os.name == "nt" and "--serve" not in sys.argv:
            from stolenhours import motw
            motw.ensure_unblocked()
        if "--selftest" in sys.argv:
            selftest()
            return
        if "--check" in sys.argv:
            from stolenhours import deps
            report = deps.check()
            path = deps.write_report(report)
            print(report.summary_text())
            print(f"(also wrote {path})")
            if os.name == "nt":
                import ctypes
                ctypes.windll.user32.MessageBoxW(
                    None, report.summary_text()[:1500], "Stolen Hours — setup check", 0x40)
            sys.exit(0 if report.ok else 2)
        if "--serve" in sys.argv:
            # headless diagnostics: StolenHours.exe --serve PORT TOKEN, then open http://127.0.0.1:PORT/?t=TOKEN
            import time
            from stolenhours.webgui import server
            i = sys.argv.index("--serve")
            server.start(None, int(sys.argv[i + 1]), sys.argv[i + 2])
            while True:
                time.sleep(3600)
        from stolenhours.webgui import app
        app.main()
    except Exception:
        log = Path(os.environ.get("LOCALAPPDATA", ".")) / "StolenHours" / "editor_crash.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        tb = traceback.format_exc()
        log.write_text(tb, encoding="utf-8")
        hint = ""
        low = tb.lower()
        if "python.runtime" in low or "pythonnet" in low or "clr_loader" in low:
            hint = ("\n\nThis PC hit a known UI library issue.\n"
                    "Try again after installing WebView2 Runtime:\n"
                    "https://go.microsoft.com/fwlink/p/?LinkId=2124703\n"
                    "Or run: StolenHours.exe --browser\n"
                    "If this is a fresh GitHub download, also try "
                    "\"Run Stolen Hours.cmd\" in the unzipped folder "
                    "(unblocks Windows download protection).")
        elif "webview" in low:
            hint = ("\n\nInstall Microsoft Edge WebView2 Runtime, then reopen Stolen Hours:\n"
                    "https://go.microsoft.com/fwlink/p/?LinkId=2124703")
        elif "dll" in low or "load" in low or "module" in low:
            hint = ("\n\nIf you just unzipped a GitHub download, Windows may be blocking files.\n"
                    "Double-click \"Run Stolen Hours.cmd\" in the Stolen Hours folder once.")
        import ctypes
        ctypes.windll.user32.MessageBoxW(
            None,
            f"Stolen Hours hit an error.{hint}\n\nDetails: {log}",
            "Stolen Hours",
            0x10,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
