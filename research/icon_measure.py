"""Measures map marker sizes in a game screenshot, in 1080p screen pixels.

usage: py -3.12 research/icon_measure.py <screenshot> <cx> <cy> [radius]
Scans rows/columns through (cx, cy) (screenshot pixels) and reports the extent of red-glow and icon pixels.
"""
import sys

from PIL import Image

im = Image.open(sys.argv[1]).convert("RGB")
cx, cy = int(sys.argv[2]), int(sys.argv[3])
rad = int(sys.argv[4]) if len(sys.argv) > 4 else 40
k = 1080 / im.height


def kind(c):
    r, g, b = c
    if r > 180 and g < 110 and b < 110:
        return "red"
    if r > 200 and 120 < g < 200 and b < 120:
        return "orange"
    if g > 170 and r < 200 and b < 200 and g > r:
        return "green"
    if b > 180 and r < 140:
        return "blue"
    return "."


for axis in ("x", "y"):
    line = []
    for d in range(-rad, rad + 1):
        p = (cx + d, cy) if axis == "x" else (cx, cy + d)
        line.append(kind(im.getpixel(p)))
    for name in ("red", "orange", "green", "blue"):
        idx = [i for i, s in enumerate(line) if s == name]
        if idx:
            span = idx[-1] - idx[0] + 1
            print(f"{axis} {name:6} span {span:3}px -> {span * k:6.1f} @1080p  ({idx[0] - rad}..{idx[-1] - rad})")
    print(axis, "".join(s[0] for s in line))
