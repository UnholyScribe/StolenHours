"""Decode a saved CDP Page.captureScreenshot response into a PNG. usage: cdp_png.py <response.json> <out.png>"""
import base64
import json
import sys
from pathlib import Path

from PIL import Image

data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
data = data.get("result", data)
Path(sys.argv[2]).parent.mkdir(parents=True, exist_ok=True)
Path(sys.argv[2]).write_bytes(base64.b64decode(data["data"]))
print(sys.argv[2], Image.open(sys.argv[2]).size)
