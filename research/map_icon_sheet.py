"""Contact sheet of every GDSMapIconData type: icon art, type number, mapTextId; plus a TSV of the rows.

usage: py -3.12 research/map_icon_sheet.py <out.png>
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "editor"))
from stolenhours import paths  # noqa: E402
from stolenhours.mapevents import _Table  # noqa: E402

rows = sorted(_Table("Menu/GDSMapIconData.json").rows.values(), key=lambda r: r["mapIconType"])
tex = _Table("Menu/GDSMenuIconTexture.json").rows
CELL, COLS = 96, 16
sheet = Image.new("RGB", (CELL * COLS, CELL * ((len(rows) + COLS - 1) // COLS)), (60, 70, 80))
d = ImageDraw.Draw(sheet)
tsv = []
for i, r in enumerate(rows):
    x, y = (i % COLS) * CELL, (i // COLS) * CELL
    t = tex.get(r["mapIconId"])
    src = None
    if t:
        asset = t["iconInfoPerId"]["AssetPath"].split(".")[0]
        src = paths.EXTRACT_DIR / "Game" / "Content" / (asset.removeprefix("/Game/") + ".png")
    if src and src.exists():
        im = Image.open(src).convert("RGBA")
        im.thumbnail((CELL - 20, CELL - 20))
        sheet.paste(im, (x + (CELL - im.width) // 2, y + 2), im)
    d.text((x + 3, y + CELL - 14), f"{r['mapIconType']} {r['mapTextId'][:10]}", fill=(255, 255, 120))
    tsv.append(f"{r['mapIconType']}\t{r['mapIconId']}\t{r['mapTextId']}\t{r['detailWindowType']}\t"
               f"{r['mapIconSubType']}\t{r['drawPriority']}\t{'yes' if src and src.exists() else 'NO ART'}")
sheet.save(sys.argv[1])
Path(sys.argv[1]).with_suffix(".tsv").write_text("\n".join(tsv), encoding="utf-8")
print(len(rows), "types")
