"""Contact sheet of extracted PNGs matching a glob, for eyeballing game textures.

usage: py -3.12 research/sheet.py <out.png> <glob> [<glob> ...]   (globs relative to assets/game)
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1] / "assets" / "game"
CELL = 192

files = sorted({p for g in sys.argv[2:] for p in ROOT.glob(g)})
cols = 6
rows = max(1, -(-len(files) // cols))
sheet = Image.new("RGBA", (cols * CELL, rows * (CELL + 28)), (40, 40, 48, 255))
draw = ImageDraw.Draw(sheet)
for i, p in enumerate(files):
    im = Image.open(p).convert("RGBA")
    size = im.size
    im.thumbnail((CELL, CELL))
    x, y = (i % cols) * CELL, (i // cols) * (CELL + 28)
    sheet.alpha_composite(im, (x + (CELL - im.width) // 2, y + (CELL - im.height) // 2))
    draw.text((x + 4, y + CELL + 2), f"{p.stem[-22:]}", fill=(230, 230, 230))
    draw.text((x + 4, y + CELL + 14), f"{size[0]}x{size[1]}", fill=(160, 160, 160))
sheet.save(sys.argv[1])
print(len(files), "images ->", sys.argv[1])
