"""Read-only probe: island craft areas, debris/craft objects, huge map, companions.

Usage:
  py -3.12 research/island_build_companion_probe.py [path/to/gamedata.bin]

Uses a temp copy when given no path: copies the detected live save to research/tmp/gamedata_probe.bin
without modifying the original.
"""
from __future__ import annotations

import collections
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "editor"))

from stolenhours import paths, savefile  # noqa: E402
from stolenhours.mapevents import _Table  # noqa: E402

TMP = ROOT / "research" / "tmp" / "gamedata_probe.bin"
GAME_DATA = paths.EXTRACT_DIR / "Game" / "Content" / "GameData"


def resolve_save(arg: str | None) -> Path:
    src = Path(arg) if arg else paths.default_save_path()
    if arg:
        return src
    TMP.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, TMP)
    print(f"temp copy: {TMP}  (from {src})")
    return TMP


def key(k):
    return k["Name"] if isinstance(k, dict) else k


def load_noun(prefix: str) -> dict[str, str]:
    rows = _Table("Map/GDSMapText_Noun.json").rows
    out = {}
    for k, v in rows.items():
        if not k.startswith(prefix):
            continue
        info = v.get("textInfo") or [{}]
        en = (info[0].get("nounSingularForm_en") or info[0].get("text_en") or "").strip()
        out[k] = en or k
    return out


def chara_names() -> dict[str, str]:
    rows = _Table("Chara/GDSCharaText_Noun.json").rows
    out = {}
    for k, v in rows.items():
        if not k.startswith("name_"):
            continue
        info = v.get("textInfo") or [{}]
        en = (info[0].get("nounSingularForm_en") or info[0].get("text_en") or "").strip()
        out[k.replace("name_", "", 1)] = en or k
    return out


def handle_id(h) -> int | None:
    if isinstance(h, dict):
        return h.get("Handle") or h.get("handle")
    return None


def bitflag_name(n: int) -> str:
    names = {0: "None", 1: "Shave", 2: "Put", 4: "IsPlannedConstruct"}
    parts = [names[b] for b in (1, 2, 4) if n & b]
    return "|".join(parts) if parts else str(n)


def summarize_craft(sf: savefile.SaveFile) -> None:
    cs = sf.sd["m_CraftStatus"]
    arr = cs["craftObjStatusPArray"]
    print(f"\n== m_CraftStatus (craftObjStatusPArray len={len(arr)})")
    flags = collections.Counter(o["objStatusBitFlag"] for o in arr)
    nz = sum(1 for o in arr if o["objStatusBitFlag"] != 0)
    nonempty_id = sum(1 for o in arr if o.get("craftObjId") not in ("None", "", None))
    print(f"  non-zero objStatusBitFlag: {nz}")
    print(f"  craftObjId not None: {nonempty_id}")
    print(f"  bitFlag histogram: {dict(flags)}")
    ex = cs["CraftExParamP"]
    print(f"  CraftExParamP arrays: land={len(ex['exParamLand'])} house={len(ex['exParamHouse'])} "
          f"pick={len(ex['exParamPickPoint'])} stand={len(ex['exParamStand'])} "
          f"plantDungeon={len(ex['exParamPlantDungeon'])} vegField={len(ex['exParamVegetableField'])} "
          f"planned={len(ex['exParamPlannedConstruct'])}")
    if ex["exParamLand"]:
        sample = ex["exParamLand"][0]
        print(f"  exParamLand[0] sample: tileId={sample.get('tileId')} isRoundView={sample.get('isRoundView')}")
    samples = [o for o in arr if o["objStatusBitFlag"] or o.get("craftObjId") not in ("None", "", None)][:8]
    for o in samples:
        print(f"    craftObjId={o['craftObjId']} flag={bitflag_name(o['objStatusBitFlag'])} "
              f"mapId={o['mapId']} gridIdx={o['gridIdx']} loc={o['Location']}")

    cas = sf.sd["m_CraftAreaStatus"]
    print(f"\n== m_CraftAreaStatus")
    for list_name in ("mapCraftAreaStatusPList", "outdoorCraftAreaStatusPList", "indoorCraftAreaStatusPList",
                      "wallCraftAreaStatusPList", "ceilingCraftAreaStatusPList"):
        lst = cas[list_name]
        print(f"  {list_name}: len={len(lst)}")
        by_map = collections.Counter(a["mapId"] for a in lst)
        if by_map:
            print(f"    mapId counts: {dict(by_map.most_common(12))}")
        for a in lst[:3]:
            print(f"    sample mapId={a['mapId']} AreaID={a['AreaID']} Category={a['Category']} "
                  f"W×D×H={a['Width']}×{a['Depth']}×{a['Height']} voxel={a['voxelWidth']}×{a['voxelDepth']}×{a['voxelHeight']} "
                  f"craftObjs={len(a['craftObjStHdlArray'])} putObjs={len(a['putCraftObjStHdlArray'])} isFix={a['isFix']}")


def summarize_huge(sf: savefile.SaveFile) -> None:
    hm = sf.sd["m_HugeMapStatusP"]["areaStatus"]
    if isinstance(hm, list):
        hm = {a["key"]: a["value"] for a in hm}
    print(f"\n== m_HugeMapStatusP.areaStatus ({len(hm)} areas)")
    ranks = [(k, v["nowAreaRank"], v["releaseAreaRank"], v["AreaPoint"]) for k, v in hm.items()]
    for k, now, rel, pt in sorted(ranks, key=lambda x: -x[3])[:8]:
        print(f"  {k}: nowRank={now} releaseRank={rel} AreaPoint={pt}")
    opened = sum(1 for _, now, rel, _ in ranks if rel > 0)
    print(f"  areas with releaseAreaRank>0: {opened}")


def summarize_play(sf: savefile.SaveFile) -> None:
    pd = sf.sd["m_PlayData"]
    pc = pd["playCountData"]
    print(f"\n== m_PlayData (craft / island hints)")
    print(f"  mapId={pd['mapId']} subMapId={pd['subMapId']}")
    print(f"  obstacleReleaseNum={pc['obstacleReleaseNum']} instantCharaJoinNum={pc['instantCharaJoinNum']}")
    print(f"  developmentRank={pc['developmentRank']} islandPurchaseNums={pc['islandPurchaseNums']}")


def summarize_companions(sf: savefile.SaveFile, names: dict[str, str]) -> None:
    ch = sf.sd["m_CharaStatus"]
    party = sf.sd["m_PartyStatus"]
    npc = sf.sd["m_NpcStatus"]
    print(f"\n== companions")
    print(f"  m_stFriendP: {len(ch['m_stFriendP'])}  m_stGuestP: {len(ch['m_stGuestP'])}  "
          f"m_stSupportP: {len(ch['m_stSupportP'])}  avatars: {len(ch['m_stAvatarP'])}")
    friends = [f for f in ch["m_stFriendP"] if f.get("m_paramId") not in ("None", "", None)]
    print(f"  friends with m_paramId set: {len(friends)}")
    for f in friends[:12]:
        pid = f["m_paramId"]
        print(f"    {pid} ({names.get(pid, '?')}) friendship={f.get('m_friendship')} lv={f.get('m_lv')} "
              f"instant={f.get('m_isInstantChara')} hdl={handle_id(f.get('m_charaStHdl'))}")

    print(f"  m_PartyStatus.party list: {len(party['m_partyCharaInfoList'])}")
    for p in party["m_partyCharaInfoList"]:
        print(f"    idx={p['m_partyIdx']} type={p['m_partyType']} leader={p['m_isLeader']} hdl={handle_id(p['m_charaStHdl'])}")
    sup = party["m_supporterCharaInfo"]
    ins = party["m_instantCharaInfo"]
    print(f"  supporter hdl={handle_id(sup.get('m_charaStatusHandle'))}  "
          f"instant hdl={handle_id(ins.get('m_charaStatusHandle'))} enableTimer={ins.get('m_isEnableUpdateTimer')}")
    print(f"  followerId={party['m_followerCharaInfo'].get('m_followerId')}")

    print(f"  m_NpcStatus: inhabitant={len(npc['CraftAreaInhabitantInfo'])} "
          f"craftFriendNpc={len(npc['CraftAreaFriendNpcInfo'])} gallery={len(npc['GalleryInhabitantInfo'])}")


def gds_craft_tables() -> None:
    craft_dir = GAME_DATA / "Craft"
    print(f"\n== GDS craft tables under EXTRACT_DIR")
    if not craft_dir.is_dir():
        print(f"  MISSING: {craft_dir} (Craft JSON not extracted in this workspace)")
        return
    for p in sorted(craft_dir.glob("*.json")):
        print(f"  {p.name}")


def map_id_guide() -> None:
    wm = _Table("Map/GDSWorldMapData.json").rows
    nouns = load_noun("name_WorldMap_")
    print("\n== GDSWorldMapData (world menu maps)")
    for k, r in sorted(wm.items(), key=lambda x: x[0]):
        mid = r["mapId"]
        name = nouns.get(r["nameId"], r["nameId"])
        print(f"  {k} -> {mid}  ({name})")

    print("\n== Map folders with GDSMapObstaclePlacement (build / debris maps)")
    for p in sorted(GAME_DATA.glob("Map/Map_*/Map_*_GDSMapObstaclePlacement.json")):
        mid = p.parent.name
        n_ob = len(json.loads(p.read_text(encoding="utf-8"))[0]["Properties"]["m_dataMap"])
        print(f"  {mid}: {n_ob} obstacles")


def main() -> None:
    save_path = resolve_save(sys.argv[1] if len(sys.argv) > 1 else None)
    sf = savefile.SaveFile.load(save_path)
    names = chara_names()
    summarize_play(sf)
    summarize_craft(sf)
    summarize_huge(sf)
    summarize_companions(sf, names)
    gds_craft_tables()
    map_id_guide()


if __name__ == "__main__":
    main()
