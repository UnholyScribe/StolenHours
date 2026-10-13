import os
import types

from stolenhours import gear, live


class FakeBridge:
    def __init__(self, alive=True, sets=None, index=0):
        self.alive, self.sets, self.index = alive, sets or [], index

    def mod_alive(self):
        return self.alive

    def get(self, target, prop):
        assert target == gear.PLAYER
        if prop == "EquipSetCurrentIndex":
            return live.Reply(True, str(self.index))
        i, slot = prop.removeprefix("ViewEquipModelInfoSet[").split("].")
        return live.Reply(True, self.sets[int(i)].get(slot, "None"))


def fake_save(tmp_path, mtime):
    p = tmp_path / "save.bin"
    p.write_bytes(b"x")
    os.utime(p, (mtime, mtime))
    return types.SimpleNamespace(path=p, worn_items=lambda: {"tops": "iam01004380"})


def test_live_reading_wins_and_is_cached(tmp_path):
    sets = [{"tops": "mdl_wea006801_00"}, {"tops": "MDL_WEA007201_00", "Head": "None"}]
    g = gear.MainGear(FakeBridge(sets=sets, index=1), tmp_path / "last.json")
    r = g.get(fake_save(tmp_path, 1))
    assert r["source"] == "live" and r["models"] == {"tops": "mdl_wea007201_00"}
    assert (tmp_path / "last.json").exists()


def test_last_live_reading_used_while_newer_than_the_save(tmp_path):
    cache = tmp_path / "last.json"
    gear.MainGear(FakeBridge(sets=[{"tops": "mdl_wea006801_00"}]), cache).get()
    offline = gear.MainGear(FakeBridge(alive=False), cache)
    assert offline.get(fake_save(tmp_path, 1))["source"] == "last live"
    r = offline.get(fake_save(tmp_path, 4_000_000_000))
    assert r["source"] == "save" and r["items"] == {"tops": "iam01004380"}
