"""Syntax-check Lua files with lupa (no UE4SS needed). usage: py -3.12 research/lua_check.py <file.lua>..."""
import sys

import lupa

check = lupa.LuaRuntime().eval("function(s, n) local f, e = load(s, n); return f and 'ok' or e end")
bad = 0
for path in sys.argv[1:]:
    res = check(open(path, encoding="utf-8").read(), "@" + path)
    print(path, res)
    bad += res != "ok"
sys.exit(bad)
