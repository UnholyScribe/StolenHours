"""Writes a CDP Page.captureScreenshot response (saved JSON) as a PNG.

Run:  py -3.12 tools/save_shot.py <cdp-response.json> <out.png>
"""

import base64
import json
import sys
from pathlib import Path

data = base64.b64decode(json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))["data"])
out = Path(sys.argv[2])
out.parent.mkdir(parents=True, exist_ok=True)
out.write_bytes(data)
w, h = int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")
print(f"{out} {w}x{h} {len(data) // 1024} KB")
