"""Read-only: fit world (X, Y) -> minimap UV by maximising how many Map_200000 func points land on land pixels.

Land = not sea-blue on the minimap art. Searches the 8 axis swaps/flips, then scale and offset per axis.
Prints the best fits; writes %TEMP%/map_fit.png with func points (white) and event spots (red) under the winner.
"""
import itertools
import os
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "editor"))
from stolenhours.mapevents import _Table  # noqa: E402

MAP = ROOT / "assets/game/Game/Content/Graphics/2D/UI/Map/Map_200000/Tex/minimap_Map_200000_000000.png"
N = 1024

Image.MAX_IMAGE_PIXELS = None
art = Image.open(MAP).convert("RGB").resize((N, N), Image.LANCZOS)
a = np.asarray(art).astype(int)
r, g, b = a[..., 0], a[..., 1], a[..., 2]
land = ~((b > r + 8) & (b >= g - 10))

func = _Table("Map/Map_200000/Map_200000_GDSMapFuncPoint.json")
pts = np.array([(v["Position"]["X"], v["Position"]["Y"]) for v in func.rows.values()
                if v.get("Position") and (v["Position"]["X"] or v["Position"]["Y"])])
print(len(pts), "func points; x", pts[:, 0].min(), pts[:, 0].max(), "y", pts[:, 1].min(), pts[:, 1].max())


def score(u, v):
    px, py = (u * N).astype(int), (v * N).astype(int)
    ok = (px >= 0) & (px < N) & (py >= 0) & (py < N)
    return land[py[ok], px[ok]].sum() / len(u)


results = []
for swap, fu, fv in itertools.product((False, True), (1, -1), (1, -1)):
    wu, wv = (pts[:, 1], pts[:, 0]) if swap else (pts[:, 0], pts[:, 1])
    for half in np.arange(80000, 160001, 5000):
        for ou in np.arange(-30000, 30001, 3000):
            for ov in np.arange(-30000, 30001, 3000):
                u = 0.5 + fu * (wu - ou) / (2 * half)
                v = 0.5 + fv * (wv - ov) / (2 * half)
                results.append((score(u, v), swap, fu, fv, half, ou, ov))
results.sort(reverse=True)
for row in results[:8]:
    print("land %.3f swap=%s fu=%d fv=%d half=%d ou=%d ov=%d" % row)
for swap, fu, fv in itertools.product((False, True), (1, -1), (1, -1)):
    best = next(rw for rw in results if rw[1:4] == (swap, fu, fv))
    print("  best for swap=%s fu=%d fv=%d: %.3f half=%d ou=%d ov=%d" % (swap, fu, fv, best[0], *best[4:]))

_, swap, fu, fv, half, ou, ov = results[0]
im = art.copy()
d = ImageDraw.Draw(im)
for x, y in pts:
    wu, wv = (y, x) if swap else (x, y)
    u, v = 0.5 + fu * (wu - ou) / (2 * half), 0.5 + fv * (wv - ov) / (2 * half)
    d.point((u * N, v * N), fill=(255, 255, 255))
out = Path(os.environ["TEMP"]) / "map_fit.png"
im.save(out)
print("->", out)
