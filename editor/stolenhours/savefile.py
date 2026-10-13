"""Parsed save model.

The GVAS body is native serialization of `/Script/DP1Project.SaveData`, not tagged properties, so it is
parsed with the community pattern file (tools/fli_save_editor, commit 124135c). A load is only editable
when both the container and the pattern parser reproduce the original bytes exactly.
"""

from __future__ import annotations

import contextlib
import copy
import hashlib
import io
import struct
import sys
from dataclasses import dataclass
from pathlib import Path

from . import container, paths, safety

if str(paths.COMMUNITY_EDITOR) not in sys.path:
    sys.path.insert(0, str(paths.COMMUNITY_EDITOR))
from fli_sav2json import SaveData as _PatternParser  # noqa: E402

S32_MAX = 2**31 - 1
U32_MAX = 2**32 - 1
U16_MAX = 0xFFFF
# Display limits seen in game UI are UNVERIFIED; these are the field type limits.
MONEY_MAX = S32_MAX
ISLAND_NAME_MAX = 16  # conservative until the in-game limit is checked
STACK_MAX = U16_MAX
LEVEL_MAX = U16_MAX
ITEM_TITLE_MAX = 5  # EItemTitleType Legend
ITEM_QUALITY_MAX = 3  # EItemQualityType Quality_3
EQUIP_STATUS_MAX = 9  # EEquipStatusType_MAX

# From GDSLifeData (ELifeType and starter tool per id); "Brand New" is the in-game name of the NoMakeup life.
LIFE_NAMES = {
    "life0000": "Brand New", "life0001": "Paladin", "life0002": "Mercenary", "life0003": "Hunter",
    "life0004": "Magician", "life0005": "Miner", "life0006": "Woodcutter", "life0007": "Angler",
    "life0008": "Farmer", "life0009": "Cook", "life0010": "Blacksmith", "life0011": "Carpenter",
    "life0012": "Tailor", "life0013": "Alchemist", "life0014": "Artist",
}

EMPTY_IDS = ("", "None", None)


class SaveFileError(RuntimeError):
    pass


def _quiet(fn, *a, **kw):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*a, **kw)


_parser_proto: _PatternParser | None = None


def _new_parser() -> _PatternParser:
    global _parser_proto
    if _parser_proto is None:
        _parser_proto = _PatternParser()
        _quiet(_parser_proto.parsePatternFile, str(paths.PATTERN_FILE))
    p = _PatternParser()
    p.save_structs = _parser_proto.save_structs
    p.save_enums = _parser_proto.save_enums
    p.save_dict = {}
    p.debug_txt = ""
    return p


def load_item_names() -> dict[str, str]:
    names = {}
    try:
        for line in open(paths.ITEM_LIST_FILE, encoding="utf-8"):
            if line.startswith("#") or ":" not in line:
                continue
            k, v = line.rstrip("\n").split(":", 1)
            names[k.strip()] = v.strip()
    except FileNotFoundError:
        pass
    return names


def parse_gvas(gvas: bytes) -> dict:
    p = _new_parser()
    p.save_binary = gvas
    data, end = _quiet(p.binToDict, 0, "SaveFile")
    if end != len(gvas):
        raise SaveFileError(f"pattern parser stopped at {end} of {len(gvas)} bytes")
    return data


_SCALARS = {
    "u8": "<B", "ENum": "<B", "u16": "<H", "u32": "<I", "u64": "<Q", "s8": "<b", "s16": "<h",
    "s32": "<i", "s64": "<q", "float": "<f", "double": "<d",
}
_VECTORS = {
    "FVector4": "<dddd", "Vector4": "<dddd", "FVector3": "<ddd", "Vector3": "<ddd", "FVector": "<ddd",
    "Vector": "<ddd", "FRotator": "<ddd", "Rotator": "<ddd", "IntVector": "<iii", "FVector2D": "<dd",
    "Vector2D": "<dd",
}


def _emit(p: _PatternParser, value, type_name, out: bytearray) -> None:
    """Same encoding as fli_sav2json.packValueToBinData, but appends to one buffer (that one is O(n^2))."""
    subtypes = None
    if isinstance(type_name, tuple):
        type_name, subtypes = type_name
    if type_name in ("TMap", "Map"):
        out += struct.pack("<I", len(value))
        for kv in value:
            _emit(p, kv["key"], subtypes[0], out)
            _emit(p, kv["value"], subtypes[1], out)
    elif type_name in ("TArray", "Array", "TSet", "Set"):
        out += struct.pack("<I", len(value))
        for v in value:
            _emit(p, v, subtypes[0], out)
    elif type_name in _SCALARS:
        out += struct.pack(_SCALARS[type_name], value)
    elif type_name in ("u128", "s128"):
        fmt = "<QQ" if type_name == "u128" else "<qq"
        out += struct.pack(fmt, value & 0xFFFFFFFFFFFFFFFF, value >> 64)
    elif type_name in _VECTORS:
        out += struct.pack(_VECTORS[type_name], *value)
    elif type_name in ("FString", "Str", "FName", "Name"):
        if value is None:
            out += struct.pack("<i", 0)
        elif isinstance(value, dict):
            s = value["content"] + "\0"
            out += struct.pack("<i", -len(s)) + s.encode("utf-16-le")
        else:
            b = value.encode("utf-8") + b"\0"
            out += struct.pack("<i", len(b)) + b
    elif type_name in p.save_structs:
        _emit_struct(p, value, type_name, out)
    elif type_name in p.save_enums:
        _emit(p, value, p.save_enums[type_name]["type"], out)
    else:
        raise SaveFileError(f"unknown type {type_name}")


def _emit_struct(p: _PatternParser, value: dict, struct_name: str, out: bytearray) -> None:
    st = p.save_structs[struct_name]
    if st["super"]:
        _emit_struct(p, value, st["super"], out)
    for param, ptype in st["parameters"].items():
        repeat = 1
        if "[" in param and param.endswith("]"):
            inner = param.split("[")[1][:-1]
            if inner.startswith("0x"):
                repeat = int(inner, 16)
            elif inner.isdigit():
                repeat = int(inner)
        name = param
        for i in range(repeat):
            _emit(p, value[name], ptype, out)
            name = param + f"_{i + 1}"


def serialize(data: dict) -> bytes:
    out = bytearray()
    _emit_struct(_new_parser(), data, "SaveFile", out)
    return bytes(out)


@dataclass
class Item:
    category: str
    index: int
    item_id: str
    stock: int | None


class SaveFile:
    def __init__(self, path: Path, raw: bytes, key: bytes, data: dict):
        self.path = Path(path)
        self.raw = raw
        self.key = key
        self.data = data
        self.dirty = False

    @classmethod
    def load(cls, path: Path | str, key: bytes | None = None) -> "SaveFile":
        path = Path(path)
        raw = path.read_bytes()
        key = key or container.resolve_key(raw)
        gvas = container.unpack(raw, key).gvas
        if container.pack(gvas, key) != raw:
            raise SaveFileError("container repack is not byte-exact; refusing to edit this file")
        data = parse_gvas(gvas)
        if serialize(data) != gvas:
            raise SaveFileError("pattern parser roundtrip is not byte-exact; refusing to edit this file")
        return cls(path, raw, key, data)

    @property
    def sd(self) -> dict:
        return self.data["saveData"]

    # ---- player ----------------------------------------------------------------
    @property
    def avatar(self) -> dict:
        return self.sd["m_CharaStatus"]["m_stAvatarP"][0]

    @property
    def character_name(self) -> str:
        v = self.avatar["m_name"]
        return v["content"] if isinstance(v, dict) else (v or "")

    @character_name.setter
    def character_name(self, name: str) -> None:
        if not name or len(name) > 64:
            raise SaveFileError("name must be 1-64 characters")
        self.avatar["m_name"] = name if name.isascii() else {"content": name, "type": "utf-16-le"}
        self.dirty = True

    @property
    def island_name(self) -> str:
        v = self.sd["m_PlayData"]["islandName"]
        return v["content"] if isinstance(v, dict) else (v or "")

    @island_name.setter
    def island_name(self, name: str) -> None:
        # islandName is the only copy in the save and nothing records a rename (the game has its own rename option);
        # the in-game length limit is UNVERIFIED (check: the in-game island rename keyboard)
        name = str(name)
        if not name.strip() or name != name.strip() or len(name) > ISLAND_NAME_MAX:
            raise SaveFileError(f"island name must be 1-{ISLAND_NAME_MAX} characters, no leading or trailing spaces")
        if any(ord(c) < 32 for c in name):
            raise SaveFileError("island name can't contain control characters")
        self.sd["m_PlayData"]["islandName"] = name if name.isascii() else {"content": name, "type": "utf-16-le"}
        self.dirty = True

    @property
    def money(self) -> int:
        return self.sd["m_PlayData"]["Money"]

    @money.setter
    def money(self, value: int) -> None:
        value = int(value)
        if not 0 <= value <= MONEY_MAX:
            raise SaveFileError(f"money must be 0..{MONEY_MAX}")
        self.sd["m_PlayData"]["Money"] = value
        self.dirty = True

    @property
    def play_time_seconds(self) -> int:
        return self.sd["m_PlayData"]["playTime"]

    @property
    def play_time_max(self) -> int:
        """Time played can't exceed the real time between starting the adventure and the last save."""
        pd = self.sd["m_PlayData"]
        return max(0, min(U32_MAX, (pd["saveDateTime"] - pd["startDateTime"]) // 10_000_000))

    @play_time_seconds.setter
    def play_time_seconds(self, value: int) -> None:
        # playTime (u32 seconds) is the only play-time counter in the save; the in-game clock (envInfo.gameTime)
        # is story-driven world time, not time played, and Steam's own hours live on Steam's servers
        value = int(value)
        if not 0 <= value <= self.play_time_max:
            raise SaveFileError(f"play time must be 0..{self.play_time_max // 3600}h (the real time since the "
                                "adventure started)")
        self.sd["m_PlayData"]["playTime"] = value
        self.dirty = True

    @property
    def current_life(self) -> str:
        return self.avatar["m_lifeId"]

    def lives(self) -> list[dict]:
        a = self.avatar
        lv = {e["key"]: e["value"] for e in a["m_lv"]}
        exp = {e["key"]: e["value"] for e in a["m_exp"]}
        out = []
        for e in a["m_lifeStatus"]:
            k = e["key"]
            out.append({"id": k, "name": LIFE_NAMES.get(k, k), "level": lv.get(k), "exp": exp.get(k),
                        "rank": e["value"]["licenseRank"], "star": e["value"]["star"],
                        "skillMaxPoint": e["value"]["skillMaxPoint"]})
        return out

    def equipped(self, handle: int) -> str | None:
        """Equipment handle -> item id. Layout (from Unholy's save, every equipped slot resolves to the matching
        item): (slot + 1) << 18 | pocket << 12 | slot, pocket = index in inventory_categories()."""
        if not handle:
            return None
        slot, pocket = handle & 0xFFF, (handle >> 12) & 0x3F
        cats = self.inventory_categories()
        if pocket >= len(cats) or (handle >> 18) != slot + 1:
            return None
        items = self.items(cats[pocket])
        return items[slot].item_id if slot < len(items) else None

    def held_items(self) -> dict[str, list[str]]:
        """Per life: weapon/tool and shield item ids; the appearance (view) set wins over the real gear."""
        a = self.avatar
        gear = {e["key"]: e["value"] for e in a["m_abilityEquipInvInfo"]}
        view = {e["key"]: e["value"] for e in a.get("m_viewEquipInvInfo") or []}
        out = {}
        for life, slots in gear.items():
            ids = []
            for slot in ("weapon", "shield"):
                h = (view.get(life, {}).get(slot) or {}).get("handle") or (slots.get(slot) or {}).get("handle")
                if (item := self.equipped(h)) is not None:
                    ids.append(item)
            out[life] = ids
        return out

    def worn_items(self, life: str | None = None) -> dict[str, str]:
        """Equipment slot (Head, tops, bottoms, arm, foot, mantle, glasses, ...) -> item id the life shows, the
        appearance (view) set winning over the real gear. Defaults to the current life."""
        a = self.avatar
        life = life or self.current_life
        gear = next((e["value"] for e in a["m_abilityEquipInvInfo"] if e["key"] == life), {})
        view = next((e["value"] for e in a.get("m_viewEquipInvInfo") or [] if e["key"] == life), {})
        out = {}
        for slot in dict.fromkeys([*gear, *view]):
            h = (view.get(slot) or {}).get("handle") or (gear.get(slot) or {}).get("handle")
            if (item := self.equipped(h)) is not None:
                out[slot] = item
        return out

    def skill_panels(self) -> dict[str, list[int]]:
        """Skill board flag numbers (GDSSkillBoard `flagNo`) that are learned / unlocked."""
        fs = self.sd["m_FlagStatus"]
        return {"learned": [i for i, v in enumerate(fs["skillPanelBitFlag"]) if v],
                "unlocked": [i for i, v in enumerate(fs["skillPanelUnlockBitFlag"]) if v]}

    def set_life(self, life_id: str, level: int | None = None, exp: int | None = None, rank: int | None = None) -> None:
        a = self.avatar
        hit = False
        if level is not None:
            if not 0 <= level <= LEVEL_MAX:
                raise SaveFileError(f"level must be 0..{LEVEL_MAX}")
            for e in a["m_lv"]:
                if e["key"] == life_id:
                    e["value"] = int(level); hit = True
        if exp is not None:
            if not 0 <= exp <= 0xFFFFFFFF:
                raise SaveFileError("exp out of u32 range")
            for e in a["m_exp"]:
                if e["key"] == life_id:
                    e["value"] = int(exp); hit = True
        if rank is not None:
            for e in a["m_lifeStatus"]:
                if e["key"] == life_id:
                    e["value"]["licenseRank"] = int(rank); hit = True
        if not hit:
            raise SaveFileError(f"unknown life id {life_id}")
        self.dirty = True

    # ---- appearance ------------------------------------------------------------
    @property
    def _body(self) -> dict:
        return self.sd["m_AvatarStatus"]["playerP"][0]["BodyParam"]

    def appearance(self) -> dict:
        return dict(self._body)

    def set_appearance(self, field: str, value, allowed=None) -> None:
        """ID fields must be one of `allowed` (the game's own option list for that field, from its
        GDSAvatar*Data tables) when given; otherwise they must keep the current ID's shape.
        """
        body = self._body
        if field not in body:
            raise SaveFileError(f"unknown appearance field {field}; one of {', '.join(body)}")
        cur = body[field]
        if isinstance(cur, int):
            value = int(value)
            if not 0 <= value <= 0xFF:
                raise SaveFileError(f"{field} is a u8 (0..255)")
        elif allowed is not None:
            value = str(value)
            if value not in allowed:
                raise SaveFileError(f"{value} is not a {field} option the game defines")
        else:
            value = str(value)
            if not isinstance(cur, str) or len(value) != len(cur) or value[:-2] != cur[:-2] or not value[-2:].isdigit():
                raise SaveFileError(f"{field} must look like {cur[:-2]}NN (current {cur})")
        body[field] = value
        self.dirty = True

    # ---- inventory -------------------------------------------------------------
    @property
    def inventory(self) -> dict:
        return self.sd["m_InventoryStatus"]

    def inventory_categories(self) -> list[str]:
        return [k for k, v in self.inventory.items()
                if k.startswith("inv") and isinstance(v, list) and v and isinstance(v[0], dict) and "ItemId" in v[0]]

    def items(self, category: str | None = None) -> list[Item]:
        cats = [category] if category else self.inventory_categories()
        out = []
        for c in cats:
            for i, it in enumerate(self.inventory[c]):
                if it["ItemId"] in EMPTY_IDS:
                    continue
                out.append(Item(c, i, it["ItemId"], it.get("stockNum")))
        return out

    def set_stock(self, category: str, index: int, stock: int) -> None:
        it = self.inventory[category][index]
        if it["ItemId"] in EMPTY_IDS:
            raise SaveFileError("slot is empty")
        if "stockNum" not in it:
            raise SaveFileError(f"{category} items are not stackable")
        if not 1 <= stock <= STACK_MAX:
            raise SaveFileError(f"stock must be 1..{STACK_MAX}")
        it["stockNum"] = int(stock)
        self.dirty = True

    def add_item(self, category: str, item_id: str, stock: int = 1, title: int | None = None,
                 bonus: int = 0, skills: list[str] | tuple = (), quality: int = 0) -> int:
        """Clone the last real item in the category into the first trailing empty slot.

        Same approach as the community editor's add_item: copy an existing record, give it a fresh handle
        and the next getOrder. Equipment starts from the blank record of the free slot instead, so it doesn't
        inherit the template's grade, bonus stat, skills or equipped marks; `title` (1-5), `quality` (0-3),
        `bonus` (EEquipStatusType) and up to three `skills` set what it comes out as. Returns the slot index.
        """
        inv = self.inventory[category]
        handles, last_item, first_free = [], -1, -1
        for i, it in enumerate(inv):
            if it["ItemId"] in EMPTY_IDS:
                if first_free < 0:
                    first_free = i
                continue
            first_free = -1
            last_item = i
            handles.append(it["Handle"]["handle"])
        if last_item < 0:
            raise SaveFileError(f"{category} has no item to use as a template; get one in game first")
        if first_free < 0:
            raise SaveFileError(f"{category} is full")
        if "stockNum" in inv[last_item] and any(it["ItemId"] == item_id for it in inv):
            raise SaveFileError(f"{item_id} is already in {category}; change its stock instead")
        equip = "itemTitle" in inv[last_item]
        new = copy.deepcopy(inv[first_free] if equip else inv[last_item])
        new["ItemId"] = item_id
        if equip:
            skills = [s for s in skills if s and s != "None"]
            if len(skills) > len(new["grantSkillId"]) or len(set(skills)) != len(skills):
                raise SaveFileError(f"up to {len(new['grantSkillId'])} different skills")
            if not 0 <= int(bonus) < EQUIP_STATUS_MAX:
                raise SaveFileError(f"bonus stat type must be 0..{EQUIP_STATUS_MAX - 1}")
            new["itemTitle"] = inv[last_item]["itemTitle"] if title is None else int(title)
            if not 0 <= new["itemTitle"] <= ITEM_TITLE_MAX:
                raise SaveFileError(f"grade must be 1..{ITEM_TITLE_MAX}")
            if not 0 <= int(quality) <= ITEM_QUALITY_MAX:
                raise SaveFileError(f"quality must be 0..{ITEM_QUALITY_MAX}")
            new["Quality"] = int(quality)
            new["addEquipStatus"] = [{"Type": int(bonus), "Value": 0}]
            new["grantSkillId"] = skills + ["None"] * (len(new["grantSkillId"]) - len(skills))
        elif title is not None or bonus or skills or quality:
            raise SaveFileError(f"{category} items have no grade, quality, bonus stat or skills")
        handle = None
        for h in reversed(handles):
            cand = h + (4 << 16) + 1
            if cand not in handles:
                handle = cand
                break
        if handle is None:
            raise SaveFileError("could not allocate an item handle")
        new["Handle"]["handle"] = handle
        self.inventory["getOrderCount"] += 1
        new["getOrder"] = self.inventory["getOrderCount"]
        if "stockNum" in new:
            if not 1 <= stock <= STACK_MAX:
                raise SaveFileError(f"stock must be 1..{STACK_MAX}")
            new["stockNum"] = int(stock)
        inv[first_free] = new
        self.dirty = True
        return first_free

    # ---- output ----------------------------------------------------------------
    def to_bin(self) -> bytes:
        gvas = serialize(self.data)
        out = container.pack(gvas, self.key)
        if container.unpack(out, self.key).gvas != gvas or parse_gvas(gvas) != self.data:
            raise SaveFileError("packed output failed verification")
        return out

    def describe(self) -> dict:
        """Who and when, for picking between copies of a save."""
        from .records import _save_id, _ticks
        pd = self.sd["m_PlayData"]
        return {"path": str(self.path), "name": self.character_name, "island": self.island_name, "money": self.money,
                "play_time": self.play_time_seconds, "started": _ticks(pd["startDateTime"]),
                "saved": _ticks(pd["saveDateTime"]), "adventure": _save_id(self),
                "sha256": hashlib.sha256(self.raw).hexdigest().upper()}

    def write(self, target: Path | None = None) -> dict:
        """Write to the save (default: the file it was loaded from). Game must be closed; backup first."""
        target = Path(target or self.path)
        safety.require_game_closed()
        if target == self.path and target.exists() and target.read_bytes() != self.raw:
            raise SaveFileError("the save changed on disk since it was loaded (the game saved?). "
                                "Reload it and redo the edit so newer progress is not overwritten.")
        out = self.to_bin()
        backup = safety.backup(target, "before-edit") if target.exists() else None
        safety.atomic_write(target, out)
        if target.read_bytes() != out:
            raise SaveFileError("written file does not match the packed output")
        self.raw = out
        self.dirty = False
        return {"target": str(target), "backup": str(backup) if backup else None,
                "sha256": safety.sha256_file(target)}


def restore_save(src: Path, target: Path) -> dict:
    """Put a copy of a save back in place of `target`, byte for byte. The copy must open and repack byte-exact
    (so a damaged or foreign file is refused before anything is touched); the current save is backed up first."""
    src, target = Path(src), Path(target)
    if src.resolve() == target.resolve():
        raise SaveFileError("that is the save itself; pick a backup copy")
    copy_ = SaveFile.load(src)
    safety.require_game_closed()
    before = safety.backup(target, "before-restore") if target.exists() else None
    safety.atomic_write(target, copy_.raw)
    if target.read_bytes() != copy_.raw:
        raise SaveFileError("restored file does not match the backup copy")
    return {"target": str(target), "from": str(src), "backup": str(before) if before else None,
            "sha256": safety.sha256_file(target)}
