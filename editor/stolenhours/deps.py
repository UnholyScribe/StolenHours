"""Portable dependency checks — no host-machine assumptions.

On a stranger's PC we detect what's missing, explain it in plain English, and point at
official installers. Never hard-code Unholy's paths or Steam layout.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import webbrowser
from dataclasses import dataclass, field
from pathlib import Path

WEBVIEW2_EVERGREEN = "https://go.microsoft.com/fwlink/p/?LinkId=2124703"
DOTNET48_DOWNLOAD = "https://dotnet.microsoft.com/download/dotnet-framework/net48"
STEAM_DOWNLOAD = "https://store.steampowered.com/about/"


@dataclass
class Dep:
    id: str
    name: str
    ok: bool
    required: bool
    detail: str = ""
    fix: str = ""
    url: str | None = None


@dataclass
class Report:
    deps: list[Dep] = field(default_factory=list)

    @property
    def blocking(self) -> list[Dep]:
        return [d for d in self.deps if d.required and not d.ok]

    @property
    def warnings(self) -> list[Dep]:
        return [d for d in self.deps if (not d.required) and not d.ok]

    @property
    def ok(self) -> bool:
        return not self.blocking

    def summary_text(self) -> str:
        lines = ["Stolen Hours — setup check", ""]
        for d in self.deps:
            mark = "OK" if d.ok else ("NEED" if d.required else "WARN")
            lines.append(f"[{mark}] {d.name}")
            if d.detail:
                lines.append(f"      {d.detail}")
            if not d.ok and d.fix:
                lines.append(f"      Fix: {d.fix}")
                if d.url:
                    lines.append(f"      Link: {d.url}")
            lines.append("")
        if self.blocking:
            lines.append("Install the NEED items, then run Stolen Hours again.")
        elif self.warnings:
            lines.append("You can run now. WARN items unlock extra features (native window / Live).")
        else:
            lines.append("All checks passed.")
        return "\n".join(lines).rstrip() + "\n"


def _reg_get(path: str, name: str | None = None) -> str | int | None:
    if os.name != "nt":
        return None
    try:
        import winreg
    except ImportError:
        return None
    hive, _, sub = path.partition("\\")
    roots = {"HKLM": winreg.HKEY_LOCAL_MACHINE, "HKCU": winreg.HKEY_CURRENT_USER}
    root = roots.get(hive)
    if root is None:
        return None
    for access in (winreg.KEY_READ | getattr(winreg, "KEY_WOW64_64KEY", 0),
                   winreg.KEY_READ | getattr(winreg, "KEY_WOW64_32KEY", 0),
                   winreg.KEY_READ):
        try:
            with winreg.OpenKey(root, sub, 0, access) as key:
                if name is None:
                    return "ok"
                val, _ = winreg.QueryValueEx(key, name)
                return val
        except OSError:
            continue
    return None


def webview2_installed() -> tuple[bool, str]:
    """Edge WebView2 Runtime (Evergreen) — preferred native UI for the portable exe."""
    # Client GUID used by the evergreen runtime installer.
    guid = "{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"
    for hive in ("HKLM", "HKCU"):
        for base in (
            rf"{hive}\SOFTWARE\Microsoft\EdgeUpdate\Clients\{guid}",
            rf"{hive}\SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{guid}",
        ):
            ver = _reg_get(base, "pv")
            if ver and str(ver) not in ("", "0.0.0.0"):
                return True, f"WebView2 {ver}"
    # Fallback: msedgewebview2.exe next to Edge
    candidates = [
        Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"))
        / "Microsoft" / "EdgeWebView" / "Application" / "msedgewebview2.exe",
        Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
        / "Microsoft" / "EdgeWebView" / "Application" / "msedgewebview2.exe",
    ]
    for p in candidates:
        if p.is_file():
            return True, str(p)
    return False, "not found"


def dotnet48_installed() -> tuple[bool, str]:
    """Full .NET Framework 4.8+ (Release >= 528040). Only needed for the old WinForms UI path."""
    rel = _reg_get(r"HKLM\SOFTWARE\Microsoft\NET Framework Setup\NDP\v4\Full", "Release")
    try:
        n = int(rel) if rel is not None else 0
    except (TypeError, ValueError):
        n = 0
    if n >= 528040:
        return True, f"Release {n}"
    if n:
        return False, f"Release {n} (need 4.8 / Release >= 528040)"
    return False, "not found"


def browser_available() -> tuple[bool, str]:
    """Any browser we can open as a UI fallback."""
    if os.name == "nt":
        for key in (
            r"HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\msedge.exe",
            r"HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe",
            r"HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\firefox.exe",
        ):
            p = _reg_get(key, None)
            # App Paths default value is the exe path
            try:
                import winreg
                hive = winreg.HKEY_LOCAL_MACHINE
                sub = key.split("\\", 1)[1]
                with winreg.OpenKey(hive, sub) as k:
                    val, _ = winreg.QueryValueEx(k, "")
                    if val and Path(str(val)).is_file():
                        return True, str(val)
            except OSError:
                continue
        for name in ("msedge", "chrome", "firefox", "brave"):
            hit = shutil.which(name)
            if hit:
                return True, hit
        # os.startfile / webbrowser usually still works via association
        return True, "Windows default browser association"
    hit = shutil.which("xdg-open") or shutil.which("open")
    return (bool(hit), hit or "no xdg-open/open")


def steam_or_game_hint() -> tuple[bool, str]:
    """Soft check — editor can still open; save/key need the game once."""
    try:
        from . import steam
        games = steam.find_game_dirs()
        saves = steam.find_saves()
        if games and saves:
            return True, f"game + save found ({games[0].name})"
        if games:
            return True, f"game found, no save yet — play once and save in-game"
        if saves:
            return True, "save found without a local game install (key may need the shipping exe)"
        return False, "Fantasy Life i / Steam not found yet"
    except Exception as e:
        return False, f"check skipped ({e})"


def check() -> Report:
    report = Report()
    # MOTW is cleared silently at launch (motw.ensure_unblocked); not a user-facing gate.
    wv_ok, wv_detail = webview2_installed()
    report.deps.append(Dep(
        id="webview2",
        name="Microsoft Edge WebView2 Runtime",
        ok=wv_ok,
        required=False,  # browser fallback works without it
        detail=wv_detail if wv_ok else "Needed for the built-in Stolen Hours window.",
        fix="Install the Evergreen Runtime, then run Stolen Hours again.",
        url=WEBVIEW2_EVERGREEN,
    ))
    net_ok, net_detail = dotnet48_installed()
    report.deps.append(Dep(
        id="dotnet48",
        name=".NET Framework 4.8",
        ok=net_ok,
        required=False,  # edgechromium / browser avoid pythonnet
        detail=net_detail if net_ok else "Only needed for a legacy UI path; browser mode works without it.",
        fix="Install .NET Framework 4.8 from Microsoft, then retry.",
        url=DOTNET48_DOWNLOAD,
    ))
    br_ok, br_detail = browser_available()
    report.deps.append(Dep(
        id="browser",
        name="Web browser (fallback UI)",
        ok=br_ok,
        required=True,
        detail=br_detail,
        fix="Install Edge, Chrome, or Firefox, then run Stolen Hours again.",
        url="https://www.microsoft.com/edge",
    ))
    st_ok, st_detail = steam_or_game_hint()
    report.deps.append(Dep(
        id="game",
        name="Fantasy Life i (Steam)",
        ok=st_ok,
        required=False,
        detail=st_detail,
        fix="Install / launch the game from Steam and make one save, then reopen Stolen Hours.",
        url=STEAM_DOWNLOAD,
    ))
    return report


def open_fix_url(dep: Dep) -> None:
    if dep.url:
        webbrowser.open(dep.url)


def write_report(report: Report, path: Path | None = None) -> Path:
    from . import paths
    out = path or (paths.USER_DATA / "setup_check.txt")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report.summary_text(), encoding="utf-8")
    return out


def gui_prompt_missing(report: Report) -> str:
    """Windows MessageBox chooser. Returns 'continue' | 'install' | 'quit'.

    Plain English for a stranger PC: what's missing, official link, or keep going
    with what you have and come back later.
    """
    if report.ok and not report.warnings:
        return "continue"
    text = report.summary_text()
    if len(text) > 1200:
        text = text[:1200] + "\n…"
    if os.name != "nt":
        print(text)
        return "continue" if not report.blocking else "quit"
    import ctypes
    missing = report.blocking or report.warnings
    first = missing[0] if missing else None
    body = text + "\n"
    body += "Yes = open the official download for the first missing item "
    body += "(install it yourself, then reopen Stolen Hours)\n"
    body += "No = keep going with what this PC already has\n"
    body += "Cancel = quit for now"
    flags = 0x03 | 0x30  # YESNOCANCEL | WARNING
    if report.blocking:
        flags = 0x03 | 0x10  # YESNOCANCEL | HAND
    res = ctypes.windll.user32.MessageBoxW(None, body, "Stolen Hours — what this PC needs", flags)
    if res == 6:  # IDYES
        if first:
            open_fix_url(first)
        return "install"
    if res == 7:  # IDNO
        return "continue"
    return "quit"
