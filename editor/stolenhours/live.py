"""Mode B client: talks to the StolenHours UE4SS mod through a file mailbox in %LOCALAPPDATA%\\StolenHours\\live."""

from __future__ import annotations

import os
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

from . import paths

HEARTBEAT_STALE_S = 5


@dataclass
class Reply:
    ok: bool
    text: str


class LiveError(RuntimeError):
    pass


class LiveBridge:
    def __init__(self, live_dir: Path | None = None):
        self.dir = Path(live_dir or paths.LIVE_DIR)
        self.dir.mkdir(parents=True, exist_ok=True)
        paths.DUMPS_DIR.mkdir(parents=True, exist_ok=True)
        self.cmd = self.dir / "cmd.txt"
        self.ack = self.dir / "ack.txt"
        self.heartbeat = self.dir / "heartbeat.txt"
        self.lock = threading.Lock()  # one mailbox: the live map polls while other tabs send commands

    def mod_alive(self) -> bool:
        try:
            return time.time() - self.heartbeat.stat().st_mtime < HEARTBEAT_STALE_S
        except FileNotFoundError:
            return False

    def send(self, verb: str, *args: str, timeout: float = 10.0) -> Reply:
        if not self.lock.acquire(timeout=timeout):
            raise LiveError(f"the mod is busy with another command; {verb} not sent")
        try:
            return self._send(verb, *args, timeout=timeout)
        finally:
            self.lock.release()

    def _send(self, verb: str, *args: str, timeout: float) -> Reply:
        if any("\t" in a or "\n" in a for a in (verb, *args)):
            raise LiveError("tabs and newlines are not allowed in commands")
        if not self.mod_alive():
            raise LiveError("live mod not running (no fresh heartbeat). Is the game running with UE4SS?")
        deadline = time.time() + timeout
        while self.cmd.exists():
            if time.time() > deadline:
                raise LiveError("previous command was never picked up")
            time.sleep(0.05)
        cid = uuid.uuid4().hex[:12]
        tmp = self.cmd.with_suffix(".tmp")
        tmp.write_bytes(("\t".join((cid, verb, *args)) + "\n").encode("utf-8"))
        os.replace(tmp, self.cmd)
        while time.time() < deadline:
            try:
                line = self.ack.read_text(encoding="utf-8", errors="replace")
            except (FileNotFoundError, PermissionError):
                time.sleep(0.05)
                continue
            parts = line.rstrip("\r\n").split("\t", 2)
            if parts[0] == cid:
                try:
                    self.ack.unlink()
                except OSError:
                    pass
                return Reply(parts[1:2] == ["OK"], parts[2] if len(parts) > 2 else "")
            time.sleep(0.05)
        try:
            self.cmd.unlink()
        except FileNotFoundError:
            pass
        raise LiveError(f"no reply to {verb} within {timeout}s")

    def ping(self) -> Reply:
        return self.send("PING", timeout=5)

    def find_prop(self, name: str) -> Reply:
        return self.send("FIND_PROP", name, timeout=60)

    def get(self, target: str, prop: str) -> Reply:
        return self.send("GET", target, prop)

    def set(self, target: str, prop: str, value) -> Reply:
        return self.send("SET", target, prop, str(value))

    def list_props(self, target: str) -> Reply:
        return self.send("LIST_PROPS", target, timeout=20)

    def dump(self) -> Reply:
        return self.send("DUMP", timeout=900)

    def dump_builtin(self) -> Reply:
        return self.send("DUMP_BUILTIN", timeout=1800)

    def events(self) -> Reply:
        return self.send("EVENTS", timeout=10)

    def player(self) -> Reply:
        return self.send("PLAYER", timeout=5)
