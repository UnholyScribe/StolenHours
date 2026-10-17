"""Read-only: plot every Map_200000 event spot on the minimap under four axis layouts, to see which fits the art.

World bounds come from Map_200000_GDSMapMinimap (+-120000). Fishing events are blue (should hug water),
legendary hunts yellow, the rest red. Output: %TEMP%/map_orientation.png
"""
import os
import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "editor"))
from stolenhours.mapevents import _Table  # noqa: E402

MAP = ROOT / "assets/game/Game/Content/Graphics/2D/UI/Map/Map_200000/Tex/minimap_Map_200000_000000.png"
LO, HI = -120000.0, 120000.0
SIZE = 900

config, place = _Table("Quest/GDSActiveEventConfig.json"), _Table("Quest/GDSActiveEventPlaceData.json")
purpose = _Table("Quest/GDSQuestPurposePoint.json")
titles = {k: (v["Text"][0].get("nounSingularForm_en") if v.get("Text") else "")
          for k, v in _Table("Quest/GDSQuestTitleText.json").rows.items()}

spots = {}
for eid, c in config.rows.items():
    pl = place.rows.get(c["EventPointId"], {})
    if pl.get("mapId") != "Map_200000":
        continue
    pp = purpose.rows.get(pl.get("purposePointId"))
    if not pp:
        continue
    t = titles.get(c["TitleId"]) or ""
    col = (40, 120, 255) if "Fish" in t else (255, 220, 0) if "Legendary" in t else (230, 30, 30)
    p = pp["tgtPosition"]
    spots[c["EventPointId"]] = (p["X"], p["Y"], col)

Image.MAX_IMAGE_PIXELS = None
if "--parts" in sys.argv:
    tiles = sorted(MAP.parent.glob("minimap_Map_200000_parts*.png"))
    tile = Image.open(tiles[0]).size[0]
    base = Image.new("RGB", (12 * tile, 12 * tile))
    for i, t in enumerate(tiles[:144]):
        base.paste(Image.open(t).convert("RGB"), ((i % 12) * tile, (i // 12) * tile))
    base = base.resize((SIZE, SIZE), Image.LANCZOS)
else:
    base = Image.open(MAP).convert("RGB").resize((SIZE, SIZE), Image.LANCZOS)
norm = lambda v: (v - LO) / (HI - LO)  # noqa: E731
layouts = {
    "u=x v=y": lambda x, y: (norm(x), norm(y)),
    "u=y v=1-x": lambda x, y: (norm(y), 1 - norm(x)),
    "u=x v=1-y": lambda x, y: (norm(x), 1 - norm(y)),
    "u=1-y v=x (fitted)": lambda x, y: (1 - norm(y), norm(x)),
}
sheet = Image.new("RGB", (SIZE * 2, SIZE * 2 + 40), (20, 20, 20))
for i, (name, f) in enumerate(layouts.items()):
    im = base.copy()
    d = ImageDraw.Draw(im)
    for x, y, col in spots.values():
        u, v = f(x, y)
        px, py = u * SIZE, v * SIZE
        d.ellipse((px - 4, py - 4, px + 4, py + 4), fill=col, outline=(0, 0, 0))
    d.text((8, 8), name, fill=(255, 255, 255))
    sheet.paste(im, ((i % 2) * SIZE, (i // 2) * SIZE))
out = Path(os.environ["TEMP"]) / "map_orientation.png"
sheet.save(out)
print(len(spots), "spots ->", out)
xs, ys = [s[0] for s in spots.values()], [s[1] for s in spots.values()]
print("x range", min(xs), max(xs), "y range", min(ys), max(ys))
