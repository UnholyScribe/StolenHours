"""Guards around writing the live save: game-running lock, SHA-256 backups, atomic replace."""

from __future__ import annotations

import csv
import datetime as _dt
import hashlib
import io
import os
import re
import shutil
import subprocess
from pathlib import Path

from . import deck, paths


class SafetyError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def running_game_processes() -> list[str]:
    # under Proton the game runs in its own Wine prefix, which tasklist can't see
    found = set(deck.running_on_host(paths.GAME_PROCESS_NAMES)) if deck.on_linux_host() else set()
    if os.name == "nt":
        out = subprocess.run(
            ["tasklist", "/FO", "CSV", "/NH"], capture_output=True, text=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        ).stdout
        wanted = {n.lower() for n in paths.GAME_PROCESS_NAMES}
        found |= {row[0] for row in csv.reader(io.StringIO(out)) if row and row[0].lower() in wanted}
    return sorted(found)


def require_game_closed() -> None:
    procs = running_game_processes()
    if procs:
        raise SafetyError(f"game is running ({', '.join(procs)}); file writes are locked. Use live mode instead.")


def backup(save: Path, reason: str) -> Path:
    stamp = _dt.datetime.now().strftime("%Y-%m-%d_%H%M%S")
    dest_dir = paths.BACKUP_ROOT / f"{stamp}_{reason}"
    n = 1
    while dest_dir.exists():
        n += 1
        dest_dir = paths.BACKUP_ROOT / f"{stamp}_{reason}-{n}"
    dest_dir.mkdir(parents=True, exist_ok=False)
    dest = dest_dir / save.name
    shutil.copy2(save, dest)
    digest = sha256_file(dest)
    if digest != sha256_file(save):
        raise SafetyError("backup copy hash does not match the source")
    mtime = _dt.datetime.fromtimestamp(save.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
    (dest_dir / "SHA256.txt").write_text(
        f"{digest}  {save.name}  (copied from {save}, original LastWriteTime {mtime})\n", encoding="ascii")
    return dest


def copy_verified(save: Path, dest: Path) -> str:
    """Copy the save somewhere the user picked; the copy's SHA-256 must match the original."""
    if dest.resolve() == save.resolve():
        raise SafetyError("pick a different place than the save itself")
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".stolenhours.tmp")
    shutil.copy2(save, tmp)
    digest = sha256_file(tmp)
    if digest != sha256_file(save):
        tmp.unlink(missing_ok=True)
        raise SafetyError("the copy's hash does not match the save; nothing was kept")
    os.replace(tmp, dest)
    return digest


def _read_any(path: Path) -> str:
    raw = path.read_bytes()
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return raw.decode("utf-16", errors="replace")
    return raw.decode("utf-8-sig", errors="replace")


def list_backups() -> list[dict]:
    """The automatic backups, newest first, each re-hashed against its SHA256.txt."""
    out = []
    root = paths.BACKUP_ROOT
    if not root.is_dir():
        return out
    for d in sorted((p for p in root.iterdir() if p.is_dir()), reverse=True):
        bins = sorted(d.glob("*.bin"))
        if not bins:
            continue
        # folder name: <YYYY-MM-DD_HHMMSS>_<reason>, as written by backup()
        try:
            when = _dt.datetime.strptime(d.name[:17], "%Y-%m-%d_%H%M%S").strftime("%Y-%m-%d %H:%M")
            reason = d.name[18:]
        except ValueError:
            when, _, reason = d.name.partition("_")
        sums = d / "SHA256.txt"
        # older records were written by PowerShell (UTF-8/UTF-16 with BOM)
        noted = re.findall(r"\b[0-9A-Fa-f]{64}\b", _read_any(sums))[:1] if sums.exists() else []
        noted = [n.upper() for n in noted]
        out.append({"path": str(bins[0]), "when": when, "reason": reason.replace("-", " "),
                    "intact": noted[0] == sha256_file(bins[0]) if noted else None,
                    "size": bins[0].stat().st_size})
    return sorted(out, key=lambda r: r["when"], reverse=True)


def atomic_write(target: Path, data: bytes) -> None:
    tmp = target.with_name(target.name + ".stolenhours.tmp")
    with open(tmp, "wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, target)
