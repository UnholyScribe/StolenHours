import sys
from pathlib import Path

import pytest

EDITOR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EDITOR))

from stolenhours import container, paths  # noqa: E402

SAMPLE_SAVE = paths.PROJECT_ROOT / "backups" / "saves" / "2026-10-11_initial" / paths.SAVE_FILE_NAME
SAMPLE_SHA256 = "D2CAF0A8772C2F83D9ABA868372340E844F775CCDF2C129CF73BAD5ABDCDF2A3"


@pytest.fixture(scope="session")
def key():
    if not paths.KEY_FILE.exists():
        pytest.skip("research/private/aes_key.hex missing")
    return container.load_key()


@pytest.fixture(scope="session")
def sample_raw():
    if not SAMPLE_SAVE.exists():
        pytest.skip("sample save backup missing")
    return SAMPLE_SAVE.read_bytes()
