"""Guards around writing the live save: game-running lock, SHA-256 backups, atomic replace."""

from __future__ import annotations

import csv
import datetime as _dt
import hashlib
import io
import os
import shutil
import subprocess
from pathlib import Path

from . import paths


class SafetyError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def running_game_processes() -> list[str]:
    out = subprocess.run(
        ["tasklist", "/FO", "CSV", "/NH"], capture_output=True, text=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    ).stdout
    wanted = {n.lower() for n in paths.GAME_PROCESS_NAMES}
    return sorted({row[0] for row in csv.reader(io.StringIO(out)) if row and row[0].lower() in wanted})


def require_game_closed() -> None:
    procs = running_game_processes()
    if procs:
        raise SafetyError(f"game is running ({', '.join(procs)}); file writes are locked. Use live mode instead.")


def backup(save: Path, reason: str) -> Path:
    stamp = _dt.datetime.now().strftime("%Y-%m-%d_%H%M%S")
    dest_dir = paths.BACKUP_ROOT / f"{stamp}_{reason}"
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


def atomic_write(target: Path, data: bytes) -> None:
    tmp = target.with_name(target.name + ".stolenhours.tmp")
    with open(tmp, "wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, target)
