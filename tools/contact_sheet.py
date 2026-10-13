"""Thumbnail grid of every PNG under a folder, with file names, for eyeballing extracted game art.

usage: py -3.12 tools\\contact_sheet.py <folder> <out.png> [thumb=160] [cols=8]
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw

src, out = Path(sys.argv[1]), Path(sys.argv[2])
thumb = int(sys.argv[3]) if len(sys.argv) > 3 else 160
cols = int(sys.argv[4]) if len(sys.argv) > 4 else 8
files = sorted(src.rglob("*.png"))
cell_h = thumb + 28
rows = (len(files) + cols - 1) // cols
sheet = Image.new("RGB", (cols * thumb, max(1, rows) * cell_h), (40, 40, 48))
draw = ImageDraw.Draw(sheet)
for i, f in enumerate(files):
    x, y = (i % cols) * thumb, (i // cols) * cell_h
    im = Image.open(f).convert("RGBA")
    size = im.size
    im.thumbnail((thumb - 6, thumb - 6))
    checker = Image.new("RGBA", (thumb - 6, thumb - 6), (90, 90, 100, 255))
    checker.alpha_composite(im, ((checker.width - im.width) // 2, (checker.height - im.height) // 2))
    sheet.paste(checker.convert("RGB"), (x + 3, y + 3))
    draw.text((x + 3, y + thumb - 1), f.stem[-22:], fill=(230, 230, 230))
    draw.text((x + 3, y + thumb + 12), f"{size[0]}x{size[1]}", fill=(160, 160, 170))
out.parent.mkdir(parents=True, exist_ok=True)
sheet.save(out)
print(out, len(files))
