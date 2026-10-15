import copy

import pytest

from conftest import SAMPLE_SAVE
from stolenhours import companions, container, savefile


@pytest.fixture(scope="module")
def bud():
    if not companions.DATA_FILE.exists():
        pytest.skip("companions.json not built")
    return companions.Companions.load()


@pytest.fixture(scope="module")
def loaded(key, sample_raw):
    return savefile.SaveFile.load(SAMPLE_SAVE, key)


def fresh(loaded):
    return savefile.SaveFile(loaded.path, loaded.raw, loaded.key, copy.deepcopy(loaded.data))


def reparse(sf):
    return savefile.parse_gvas(container.unpack(sf.to_bin(), sf.key).gvas)["saveData"]


def test_catalog(bud):
    assert len(bud.buddies) >= 40
    assert "chr000100" in bud.buddies and bud.buddies["chr000100"]["name"] == "Laura"
    assert any(f["id"] == "chr100400" for f in bud.followers)


def test_follower_roundtrip(bud, loaded):
    sf = fresh(loaded)
    assert bud.set_follower(sf, "chr100400") == "chr100400" and sf.dirty
    assert bud.set_follower(sf, None) == "cleared"
    sd = reparse(sf)
    assert sd["m_PartyStatus"]["m_followerCharaInfo"]["m_followerId"] == "None"
    bud.set_follower(sf, "chr100400")
    sd = reparse(sf)
    assert sd["m_PartyStatus"]["m_followerCharaInfo"]["m_followerId"] == "chr100400"


def test_add_remove_friend_roundtrip(bud, loaded):
    sf = fresh(loaded)
    before = len(bud.state(sf)["friends"])
    row = bud.add_friend(sf, "chr000100", friendship=100, level=5)
    assert row["name"] == "Laura" and sf.dirty
    assert len(bud.state(sf)["friends"]) == before + 1
    with pytest.raises(savefile.SaveFileError):
        bud.add_friend(sf, "chr000100")
    assert bud.remove_friend(sf, chara_id="chr000100") == 1
    sd = reparse(sf)
    friends = sd["m_CharaStatus"]["m_stFriendP"]
    assert all(f.get("m_paramId") in (None, "None", "", 0) or f["m_paramId"] != row["param"]
               for f in friends)
