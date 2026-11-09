"""Mark-of-the-Web helpers — ADS create/clear without touching a real exe tree."""

from pathlib import Path

from stolenhours import motw


def test_clear_motw_roundtrip(tmp_path: Path):
    f = tmp_path / "dummy.dll"
    f.write_bytes(b"x")
    assert not motw.has_motw(f)
    Path(str(f) + ":Zone.Identifier").write_text("[ZoneTransfer]\nZoneId=3\n", encoding="utf-8")
    assert motw.has_motw(f)
    assert motw.clear_motw(f)
    assert not motw.has_motw(f)


def test_unblock_tree(tmp_path: Path):
    a = tmp_path / "StolenHours.exe"
    b = tmp_path / "_internal" / "Python.Runtime.dll"
    b.parent.mkdir()
    a.write_bytes(b"e")
    b.write_bytes(b"d")
    for p in (a, b):
        Path(str(p) + ":Zone.Identifier").write_text("[ZoneTransfer]\nZoneId=3\n", encoding="utf-8")
    hits = motw.scan(tmp_path)
    assert a in hits and b in hits
    n = motw.unblock_tree(tmp_path)
    assert n >= 2
    assert motw.scan(tmp_path) == []
