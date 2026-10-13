"""The shipped exe has no key; it finds it in the game binary by testing candidates against the save."""

import os

from stolenhours import container


def _utf16(s: bytes) -> bytes:
    return s.decode("ascii").encode("utf-16-le") + b"\x00\x00"


def test_finds_key_among_decoys(tmp_path):
    key = os.urandom(16).hex().encode()  # 32 printable chars, like the real one
    raw = container.pack(b"GVAS" + os.urandom(200), key)
    decoys = [b"A" * 32, b"x9" * 16, os.urandom(16).hex().encode()]
    exe = tmp_path / "game.exe"
    exe.write_bytes(os.urandom(4096) + b"".join(_utf16(d) + os.urandom(64) for d in decoys)
                    + _utf16(key) + os.urandom(4096))
    assert container.key_from_game(exe, raw) == key


def test_no_key_in_binary(tmp_path):
    raw = container.pack(b"GVAS" + os.urandom(200), os.urandom(16).hex().encode())
    exe = tmp_path / "game.exe"
    exe.write_bytes(os.urandom(8192) + _utf16(b"B" * 32))
    assert container.key_from_game(exe, raw) is None
