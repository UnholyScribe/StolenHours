"""Read-only: look for hidden copies of the play time in the raw save body, and show the real-world dates.
Usage: py -3.12 research/playtime_copies.py"""

import datetime as dt
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "editor"))
from stolenhours import container, paths, savefile  # noqa: E402


def ticks(t: int) -> str:
    return (dt.datetime(1, 1, 1) + dt.timedelta(microseconds=t // 10)).strftime("%Y-%m-%d %H:%M:%S")


def find_all(blob: bytes, pat: bytes) -> list[int]:
    out, i = [], blob.find(pat)
    while i != -1:
        out.append(i)
        i = blob.find(pat, i + 1)
    return out


def main():
    sf = savefile.SaveFile.load(paths.default_save_path())
    gvas = container.unpack(sf.raw, sf.key).gvas
    pd = sf.sd["m_PlayData"]
    secs = pd["playTime"]
    print(f"playTime {secs} s = {secs // 3600}h {secs % 3600 // 60}m")
    for label, pat in (("u32", struct.pack("<I", secs)), ("u64", struct.pack("<Q", secs)),
                       ("f32 seconds", struct.pack("<f", secs)), ("f64 seconds", struct.pack("<d", secs)),
                       ("f32 hours", struct.pack("<f", secs / 3600)), ("u32 minutes", struct.pack("<I", secs // 60))):
        print(f"  {label:12} hits {find_all(gvas, pat)}")
    print(f"startDateTime {ticks(pd['startDateTime'])}")
    print(f"saveDateTime  {ticks(pd['saveDateTime'])}")
    span = (pd["saveDateTime"] - pd["startDateTime"]) // 10_000_000
    print(f"real time between start and last save: {span // 86400} days ({span // 3600} h)")


if __name__ == "__main__":
    main()
