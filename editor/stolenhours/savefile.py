"""Parsed save model.

The GVAS body is native serialization of `/Script/DP1Project.SaveData`, not tagged properties, so it is
parsed with the community pattern file (tools/fli_save_editor, commit 124135c). A load is only editable
when both the container and the pattern parser reproduce the original bytes exactly.
"""

from __future__ import annotations

import contextlib
import copy
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
U16_MAX = 0xFFFF
# Display limits seen in game UI are UNVERIFIED; these are the field type limits.
MONEY_MAX = S32_MAX
STACK_MAX = U16_MAX
LEVEL_MAX = U16_MAX

# life0001-0013 follow the EMapIconType Master* order in the pattern file; life0000 and life0014 are guesses.
LIFE_NAMES_UNVERIFIED = {
    "life0000": "(base / overall?)", "life0001": "Paladin", "life0002": "Mercenary", "life0003": "Hunter",
    "life0004": "Magician", "life0005": "Miner", "life0006": "Woodcutter", "life0007": "Angler",
    "life0008": "Farmer", "life0009": "Cook", "life0010": "Blacksmith", "life0011": "Carpenter",
    "life0012": "Tailor", "life0013": "Alchemist", "life0014": "Artist?",
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
        key = key or container.load_key()
        raw = path.read_bytes()
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
    def current_life(self) -> str:
        return self.avatar["m_lifeId"]

    def lives(self) -> list[dict]:
        a = self.avatar
        lv = {e["key"]: e["value"] for e in a["m_lv"]}
        exp = {e["key"]: e["value"] for e in a["m_exp"]}
        out = []
        for e in a["m_lifeStatus"]:
            k = e["key"]
            out.append({"id": k, "name": LIFE_NAMES_UNVERIFIED.get(k, k), "level": lv.get(k), "exp": exp.get(k),
                        "rank": e["value"]["licenseRank"], "star": e["value"]["star"],
                        "skillMaxPoint": e["value"]["skillMaxPoint"]})
        return out

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

    def add_item(self, category: str, item_id: str, stock: int = 1) -> int:
        """Clone the last real item in the category into the first trailing empty slot.

        Same approach as the community editor's add_item: copy an existing record, give it a fresh handle
        and the next getOrder. Returns the slot index.
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
        new = copy.deepcopy(inv[last_item])
        new["ItemId"] = item_id
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

    def write(self, target: Path | None = None) -> dict:
        """Write to the save (default: the file it was loaded from). Game must be closed; backup first."""
        target = Path(target or self.path)
        safety.require_game_closed()
        out = self.to_bin()
        backup = safety.backup(target, "before-edit") if target.exists() else None
        safety.atomic_write(target, out)
        if target.read_bytes() != out:
            raise SaveFileError("written file does not match the packed output")
        self.raw = out
        self.dirty = False
        return {"target": str(target), "backup": str(backup) if backup else None,
                "sha256": safety.sha256_file(target)}
