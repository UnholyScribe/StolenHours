"""Read-only: where the save keeps the island name and anything clock-like. Usage: py -3.12 research/island_time_probe.py"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "editor"))
from stolenhours import paths, savefile  # noqa: E402

PATTERN = re.compile(r"(?i)time|date|tick|clock|island|day|hour|elapsed|period|second|minute|count")


def walk(o, path=""):
    if isinstance(o, dict):
        for k, v in o.items():
            yield from walk(v, f"{path}.{k}")
    elif isinstance(o, list):
        for n, v in enumerate(o[:2]):
            yield from walk(v, f"{path}[{n}]")
    else:
        yield path, o


def main():
    sf = savefile.SaveFile.load(Path(sys.argv[1]) if len(sys.argv) > 1 else paths.default_save_path())
    print("m_PlayData:")
    for k, v in sf.sd["m_PlayData"].items():
        s = repr(v)
        print(f"  {k} = {s if len(s) < 100 else f'<{type(v).__name__}, {len(v)} entries>'}")
    print("\nclock / island / counter fields anywhere:")
    seen = set()
    for path, v in walk(sf.data):
        key = re.sub(r"\[\d+\]", "[]", path)
        if key not in seen and PATTERN.search(key.split(".")[-1]):
            seen.add(key)
            print(f"  {key} = {repr(v)[:70]}")


def game_texts(key_re: str):
    """English text of every game text row whose key matches."""
    root = Path(__file__).resolve().parents[1] / "assets" / "game" / "Game" / "Content" / "GameData"
    for f in sorted(root.rglob("GDS*Text*.json")):
        rows = [r for obj in json.loads(f.read_text(encoding="utf-8")) if isinstance(obj, dict)
                for r in obj.get("Properties", {}).get("m_dataMap", [])]
        for row in rows:
            if re.search(key_re, row.get("Key", "")):
                info = row["Value"].get("textInfo") or [{}]
                yield f.stem, row["Key"], (info[0].get("text_en") or info[0].get("Text") or "").replace("\r\n", " / ")


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--texts":
        for stem, key, text in game_texts(sys.argv[2]):
            print(f"{stem}  {key}  |  {text}")
    else:
        main()
