"""Builds the standalone StolenHours.exe (PyInstaller, one folder) into <dest>, default G:\\Stolen Hours.

Shippable: no key and no project paths inside. At runtime the exe finds Steam, the game and the saves itself and
reads the save key from the installed game (container.resolve_key). Backups go to %LOCALAPPDATA%\\StolenHours.
"""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image

from stolenhours import modinstall, paths

EDITOR = Path(__file__).resolve().parent
WEB = paths.PACKAGE_DIR / "webgui" / "web"
DECK = EDITOR / "deck"  # Steam Deck launcher and instructions, shipped next to the exe
PARSER_DATA = ("fli_sav_pattern.txt", "itemlist.txt", "skilllist.txt", "flaglist.txt")


def _set_aside(fn, path, exc) -> None:
    """A file Windows still has mapped can be renamed but not deleted; move it out of the way instead."""
    p = Path(path)
    if fn is not os.rmdir and p.is_file():
        p.rename(p.with_name(p.name + ".old"))


def _running_from(dest: Path) -> list[str]:
    """Processes started from `dest` (by image path, so a renamed exe still counts)."""
    ps = ("Get-CimInstance Win32_Process | Where-Object { $_.ExecutablePath -like '%s\\*' } | "
          "ForEach-Object { \"$($_.ProcessId) $($_.Name)\" }" % str(dest.resolve()).replace("'", "''"))
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True,
                             timeout=30).stdout
    except (OSError, subprocess.TimeoutExpired):
        return []
    return [line for line in out.splitlines() if line.strip()]


def main(dest: Path) -> None:
    running = _running_from(dest) if dest.exists() else []
    if running:
        sys.exit(f"close Stolen Hours first (running from {dest}: {', '.join(running)})")
    if not (WEB / "game" / "wallpaper.jpg").exists():
        sys.exit("UI assets missing; run `python -m stolenhours build-ui` first")
    work = Path(tempfile.mkdtemp(prefix="stolenhours_build_"))
    icon = work / "icon.ico"
    Image.open(WEB / "game" / "coin.png").convert("RGBA").save(icon, sizes=[(256, 256), (64, 64), (48, 48), (32, 32), (16, 16)])
    data = [f"{WEB};stolenhours/webgui/web"]
    data += [f"{paths.COMMUNITY_EDITOR / n};tools/fli_save_editor" for n in PARSER_DATA]
    data += [f"{modinstall.BUNDLED};hook/ue4ss_mod/{modinstall.MOD_NAME}"]
    cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--windowed", "--onedir",
           "--name", "StolenHours", "--icon", str(icon),
           "--distpath", str(work / "dist"), "--workpath", str(work / "build"), "--specpath", str(work),
           "--paths", str(paths.COMMUNITY_EDITOR), "--hidden-import", "fli_sav2json",
           "--collect-all", "webview"]
    for d in data:
        cmd += ["--add-data", d]
    subprocess.run(cmd + [str(EDITOR / "launcher.py")], check=True, cwd=EDITOR)
    out = work / "dist" / "StolenHours"
    leaked = [p for p in out.rglob("*") if p.suffix in (".hex", ".usmap")]
    if leaked:
        sys.exit(f"refusing to ship key/mapping files: {leaked}")
    if dest.exists():
        if not any(dest.glob("StolenHours*.exe")):
            sys.exit(f"{dest} exists and is not a previous build; refusing to replace it")
        shutil.rmtree(dest, onexc=_set_aside)
    shutil.copytree(out, dest, dirs_exist_ok=True)
    for f in DECK.iterdir():
        (dest / f.name).write_bytes(f.read_bytes().replace(b"\r\n", b"\n"))  # bash refuses CRLF scripts
    shutil.rmtree(work, ignore_errors=True)
    print(f"built {dest / 'StolenHours.exe'}")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else Path(r"<portable build dir>"))
