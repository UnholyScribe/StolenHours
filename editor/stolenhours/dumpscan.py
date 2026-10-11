"""Read a StolenHours value dump and cross-reference it with the save file.

Value dump line formats (written by hook\\ue4ss_mod\\StolenHours\\Scripts\\stolenhours_dump.lua):
    === <object full name>
      -- <class full name>
      0x<offset> <PropertyType> <Name> = <value>
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from . import paths

PROP_RE = re.compile(r"^  0x([0-9A-Fa-f]+) (\w+) (\S+) = (.*)$")
INTERESTING_NAME = re.compile(
    r"money|dosh|gold|coin|price|lv|level|exp|life|job|hp|sp|stamina|status|param|stat|name|item|inventory|"
    r"stock|equip|skill|rank|star|avatar|chara|player|island|playtime|time", re.I)


@dataclass
class Prop:
    obj: str
    cls: str
    offset: int
    ptype: str
    name: str
    value: str


@dataclass
class Report:
    objects: int = 0
    props: int = 0
    hits: dict[str, list[Prop]] = field(default_factory=dict)
    interesting: list[Prop] = field(default_factory=list)


def latest_dump(kind: str = "values") -> Path | None:
    files = sorted(paths.DUMPS_DIR.glob(f"{kind}_*.txt"), key=lambda p: p.stat().st_mtime)
    return files[-1] if files else None


def iter_props(path: Path):
    obj = cls = ""
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.rstrip("\n")
            if line.startswith("=== "):
                obj, cls = line[4:], ""
            elif line.startswith("  -- "):
                cls = line[5:]
            else:
                m = PROP_RE.match(line)
                if m:
                    yield Prop(obj, cls, int(m.group(1), 16), m.group(2), m.group(3), m.group(4))


def _needle(value) -> re.Pattern:
    if isinstance(value, str):
        return re.compile(re.escape(f'"{value}"'))
    return re.compile(rf"(?<![\w.\-]){re.escape(str(value))}(?![\w.])")


def save_targets(sf) -> dict[str, object]:
    t: dict[str, object] = {"Money": sf.money, "character name": sf.character_name,
                            "island name": sf.island_name,
                            "inventory getOrderCount": sf.inventory["getOrderCount"]}
    for l in sf.lives():
        if l["level"] and l["level"] > 1:
            t[f"{l['id']} ({l['name']}) level"] = l["level"]
        if l["exp"] and l["exp"] > 100:
            t[f"{l['id']} ({l['name']}) exp"] = l["exp"]
    return t


def analyze(path: Path, targets: dict[str, object]) -> Report:
    rep = Report(hits={k: [] for k in targets})
    needles = {k: _needle(v) for k, v in targets.items()}
    seen_obj = set()
    for p in iter_props(path):
        rep.props += 1
        if p.obj not in seen_obj:
            seen_obj.add(p.obj)
            rep.objects += 1
        for k, n in needles.items():
            if n.search(p.value):
                rep.hits[k].append(p)
        if INTERESTING_NAME.search(p.name) and "/Script/DP1Project." in p.cls:
            rep.interesting.append(p)
    return rep


def format_report(rep: Report, targets: dict[str, object], max_per_target: int = 25) -> str:
    out = [f"{rep.objects} objects, {rep.props} properties scanned", "",
           "== Save values found in the running game ==",
           "(the live value can differ if you earned/spent since the last save)"]
    for k, v in targets.items():
        hits = rep.hits.get(k, [])
        out.append(f"{k} = {v!r}: {len(hits)} hit(s)")
        for p in hits[:max_per_target]:
            val = p.value if len(p.value) < 160 else p.value[:160] + "..."
            out.append(f"    {p.obj}  ::  {p.ptype} {p.name} @0x{p.offset:X} = {val}")
    out += ["", "== Game-code properties with interesting names =="]
    for p in rep.interesting:
        val = p.value if len(p.value) < 120 else p.value[:120] + "..."
        out.append(f"    {p.obj}  ::  {p.ptype} {p.name} = {val}")
    return "\n".join(out)
