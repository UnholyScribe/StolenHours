"""Skill board editing on top of the dumped boards (`skillboard.build` -> boards.json) and the save's flags.

Save side (verified on Unholy's save):
- learned panel: `m_FlagStatus.skillPanelBitFlag[flagNo]` = 1; nothing else in the save names skills.
- `skillMaxPoint` (per life) = SP earned = running total of GDSCharaLevelConfig `skillPoint` up to the life's level
  (Brand New lv 11 -> 43, Miner lv 13 -> 51); free SP = skillMaxPoint - costs of the learned panels.
- `skillPanelUnlockBitFlag[flagNo]` = 1 on conditional panels whose parent is learned and whose condition holds
  (all 5 on Unholy's Miner board fit; none that fail it are set).
- blank panels (`isBlankPanel`, cost 0) are not counted: Miner shows "11/64" = 73 panels - start - 8 blanks.
UNVERIFIED: whether "GainedSkillPanelNum_Greater n" means >= n or > n (no panel on the save sits at the boundary;
treated as >=, like LicenseRank_Over which is >= on the save: rank 3 unlocks "rank 3" panels).
UNVERIFIED: blank panels are treated as pass-through connectors whose flag is never set (none on the save has a
learned panel behind it; check: learn one in game, then diff skillPanelBitFlag at the blank's flagNo).
"""
from __future__ import annotations

import json
from pathlib import Path

from . import paths
from .savefile import SaveFile, SaveFileError

BOARDS_FILE = paths.UI_ASSET_DIR / "skillboard" / "boards.json"


class SkillTree:
    def __init__(self, data: dict):
        self.boards: dict[str, dict] = data["boards"]
        self.skills: dict[str, dict] = data["skills"]
        self.level_sp: list[int] = data.get("levelSp") or []
        self.board_life = {b["id"]: life for life, b in self.boards.items()}

    @classmethod
    def load(cls, path: Path = BOARDS_FILE) -> "SkillTree":
        return cls(json.loads(Path(path).read_text(encoding="utf-8")))

    # ---- tables ----------------------------------------------------------------
    def sp_for_level(self, level: int) -> int:
        return sum(self.level_sp[:max(0, int(level))])

    def board(self, life: str) -> dict:
        if life not in self.boards:
            raise SaveFileError(f"{life} has no skill board")
        return self.boards[life]

    def _panels(self, life: str) -> dict[int, dict]:
        return {p["no"]: p for p in self.board(life)["panels"]}

    @staticmethod
    def _root(panels: dict[int, dict]) -> int:
        return next(no for no, p in panels.items() if p["parent"] < 0)

    # ---- save access -----------------------------------------------------------
    @staticmethod
    def _flags(sf: SaveFile) -> tuple[list[int], list[int]]:
        fs = sf.sd["m_FlagStatus"]
        return fs["skillPanelBitFlag"], fs["skillPanelUnlockBitFlag"]

    @staticmethod
    def _status(sf: SaveFile, life: str) -> dict:
        for e in sf.avatar["m_lifeStatus"]:
            if e["key"] == life:
                return e["value"]
        raise SaveFileError(f"unknown life id {life}")

    def _learned(self, sf: SaveFile, life: str) -> set[int]:
        learned, _ = self._flags(sf)
        panels = self._panels(life)
        root = self._root(panels)
        return {no for no, p in panels.items() if no != root and not p["blank"] and learned[p["flag"]]}

    @staticmethod
    def _open(panels: dict[int, dict], root: int, learned: set[int], no: int) -> bool:
        """A panel's children are reachable: the start panel, a learned panel, or a blank behind an open one."""
        while True:
            if no == root or no in learned:
                return True
            p = panels.get(no)
            if p is None or not p["blank"]:
                return False
            no = p["parent"]

    def _cond_met(self, sf: SaveFile, cond: dict) -> bool:
        if cond["type"] == "rank":
            return self._status(sf, cond["life"])["licenseRank"] >= cond["rank"]
        if cond["type"] == "panels":
            life = self.board_life.get(cond["board"])
            return life is not None and len(self._learned(sf, life)) >= cond["count"]
        return False

    # ---- read ------------------------------------------------------------------
    def state(self, sf: SaveFile, life: str) -> dict:
        panels = self._panels(life)
        root = self._root(panels)
        learned_flags, unlock_flags = self._flags(sf)
        learned = self._learned(sf, life)
        st = self._status(sf, life)
        spent = sum(panels[no]["cost"] for no in learned)
        out = []
        for no, p in panels.items():
            reachable = p["parent"] < 0 or self._open(panels, root, learned, p["parent"])
            conds = [dict(c, met=self._cond_met(sf, c)) for c in p["conds"]]
            if no == root:
                status = "root"
            elif p["blank"]:
                status = "blank"
            elif no in learned:
                status = "learned"
            elif not reachable:
                status = "hidden"
            elif not all(c["met"] for c in conds):
                status = "locked"
            else:
                status = "available"
            out.append(dict(p, status=status, conds=conds, unlocked=bool(unlock_flags[p["flag"]])))
        return {"life": life, "board": self.board(life)["id"], "panels": out, "rank": st["licenseRank"],
                "sp": {"earned": st["skillMaxPoint"], "spent": spent, "free": st["skillMaxPoint"] - spent},
                "learned": len(learned), "total": sum(1 for no, p in panels.items() if no != root and not p["blank"])}

    # ---- write -----------------------------------------------------------------
    def _refresh_unlocks(self, sf: SaveFile) -> None:
        """Set the unlock flag on every conditional panel whose parent is learned and whose conditions hold.
        Flags already set stay set (the game keeps them after the condition passes)."""
        _, unlock = self._flags(sf)
        for life in self.boards:
            panels = self._panels(life)
            root = self._root(panels)
            learned = self._learned(sf, life)
            for no, p in panels.items():
                if not p["conds"] or no == root or p["blank"]:
                    continue
                parent_ok = self._open(panels, root, learned, p["parent"])
                if (no in learned or parent_ok) and all(self._cond_met(sf, c) for c in p["conds"]):
                    unlock[p["flag"]] = 1

    def learn(self, sf: SaveFile, life: str, no: int, free: bool = False) -> list[int]:
        """Learn a panel. Game rules: the parent must be learned, its conditions met and the SP free.
        `free`: learn the whole path from the start panel, ignore conditions, and raise `skillMaxPoint` if the
        learned panels would cost more than the life has earned."""
        panels = self._panels(life)
        root = self._root(panels)
        if no not in panels or no == root or panels[no]["blank"]:
            raise SaveFileError(f"no learnable panel {no} on {life}'s board")
        learned = self._learned(sf, life)
        path, cur = [], no
        while cur != root and cur not in learned:
            if not panels[cur]["blank"]:
                path.append(cur)
            cur = panels[cur]["parent"]
            if cur < 0 or cur not in panels:
                break
        if not path:
            return []
        if not free:
            if len(path) > 1 or not self._open(panels, root, learned, panels[no]["parent"]):
                raise SaveFileError("learn the panel next to it first")
            p = panels[no]
            missing = [c for c in p["conds"] if not self._cond_met(sf, c)]
            if missing:
                raise SaveFileError("requirement not met: " + ", ".join(_cond_text(c) for c in missing))
        cost = sum(panels[n]["cost"] for n in path)
        st = self._status(sf, life)
        spent = sum(panels[n]["cost"] for n in learned)
        if spent + cost > st["skillMaxPoint"]:
            if not free:
                raise SaveFileError(f"needs {cost} SP, {st['skillMaxPoint'] - spent} free")
            st["skillMaxPoint"] = spent + cost
        flags, unlock = self._flags(sf)
        for n in path:
            flags[panels[n]["flag"]] = 1
            if panels[n]["conds"]:
                unlock[panels[n]["flag"]] = 1
        self._refresh_unlocks(sf)
        sf.dirty = True
        return [panels[n]["flag"] for n in path]

    def remove(self, sf: SaveFile, life: str, no: int) -> list[int]:
        """Forget a panel and every learned panel that hangs off it; the SP comes back."""
        panels = self._panels(life)
        learned = self._learned(sf, life)
        if no not in learned:
            return []
        children: dict[int, list[int]] = {}
        for n, p in panels.items():
            children.setdefault(p["parent"], []).append(n)
        drop, todo = [], [no]
        while todo:
            n = todo.pop()
            if n in learned or panels[n]["blank"]:
                if n in learned:
                    drop.append(n)
                todo.extend(children.get(n, []))
        flags, _ = self._flags(sf)
        for n in drop:
            flags[panels[n]["flag"]] = 0
        sf.dirty = True
        return [panels[n]["flag"] for n in drop]

    def learn_all(self, sf: SaveFile, life: str) -> int:
        panels = self._panels(life)
        root = self._root(panels)
        before = len(self._learned(sf, life))
        for no, p in panels.items():
            if no != root and not p["blank"]:
                self.learn(sf, life, no, free=True)
        return len(self._learned(sf, life)) - before

    def reset(self, sf: SaveFile, life: str) -> int:
        panels = self._panels(life)
        flags, _ = self._flags(sf)
        learned = self._learned(sf, life)
        for no in learned:
            flags[panels[no]["flag"]] = 0
        sf.dirty = True
        return len(learned)

    def set_level_sp(self, sf: SaveFile, life: str, old_level: int, new_level: int) -> None:
        """Keep `skillMaxPoint` in step with a level edit; SP above the level table (from free learning) stays."""
        st = self._status(sf, life)
        extra = st["skillMaxPoint"] - self.sp_for_level(old_level)
        st["skillMaxPoint"] = max(0, self.sp_for_level(new_level) + max(0, extra))
        sf.dirty = True


def _cond_text(c: dict) -> str:
    if c["type"] == "rank":
        return f"license rank {c['rank']}"
    if c["type"] == "panels":
        return f"{c['count']} panels learned"
    return c["type"]
