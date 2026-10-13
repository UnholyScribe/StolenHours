"""Entry point for the built StolenHours.exe (windowed, so errors go to a log and a message box)."""

import os
import sys
import traceback
from pathlib import Path


def selftest() -> None:
    """Read-only check of everything a fresh machine needs; report in %LOCALAPPDATA%\\StolenHours\\selftest.txt."""
    from stolenhours import container, paths, savefile, steam
    lines = [f"steam roots: {steam.find_steam_roots()}", f"game: {steam.find_game_dirs()}",
             f"saves: {[str(s.path) for s in steam.find_saves()]}", f"key file used: {paths.KEY_FILE.exists()}"]
    sf = savefile.SaveFile.load(paths.default_save_path())
    lines += [f"loaded: {sf.path}", f"key from game: {container._found_key is not None}",
              f"roundtrip byte-exact: {container.roundtrip_exact(sf.raw, sf.key)}", "OK"]
    out = paths.USER_DATA / "selftest.txt"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    try:
        if "--selftest" in sys.argv:
            selftest()
            return
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
        log.write_text(traceback.format_exc(), encoding="utf-8")
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, f"Stolen Hours hit an error.\n\nDetails: {log}", "Stolen Hours", 0x10)
        sys.exit(1)


if __name__ == "__main__":
    main()
