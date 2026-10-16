"""Buddies / companions: follower, party, and the friend roster.

Save (pattern + Unholy's save):
- `m_PartyStatus.m_followerCharaInfo.m_followerId` = Name (Trip = `chr100400` on this save)
- `m_PartyStatus.m_partyCharaInfoList` = up to 4 slots; leader handle 65536 = avatar
- `m_PartyStatus.m_supporterCharaInfo` / `m_instantCharaInfo` = handles into chara status arrays
- `m_CharaStatus.m_stFriendP` = 64 `NpcCharaStatusP` slots (`m_paramId` Name, friendship, level, …)
- Library characters (category 3) are the named buddies; InstantChara rows are Ginormosia guest helpers

UNVERIFIED: filling an empty friend slot and loading in game (need a save that already has friends to
diff handle / equip defaults). Follower Id swap is a single Name field and is the safest first edit.
"""
from __future__ import annotations

import json
from pathlib import Path

from . import paths, uiassets
from .savefile import SaveFile, SaveFileError

GAME_DATA = paths.EXTRACT_DIR / "Game" / "Content" / "GameData"
DATA_FILE = paths.UI_ASSET_DIR / "companions" / "companions.json"
DATA_PATTERN = (
    r"^Game/Content/GameData/(Chara/GDS(CharaParameter|CharaText_Noun|InstantCharaData)|"
    r"Activity/GDSLibraryListData|Limit/GDSFollowerLimitConfig|Friend/GDSFriendshipInfoSetting)\.uasset$"
)
FRIEND_SLOTS = 64
# Avatar = 0x10000 (65536). Real friends on Unholy's Deck-synced save: Kunugi 0x11000, Duglas 0x11001.
FRIEND_HANDLE_BASE = 0x11000  # 69632
AVATAR_HANDLE = 0x10000


def extract(force: bool = False) -> None:
    need = [
        GAME_DATA / "Chara" / "GDSCharaParameter.json",
        GAME_DATA / "Chara" / "GDSCharaText_Noun.json",
        GAME_DATA / "Activity" / "GDSLibraryListData.json",
    ]
    if force or not all(p.exists() for p in need):
        uiassets._run_extractor("json", DATA_PATTERN)


def _rows(rel: str) -> dict:
    props = json.loads((GAME_DATA / rel).read_text(encoding="utf-8"))[0]["Properties"]
    return {(r["Key"]["Name"] if isinstance(r["Key"], dict) else r["Key"]): r["Value"] for r in props["m_dataMap"]}


def _nouns() -> dict[str, str]:
    out = {}
    for k, v in _rows("Chara/GDSCharaText_Noun.json").items():
        if not k.startswith("name_"):
            continue
        info = (v.get("textInfo") or [{}])[0]
        out[k[5:]] = (info.get("nounSingularForm_en") or info.get("text_en") or "").strip()
    return out


def build(out: Path | None = None, log=print) -> dict:
    out = out or DATA_FILE.parent
    if not (GAME_DATA / "Chara" / "GDSCharaParameter.json").exists():
        log("companions: no exported data; run extract first")
        return {"missing": ["companions data"]}
    names = _nouns()
    params = _rows("Chara/GDSCharaParameter.json")
    by_chara: dict[str, str] = {}
    for pid, v in params.items():
        cid = v.get("charaID")
        if not cid or cid in by_chara:
            continue
        # Prefer the base para_chrXXXX00 row (named buddies) over instant para_chrXXXX20 variants
        by_chara[cid] = pid

    library = []
    try:
        for lid, v in _rows("Activity/GDSLibraryListData.json").items():
            if v.get("Category") != 3:
                continue
            cid = v["ObjecyID"]
            library.append({"id": cid, "param": by_chara.get(cid) or f"para_{cid}",
                            "name": names.get(cid) or cid, "library": lid})
    except FileNotFoundError:
        pass

    # Named NPCs from chara params that have an English noun (covers Trip etc. outside library)
    seen = {c["id"] for c in library}
    extras = []
    for cid, pid in by_chara.items():
        if cid in seen or not str(cid).startswith("chr"):
            continue
        nm = names.get(cid)
        if not nm:
            continue
        extras.append({"id": cid, "param": pid, "name": nm, "library": None})
    extras.sort(key=lambda c: c["name"].lower())
    library.sort(key=lambda c: c["name"].lower())

    followers = []
    try:
        for cid, v in _rows("Limit/GDSFollowerLimitConfig.json").items():
            followers.append({"id": v.get("charaID") or cid, "name": names.get(v.get("charaID") or cid) or cid})
    except FileNotFoundError:
        followers = [{"id": "chr100400", "name": names.get("chr100400") or "Trip"}]

    ranks = []
    try:
        for k, v in _rows("Friend/GDSFriendshipInfoSetting.json").items():
            ranks.append({"id": k, "step": v.get("step", 0), "friendship": v.get("friendship", 0)})
        ranks.sort(key=lambda r: r["step"])
    except FileNotFoundError:
        ranks = [{"id": f"Rank_{i}", "step": i, "friendship": (i - 1) * 100} for i in range(1, 7)]

    instant = []
    try:
        for pid, v in _rows("Chara/GDSInstantCharaData.json").items():
            base = v.get("baseCharaParamID") or pid
            cid = params.get(pid, {}).get("charaID") or params.get(base, {}).get("charaID") or pid
            instant.append({"id": cid, "param": pid, "name": names.get(cid) or cid})
    except FileNotFoundError:
        pass

    data = {"buddies": library, "extras": extras, "followers": followers, "ranks": ranks, "instant": instant}
    out.mkdir(parents=True, exist_ok=True)
    (out / "companions.json").write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")),
                                         encoding="utf-8")
    log(f"companions: {len(library)} library buddies, {len(extras)} named extras, "
        f"{len(followers)} followers -> {out}")
    return {"buddies": len(library), "extras": len(extras)}


def _empty_friend(slot: dict) -> bool:
    return slot.get("m_paramId") in (None, "None", "", 0)


class Companions:
    def __init__(self, data: dict):
        self.buddies = {b["id"]: b for b in data["buddies"]}
        self.extras = {b["id"]: b for b in data.get("extras") or []}
        self.all = {**self.extras, **self.buddies}
        self.followers = data.get("followers") or []
        self.ranks = data.get("ranks") or []
        self.instant = data.get("instant") or []

    @classmethod
    def load(cls, path: Path | None = None) -> "Companions":
        p = path or DATA_FILE
        if not p.exists():
            raise FileNotFoundError(p)
        return cls(json.loads(p.read_text(encoding="utf-8")))

    def name_of(self, cid: str) -> str:
        if cid in self.all:
            return self.all[cid]["name"]
        for f in self.followers:
            if f["id"] == cid:
                return f["name"]
        return cid

    def state(self, sf: SaveFile) -> dict:
        friends = []
        for i, slot in enumerate(sf.sd["m_CharaStatus"]["m_stFriendP"]):
            if _empty_friend(slot):
                continue
            pid = slot["m_paramId"]
            cid = pid[5:] if isinstance(pid, str) and pid.startswith("para_") else pid
            h = (slot.get("m_charaStHdl") or {}).get("handle") or 0
            friends.append({
                "slot": i, "id": cid, "param": pid, "name": self.name_of(cid),
                "level": int(slot.get("m_lv") or 0), "friendship": int(slot.get("m_friendship") or 0),
                "handle": h, "talk": int(slot.get("m_talkCount") or 0),
                "quests": int(slot.get("m_questCount") or 0),
            })
        by_h = {f["handle"]: f for f in friends}
        party = []
        for row in sf.sd["m_PartyStatus"]["m_partyCharaInfoList"]:
            h = (row.get("m_charaStHdl") or {}).get("handle") or 0
            party.append({
                "handle": h, "type": row.get("m_partyType", 0), "idx": row.get("m_partyIdx", 0),
                "leader": bool(row.get("m_isLeader")),
                "who": ("You" if h == AVATAR_HANDLE else
                        (by_h[h]["name"] if h in by_h else (f"#{h}" if h else "Empty"))),
            })
        residents = []
        for info in sf.sd["m_NpcStatus"].get("CraftAreaFriendNpcInfo") or []:
            h = (info.get("CharaStatusHandle") or {}).get("handle") or 0
            if not h:
                continue
            f = by_h.get(h)
            residents.append({
                "handle": h, "name": f["name"] if f else f"#{h}", "id": f["id"] if f else None,
                "map": info.get("mapId"), "living": bool((info.get("CraftAreaInhabitantHandle") or {}).get("handle")),
            })
        fid = sf.sd["m_PartyStatus"]["m_followerCharaInfo"].get("m_followerId")
        if fid in (None, "None", ""):
            fid = None
        return {
            "buddies": list(self.buddies.values()),
            "extras": list(self.extras.values()),
            "followers": self.followers,
            "ranks": self.ranks,
            "instant": self.instant,
            "friends": friends,
            "party": party,
            "residents": residents,
            "follower": {"id": fid, "name": self.name_of(fid) if fid else None},
            "supporter": (sf.sd["m_PartyStatus"]["m_supporterCharaInfo"].get("m_charaStatusHandle") or {}).get("handle") or 0,
            "instantHandle": (sf.sd["m_PartyStatus"]["m_instantCharaInfo"].get("m_charaStatusHandle") or {}).get("handle") or 0,
            "slotsFree": FRIEND_SLOTS - len(friends),
            "instantJoins": sf.sd["m_PlayData"]["playCountData"].get("instantCharaJoinNum", 0),
        }

    def set_follower(self, sf: SaveFile, chara_id: str | None) -> str:
        """Set or clear the follower (Trip). `None` / '' / 'None' clears."""
        info = sf.sd["m_PartyStatus"]["m_followerCharaInfo"]
        if not chara_id or chara_id in ("None", "none", "clear"):
            info["m_followerId"] = "None"
            sf.dirty = True
            return "cleared"
        known = {f["id"] for f in self.followers} | set(self.all)
        if chara_id not in known and not chara_id.startswith("chr"):
            raise SaveFileError(f"unknown follower {chara_id}")
        info["m_followerId"] = chara_id
        sf.dirty = True
        return chara_id

    def add_friend(self, sf: SaveFile, chara_id: str, friendship: int = 0, level: int = 1,
                   to_party: bool = True) -> dict:
        """Fill the first empty friend slot.

        Handle layout verified on Unholy's Deck-synced save (Kunugi @ 0x11000, Duglas @ 0x11001).
        Gear / island house / CraftAreaFriendNpc wiring still UNVERIFIED for newly added buddies.
        """
        meta = self.all.get(chara_id)
        if not meta:
            raise SaveFileError(f"unknown buddy {chara_id}")
        friends = sf.sd["m_CharaStatus"]["m_stFriendP"]
        for slot in friends:
            if not _empty_friend(slot) and (
                    slot["m_paramId"] == meta["param"] or slot["m_paramId"] == chara_id
                    or slot["m_paramId"] == f"para_{chara_id}"):
                raise SaveFileError(f"{meta['name']} is already in your buddy list")
        for i, slot in enumerate(friends):
            if not _empty_friend(slot):
                continue
            h = FRIEND_HANDLE_BASE + i
            hp = max(1, 100 + 20 * max(1, int(level)))
            slot["m_paramId"] = meta["param"]
            slot["m_charaStHdl"] = {"handle": h}
            slot["m_lv"] = max(1, int(level))
            slot["m_friendship"] = max(0, min(500, int(friendship)))
            slot["m_exp"] = slot["m_friendship"]
            slot["m_nowHp"] = hp
            slot["m_nowSp"] = 100
            slot["rateMaxHp"] = hp
            slot["rateNowHp"] = hp
            slot["rateMaxSp"] = 100
            slot["rateNowSp"] = 100
            slot["m_addOrder"] = i + 1
            slot["m_nowRecoverySPTime"] = 1.0
            slot["m_lifeStatus"] = {"licenseRank": 1, "star": 0, "skillMaxPoint": 0}
            slot["m_isInstantChara"] = 0
            if to_party:
                self._seat_in_party(sf, h)
            sf.dirty = True
            return {"slot": i, "id": chara_id, "param": meta["param"], "name": meta["name"],
                    "level": slot["m_lv"], "friendship": slot["m_friendship"], "handle": h}
        raise SaveFileError("no free buddy slots (64)")

    def _seat_in_party(self, sf: SaveFile, handle: int) -> None:
        party = sf.sd["m_PartyStatus"]["m_partyCharaInfoList"]
        used = {(p.get("m_partyIdx") if (p.get("m_charaStHdl") or {}).get("handle") else None) for p in party}
        for idx in (1, 2, 3):
            if idx in used:
                continue
            for p in party:
                if (p.get("m_charaStHdl") or {}).get("handle"):
                    continue
                p["m_charaStHdl"] = {"handle": handle}
                p["m_partyType"] = 0
                p["m_partyIdx"] = idx
                p["m_isLeader"] = 0
                return

    def remove_friend(self, sf: SaveFile, chara_id: str | None = None, slot: int | None = None) -> int:
        friends = sf.sd["m_CharaStatus"]["m_stFriendP"]
        n = 0
        for i, row in enumerate(friends):
            if _empty_friend(row):
                continue
            pid = row["m_paramId"]
            cid = pid[5:] if isinstance(pid, str) and pid.startswith("para_") else pid
            if slot is not None and i != slot:
                continue
            if chara_id is not None and cid != chara_id and pid != chara_id and pid != f"para_{chara_id}":
                continue
            h_gone = (row.get("m_charaStHdl") or {}).get("handle") or 0
            row["m_paramId"] = "None"
            row["m_charaStHdl"] = {"handle": 0}
            row["m_lv"] = 0
            row["m_friendship"] = 0
            row["m_exp"] = 0
            row["m_nowHp"] = 0
            row["m_nowSp"] = 0
            row["rateMaxHp"] = 0
            row["rateNowHp"] = 0
            row["rateMaxSp"] = 0
            row["rateNowSp"] = 0
            row["m_addOrder"] = 0
            for p in sf.sd["m_PartyStatus"]["m_partyCharaInfoList"]:
                if (p.get("m_charaStHdl") or {}).get("handle") == h_gone:
                    p["m_charaStHdl"] = {"handle": 0}
                    p["m_partyIdx"] = 4
                    p["m_isLeader"] = 0
            # clear island friend-npc row that pointed at this handle
            for info in sf.sd["m_NpcStatus"].get("CraftAreaFriendNpcInfo") or []:
                if (info.get("CharaStatusHandle") or {}).get("handle") == h_gone:
                    info["CharaStatusHandle"] = {"handle": 0}
                    info["CraftAreaInhabitantHandle"] = {"handle": 0}
            for info in sf.sd["m_NpcStatus"].get("CraftAreaInhabitantInfo") or []:
                if (info.get("CharaStatusHandle") or {}).get("handle") == h_gone:
                    info["CharaStatusHandle"] = {"handle": 0}
            n += 1
            if slot is not None or chara_id is not None:
                break
        if n:
            sf.dirty = True
        return n
