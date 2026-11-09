"""Portable dependency checks — no network, no real Steam required."""

from stolenhours import deps


def test_check_returns_report():
    r = deps.check()
    ids = {d.id for d in r.deps}
    assert {"webview2", "dotnet48", "browser", "game"} <= ids
    assert isinstance(r.ok, bool)
    text = r.summary_text()
    assert "Stolen Hours" in text
    assert "[OK]" in text or "[NEED]" in text or "[WARN]" in text


def test_write_report(tmp_path):
    r = deps.check()
    out = deps.write_report(r, tmp_path / "setup_check.txt")
    assert out.is_file()
    assert "setup check" in out.read_text(encoding="utf-8").lower() or "Stolen Hours" in out.read_text(encoding="utf-8")
