"""The encrypted `gamedata.bin` container.

Layout (verified 2026-10-11 against the real save, matches Niedzielan/fli_save_editor fli_bin2sav.py):

    AES-256-ECB( PKCS#7( u32 gvas_size | zlib(gvas, level 6) | footer ) )
    footer (34 bytes) = u32 1 | MD5(u32 gvas_size | zlib stream) | 14 x 0x00

zlib level 6 / memLevel 8 / wbits 15 reproduces the game's compressed stream byte for byte.
"""

from __future__ import annotations

import hashlib
import mmap
import re
import struct
import zlib
from dataclasses import dataclass
from pathlib import Path

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

from . import paths, steam

BLOCK = 16
FOOTER_VERSION = 1
FOOTER_ZERO_LEN = 14
FOOTER_LEN = 4 + 16 + FOOTER_ZERO_LEN
ZLIB_LEVEL = 6


class ContainerError(ValueError):
    pass


# The game exe holds the save key as a 32-character UTF-16LE string; candidates are tested against the save itself.
KEY_CANDIDATE = re.compile(rb"(?<![\x20-\x7e]\x00)((?:[\x21-\x7e]\x00){32})\x00\x00")
_found_key: bytes | None = None


def key_from_game(exe: Path, raw: bytes) -> bytes | None:
    """Finds the key in the user's own game binary: the one candidate that decrypts `raw` into a valid container."""
    with open(exe, "rb") as f, mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as m:
        seen = set()
        for hit in KEY_CANDIDATE.finditer(m):
            key = hit.group(1)[::2]
            if key in seen:
                continue
            seen.add(key)
            head = AES.new(key, AES.MODE_ECB).decrypt(raw[:BLOCK])
            if head[4] & 0x0F != 8 or (head[4] << 8 | head[5]) % 31:  # zlib header after the size prefix
                continue
            try:
                unpack(raw, key)
            except ContainerError:
                continue
            return key
    return None


def resolve_key(raw: bytes | None = None) -> bytes:
    """Project key file when it still decrypts the save; otherwise scan the installed game exe.

    After a Steam update the key file can be stale. When `raw` is given we only keep the file key if it
    actually unpacks; otherwise we re-walk every Fantasy Life i install for a UTF-16LE candidate that works.
    """
    global _found_key
    if _found_key and raw is not None:
        try:
            unpack(raw, _found_key)
            return _found_key
        except ContainerError:
            _found_key = None
    elif _found_key and raw is None:
        return _found_key

    if paths.KEY_FILE.exists():
        file_key = load_key()
        if raw is None:
            return file_key
        try:
            unpack(raw, file_key)
            _found_key = file_key
            return file_key
        except ContainerError:
            pass  # stale after an update — fall through to the game binary

    if raw is None:
        raise ContainerError("no key file, and no save given to test game keys against")
    for game in steam.find_game_dirs():
        key = key_from_game(game / steam.SHIPPING_REL, raw)
        if key:
            _found_key = key
            return key
    raise ContainerError("could not find the save key in the Fantasy Life i install "
                         f"(set {steam.ENV_GAME} if the game is somewhere unusual)")


def load_key(path=None) -> bytes:
    path = path or paths.KEY_FILE
    try:
        text = open(path, encoding="ascii").read()
    except FileNotFoundError as e:
        raise ContainerError(f"AES key file missing: {path}") from e
    key = bytes.fromhex("".join(text.split()))
    if len(key) != 32:
        raise ContainerError(f"AES key must be 32 bytes, got {len(key)}")
    return key


@dataclass
class Unpacked:
    gvas: bytes
    footer_version: int
    md5_ok: bool


def unpack(raw: bytes, key: bytes, strict: bool = True) -> Unpacked:
    if len(raw) == 0 or len(raw) % BLOCK:
        raise ContainerError(f"file size {len(raw)} is not a multiple of {BLOCK}")
    try:
        plain = unpad(AES.new(key, AES.MODE_ECB).decrypt(raw), BLOCK)
    except ValueError as e:
        raise ContainerError("bad PKCS#7 padding (wrong key or not a gamedata.bin)") from e
    if len(plain) < 4 + FOOTER_LEN:
        raise ContainerError("payload too short")

    body, footer = plain[:-FOOTER_LEN], plain[-FOOTER_LEN:]
    footer_version = struct.unpack_from("<I", footer, 0)[0]
    md5_ok = hashlib.md5(body).digest() == footer[4:20]
    if strict:
        if footer_version != FOOTER_VERSION:
            raise ContainerError(f"unknown footer version {footer_version}")
        if footer[20:] != bytes(FOOTER_ZERO_LEN):
            raise ContainerError("footer padding is not zero")
        if not md5_ok:
            raise ContainerError("MD5 checksum mismatch")

    size = struct.unpack_from("<I", body, 0)[0]
    d = zlib.decompressobj()
    gvas = d.decompress(body[4:])
    if not d.eof or d.unused_data:
        raise ContainerError("zlib stream incomplete or followed by extra bytes")
    if len(gvas) != size:
        raise ContainerError(f"size prefix {size} != decompressed {len(gvas)}")
    return Unpacked(gvas=gvas, footer_version=footer_version, md5_ok=md5_ok)


def pack(gvas: bytes, key: bytes) -> bytes:
    c = zlib.compressobj(ZLIB_LEVEL, zlib.DEFLATED, 15, 8)
    body = struct.pack("<I", len(gvas)) + c.compress(gvas) + c.flush()
    footer = struct.pack("<I", FOOTER_VERSION) + hashlib.md5(body).digest() + bytes(FOOTER_ZERO_LEN)
    return AES.new(key, AES.MODE_ECB).encrypt(pad(body + footer, BLOCK))


def roundtrip_exact(raw: bytes, key: bytes) -> bool:
    return pack(unpack(raw, key).gvas, key) == raw
