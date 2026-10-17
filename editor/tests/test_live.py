"""Mailbox protocol test against a Python stand-in for the Lua mod."""

import os
import threading
import time

import pytest

from stolenhours import live


def fake_mod(d, stop):
    cmd, ack, hb = d / "cmd.txt", d / "ack.txt", d / "heartbeat.txt"
    state = {"Money": 100}
    while not stop.is_set():
        hb.write_text(str(time.time()))
        if cmd.exists():
            cid, verb, *args = cmd.read_text().rstrip("\n").split("\t")
            cmd.unlink()
            if verb == "PING":
                out = "OK\tpong"
            elif verb == "SET":
                state[args[1]] = int(args[2]); out = f"OK\t{state[args[1]]}"
            elif verb == "GET":
                out = f"OK\t{state[args[1]]}"
            else:
                out = "ERR\tunknown command " + verb
            tmp = d / "ack.tmp"
            tmp.write_text(f"{cid}\t{out}")
            os.replace(tmp, ack)
        time.sleep(0.02)


@pytest.fixture
def bridge(tmp_path):
    stop = threading.Event()
    t = threading.Thread(target=fake_mod, args=(tmp_path, stop), daemon=True)
    t.start()
    time.sleep(0.1)
    yield live.LiveBridge(tmp_path)
    stop.set()
    t.join()


def test_ping_get_set(bridge):
    assert bridge.ping().ok
    assert bridge.set("Obj", "Money", 5000).text == "5000"
    assert bridge.get("Obj", "Money").text == "5000"
    r = bridge.send("NOPE")
    assert not r.ok and "unknown" in r.text


def test_no_mod(tmp_path):
    with pytest.raises(live.LiveError):
        live.LiveBridge(tmp_path).ping()


def test_rejects_tabs(bridge):
    with pytest.raises(live.LiveError):
        bridge.set("a\tb", "Money", 1)
