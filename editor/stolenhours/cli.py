"""Command line entry point: `py -3.12 -m stolenhours <command>` from the editor folder."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from . import container, live, paths, safety, savefile, steam


def _save_path(args) -> Path:
    return Path(args.save) if args.save else paths.default_save_path()


def _load(args) -> savefile.SaveFile:
    p = _save_path(args)
    print(f"loading {p} ...", file=sys.stderr)
    return savefile.SaveFile.load(p)


def _finish(sf: savefile.SaveFile, args) -> None:
    if args.dry_run:
        sf.to_bin()
        print("dry run: packed and verified, nothing written")
        return
    res = sf.write(Path(args.out) if args.out else None)
    print(f"written {res['target']}\n  sha256 {res['sha256']}\n  backup {res['backup']}")


def cmd_info(args):
    sf = _load(args)
    h, m = divmod(sf.play_time_seconds // 60, 60)
    print(f"character  {sf.character_name}\nisland     {sf.island_name}\nmoney      {sf.money}\n"
          f"life       {sf.current_life} ({savefile.LIFE_NAMES_UNVERIFIED.get(sf.current_life, '?')})\n"
          f"play time  {h}h{m:02d}m\nitems      {len(sf.items())}")
    procs = safety.running_game_processes()
    print(f"game       {'RUNNING: ' + ', '.join(procs) if procs else 'closed'}")


def cmd_verify(args):
    p = _save_path(args)
    key = container.load_key()
    raw = p.read_bytes()
    up = container.unpack(raw, key)
    print(f"container  ok  (gvas {len(up.gvas)} bytes, footer v{up.footer_version}, md5 ok)")
    print(f"repack     {'byte-exact' if container.roundtrip_exact(raw, key) else 'MISMATCH'}")
    data = savefile.parse_gvas(up.gvas)
    print(f"parser     {'byte-exact' if savefile.serialize(data) == up.gvas else 'MISMATCH'}")
    print(f"sha256     {safety.sha256_file(p)}")


def cmd_lives(args):
    sf = _load(args)
    print(f"{'id':9} {'name (unverified)':20} {'lv':>5} {'exp':>10} {'rank':>4} {'star':>4}")
    for l in sf.lives():
        print(f"{l['id']:9} {l['name']:20} {l['level']:>5} {l['exp']:>10} {l['rank']:>4} {l['star']:>4}")


def cmd_items(args):
    sf = _load(args)
    names = savefile.load_item_names()
    for it in sf.items(args.category):
        stock = "" if it.stock is None else f"x{it.stock}"
        print(f"{it.category:26} {it.index:5} {it.item_id:16} {stock:7} {names.get(it.item_id, '')}")


def cmd_find_item(args):
    q = args.query.lower()
    for k, v in savefile.load_item_names().items():
        if q in k.lower() or q in v.lower():
            print(f"{k:16} {v}")


def cmd_set_money(args):
    sf = _load(args)
    old = sf.money
    sf.money = args.value
    print(f"money {old} -> {sf.money}")
    _finish(sf, args)


def cmd_set_name(args):
    sf = _load(args)
    old = sf.character_name
    sf.character_name = args.name
    print(f"name {old} -> {sf.character_name}")
    _finish(sf, args)


def cmd_set_life(args):
    sf = _load(args)
    sf.set_life(args.life_id, level=args.level, exp=args.exp, rank=args.rank)
    print(next(l for l in sf.lives() if l["id"] == args.life_id))
    _finish(sf, args)


def cmd_set_stock(args):
    sf = _load(args)
    sf.set_stock(args.category, args.index, args.stock)
    print(f"{args.category}[{args.index}] stock -> {args.stock}")
    _finish(sf, args)


def cmd_add_item(args):
    sf = _load(args)
    idx = sf.add_item(args.category, args.item_id, args.stock)
    print(f"added {args.item_id} x{args.stock} to {args.category}[{idx}]")
    _finish(sf, args)


def cmd_unpack(args):
    up = container.unpack(Path(args.input).read_bytes(), container.load_key())
    Path(args.output).write_bytes(up.gvas)
    print(f"wrote {args.output} ({len(up.gvas)} bytes)")


def cmd_pack(args):
    out = Path(args.output)
    if out.resolve() in {p.resolve() for p in paths.candidate_save_paths()}:
        sys.exit("refusing to pack straight onto a live save; use import-json or an edit command")
    out.write_bytes(container.pack(Path(args.input).read_bytes(), container.load_key()))
    print(f"wrote {out}")


def cmd_export_json(args):
    sf = _load(args)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(sf.data, f, indent=1, ensure_ascii=False)
    print(f"wrote {args.output}")


def cmd_import_json(args):
    sf = _load(args)
    with open(args.input, encoding="utf-8") as f:
        sf.data = json.load(f)
    sf.dirty = True
    _finish(sf, args)


def cmd_backup(args):
    print(safety.backup(_save_path(args), args.reason))


def cmd_restore(args):
    src = Path(args.backup_file)
    target = _save_path(args)
    safety.require_game_closed()
    container.unpack(src.read_bytes(), container.load_key())
    pre = safety.backup(target, "before-restore") if target.exists() else None
    safety.atomic_write(target, src.read_bytes())
    print(f"restored {src} -> {target}\n  previous file backed up to {pre}")


def cmd_live(args):
    b = live.LiveBridge()
    verb = args.verb
    if verb == "status":
        print("mod heartbeat:", "alive" if b.mod_alive() else "none")
        print("game processes:", ", ".join(safety.running_game_processes()) or "none")
        return
    fn = {"ping": lambda: b.ping(), "find": lambda: b.find_prop(args.args[0]),
          "get": lambda: b.get(args.args[0], args.args[1]),
          "set": lambda: b.set(args.args[0], args.args[1], args.args[2]),
          "props": lambda: b.list_props(args.args[0])}[verb]
    r = fn()
    print(("OK  " if r.ok else "ERR ") + r.text.replace(" | ", "\n    "))


def cmd_where(args):
    if args.game_dir:
        print(paths.game_dir())
        return
    roots = steam.find_steam_roots()
    print("steam      " + (", ".join(map(str, roots)) or "not found"))
    games = steam.find_game_dirs()
    print("game       " + (", ".join(map(str, games)) or "not found"))
    saves = steam.find_saves()
    if not saves:
        print("saves      none found")
    for i, s in enumerate(saves):
        who = f"account {s.account_id}" + (f" ({s.persona})" if s.persona else "") if s.account_id else s.kind
        tag = "  <- default" if i == 0 and not os.environ.get(steam.ENV_SAVE) else ""
        print(f"save       {s.path}  [{who}{', most recent login' if s.most_recent_user else ''}]{tag}")
    for env in (steam.ENV_STEAM, steam.ENV_GAME, steam.ENV_SAVE):
        if os.environ.get(env):
            print(f"override   {env}={os.environ[env]}")


def cmd_gui(args):
    from . import gui
    try:
        p = _save_path(args)
    except paths.NotFound:
        p = None
    gui.main(p)


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="stolenhours", description="Fantasy Life i save editor (Stolen Hours)")
    ap.add_argument("--save", help="save file (default: auto-detected, see `where`)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def edit(name, fn, help_):
        p = sub.add_parser(name, help=help_)
        p.add_argument("--dry-run", action="store_true", help="pack and verify only, write nothing")
        p.add_argument("--out", help="write to this file instead of the loaded save")
        p.set_defaults(fn=fn)
        return p

    sub.add_parser("info", help="summary of the save").set_defaults(fn=cmd_info)
    sub.add_parser("verify", help="decrypt + byte-exact roundtrip checks").set_defaults(fn=cmd_verify)
    sub.add_parser("lives", help="life levels").set_defaults(fn=cmd_lives)
    p = sub.add_parser("items", help="list inventory"); p.add_argument("category", nargs="?"); p.set_defaults(fn=cmd_items)
    p = sub.add_parser("find-item", help="search the item name list"); p.add_argument("query"); p.set_defaults(fn=cmd_find_item)

    p = edit("set-money", cmd_set_money, "set Dosh"); p.add_argument("value", type=int)
    p = edit("set-name", cmd_set_name, "set character name"); p.add_argument("name")
    p = edit("set-life", cmd_set_life, "set level/exp/rank of one life")
    p.add_argument("life_id"); p.add_argument("--level", type=int); p.add_argument("--exp", type=int); p.add_argument("--rank", type=int)
    p = edit("set-stock", cmd_set_stock, "set stack size of an inventory slot")
    p.add_argument("category"); p.add_argument("index", type=int); p.add_argument("stock", type=int)
    p = edit("add-item", cmd_add_item, "add an item to an inventory category")
    p.add_argument("category"); p.add_argument("item_id"); p.add_argument("stock", type=int, nargs="?", default=1)
    p = edit("import-json", cmd_import_json, "replace save contents from exported JSON"); p.add_argument("input")

    p = sub.add_parser("export-json", help="dump the parsed save to JSON"); p.add_argument("output"); p.set_defaults(fn=cmd_export_json)
    p = sub.add_parser("unpack", help=".bin -> raw GVAS"); p.add_argument("input"); p.add_argument("output"); p.set_defaults(fn=cmd_unpack)
    p = sub.add_parser("pack", help="raw GVAS -> .bin (not onto a live save)"); p.add_argument("input"); p.add_argument("output"); p.set_defaults(fn=cmd_pack)
    p = sub.add_parser("backup", help="back up the save with SHA-256"); p.add_argument("--reason", default="manual"); p.set_defaults(fn=cmd_backup)
    p = sub.add_parser("restore", help="restore a backup .bin over the save"); p.add_argument("backup_file"); p.set_defaults(fn=cmd_restore)
    p = sub.add_parser("live", help="Mode B: talk to the in-game mod")
    p.add_argument("verb", choices=["status", "ping", "find", "get", "set", "props"]); p.add_argument("args", nargs="*")
    p.set_defaults(fn=cmd_live)
    p = sub.add_parser("where", help="show the detected Steam, game and save locations")
    p.add_argument("--game-dir", action="store_true", help="print only the game folder (for scripts)")
    p.set_defaults(fn=cmd_where)
    sub.add_parser("gui", help="desktop editor").set_defaults(fn=cmd_gui)
    return ap


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        args.fn(args)
    except (container.ContainerError, savefile.SaveFileError, safety.SafetyError, live.LiveError,
            paths.NotFound) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 0
