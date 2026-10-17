import hashlib
import os

import pytest

from conftest import SAMPLE_SHA256
from stolenhours import container


def test_sample_is_the_backed_up_file(sample_raw):
    assert hashlib.sha256(sample_raw).hexdigest().upper() == SAMPLE_SHA256


def test_unpack_sample(sample_raw, key):
    up = container.unpack(sample_raw, key)
    assert up.gvas[:4] == b"GVAS"
    assert up.footer_version == 1 and up.md5_ok
    assert b"/Script/DP1Project.SaveData" in up.gvas[:0x1000]


def test_repack_is_byte_exact(sample_raw, key):
    assert container.roundtrip_exact(sample_raw, key)


def test_synthetic_roundtrip(key):
    for n in (0, 1, 15, 16, 17, 4096, 100_003):
        data = os.urandom(n)
        assert container.unpack(container.pack(data, key), key).gvas == data


def test_wrong_key_rejected(sample_raw):
    with pytest.raises(container.ContainerError):
        container.unpack(sample_raw, bytes(32))


def test_tampered_payload_rejected(key):
    packed = bytearray(container.pack(b"GVAS" + bytes(5000), key))
    packed[32] ^= 1
    with pytest.raises(container.ContainerError):
        container.unpack(bytes(packed), key)


def test_bad_size_rejected(key):
    with pytest.raises(container.ContainerError):
        container.unpack(b"\x00" * 17, key)
