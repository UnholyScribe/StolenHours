"""Skill boards: dump the game's per-life boards (layout, costs, skills, texts, art) for the editor.

Game data (GDSSkillBoard etc.):
- one board per life (`sb_lifeNNNN`); each panel has a hex-grid cell (indexX/indexY), a parent panel, an SP cost
  (`skillPoint`), a save flag number (`flagNo`) and a GDSSkillPanel id whose `contentID` is a GDSSkillData skill.
- panel conditions and skill parameters are stored in the table's `m_autoBin`: 16-byte header, then each argument
  at 16 + m_offset is a tag byte and an int32 (tag 0x34 = offset into `m_autoStr`, 0x32 = integer).
Save (verified on Unholy's save: Miner 11 learned panels, 51 SP = `skillMaxPoint`):
- `m_FlagStatus.skillPanelBitFlag[flagNo]` = 1 when learned; `skillPanelUnlockBitFlag[flagNo]` = 1 once a
  conditional panel has been unlocked.
"""
from __future__ import annotations

import json
import shutil
import struct
from pathlib import Path

from . import paths, uiassets

SKILL_DATA = paths.EXTRACT_DIR / "Game" / "Content" / "GameData" / "Skill"
LEVEL_TABLE = paths.EXTRACT_DIR / "Game" / "Content" / "GameData" / "Chara" / "GDSCharaLevelConfig.json"
ART_DIRS = [paths.EXTRACT_DIR / "Game" / "Content" / "Graphics" / "2D" / "UI" / "SkillBoard",
            paths.EXTRACT_DIR / "Game" / "Content" / "Graphics" / "2D" / "UI" / "Icon" / "SkillBoard"]
DATA_PATTERN = r"^Game/Content/GameData/(Skill/GDS\w+|Chara/GDSCharaLevelConfig)\.uasset$"
ART_PATTERN = r"^Game/Content/Graphics/2D/UI/(SkillBoard/Tex|Icon/SkillBoard)/.*\.uasset$"
ICON_KIND = {1: "status", 2: "technique", 3: "unique"}


def extract(force: bool = False) -> None:
    if force or not (SKILL_DATA / "GDSSkillBoard.json").exists() or not LEVEL_TABLE.exists():
        uiassets._run_extractor("json", DATA_PATTERN)
    if force or not any(p.exists() and any(p.rglob("*.png")) for p in ART_DIRS):
        uiassets._run_extractor("export", ART_PATTERN)


class _Table:
    def __init__(self, name: str):
        props = json.loads((SKILL_DATA / f"{name}.json").read_text(encoding="utf-8"))[0]["Properties"]
        self.rows = {self._key(r["Key"]): r["Value"] for r in props["m_dataMap"]}
        self.bin = bytes(props.get("m_autoBin") or [])
        self.str = props.get("m_autoStr") or ""

    @staticmethod
    def _key(k):
        return k["Name"] if isinstance(k, dict) else k

    def arg(self, a: dict):
        at = 16 + a["m_offset"]
        tag, val = self.bin[at], struct.unpack_from("<i", self.bin, at + 1)[0]
        if tag == 0x34:
            return self.str[val:val + a["m_dataSize"]]
        if tag == 0x32:
            return val
        return {"tag": tag, "raw": val}


def _conditions(table: _Table, conds: list) -> list:
    out = []
    for c in conds:
        args = [table.arg(a) for a in c["arg"]]
        cmd = c["Cmd"].removeprefix("CondCmd_")
        if cmd == "LicenseRank_Over":
            out.append({"type": "rank", "life": args[1], "rank": args[2]})
        elif cmd == "GainedSkillPanelNum_Greater":
            out.append({"type": "panels", "board": args[0], "count": args[1]})
        else:
            out.append({"type": cmd, "args": args})
    return out


def build(out: Path | None = None, log=print) -> dict:
    out = out or paths.UI_ASSET_DIR / "skillboard"
    if not (SKILL_DATA / "GDSSkillBoard.json").exists():
        log("skill boards: no exported skill data; run extract first")
        return {"missing": ["skill data"]}
    boards, panels, skills = _Table("GDSSkillBoard"), _Table("GDSSkillPanel"), _Table("GDSSkillData")
    noun = {k: v["textInfo"][0].get("nounSingularForm_en") for k, v in _Table("GDSSkillText_Noun").rows.items()}
    text = {k: v["textInfo"][0].get("text_en") for k, v in _Table("GDSSkillText").rows.items()}

    used: dict[str, dict] = {}
    result = {}
    for bid, b in boards.rows.items():
        cells = []
        for p in b["skillPanelInfoList"]:
            pan = panels.rows.get(p["skillPanelId"], {})
            sid = pan.get("contentID") or "None"
            cell = {"no": p["No"], "flag": p["flagNo"], "cost": p["skillPoint"], "x": p["indexX"], "y": p["indexY"],
                    "parent": p["parentNo"], "blank": bool(pan.get("isBlankPanel", True)),
                    "special": bool(pan.get("isSpecial")), "lifeLimit": p["isLifelimit"],
                    "conds": _conditions(panels, pan.get("Condition") or [])}
            if sid != "None":
                cell["skill"] = sid
                if sid not in used and sid in skills.rows:
                    s = skills.rows[sid]
                    used[sid] = {
                        "kind": ICON_KIND.get(s["skillIconType"], str(s["skillIconType"])),
                        "name": noun.get(s["nameTextID"]) or text.get(s["nameTextID"]) or sid,
                        "desc": text.get(s["dascTextId"]) or "",
                        "params": [skills.arg(a) for a in s["Params"]["prm"] if a["m_dataSize"]],
                    }
            cells.append(cell)
        result[b["lifeId"]] = {"id": bid, "start": [b["startIndexX"], b["startIndexY"]], "panels": cells}

    # SP gained on reaching each level (index = level - 1); the running total is the save's `skillMaxPoint`
    level_sp = []
    if LEVEL_TABLE.exists():
        rows = json.loads(LEVEL_TABLE.read_text(encoding="utf-8"))[0]["Properties"]["m_dataMap"]
        level_sp = [r["Value"]["skillPoint"] for r in sorted(rows, key=lambda r: r["Value"]["lv"])]

    out.mkdir(parents=True, exist_ok=True)
    (out / "boards.json").write_text(json.dumps({"boards": result, "skills": used, "levelSp": level_sp},
                                                ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    art = 0
    for d in ART_DIRS:
        for png in d.rglob("*.png") if d.exists() else []:
            shutil.copy2(png, out / png.name)
            art += 1
    n = sum(len(b["panels"]) for b in result.values())
    log(f"skill boards: {len(result)} boards, {n} panels, {len(used)} skills, {art} images -> {out}")
    return {"boards": len(result), "panels": n, "skills": len(used), "images": art}
