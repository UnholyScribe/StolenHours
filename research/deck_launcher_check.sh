#!/usr/bin/env bash
# Dry run of editor/deck/StolenHours-Deck.sh on any Linux (WSL is fine): fake Steam home, a stub "proton" that serves
# HTTP instead of running the exe, a stub browser. Checks Proton choice, startup wait, URL handoff and cleanup.
set -u
SRC="$(cd "$(dirname "$0")/../editor/deck" && pwd)"
T="$(mktemp -d)"
export HOME="$T/home" XDG_DATA_HOME="$T/home/.local/share"
STEAM="$HOME/.local/share/Steam"
mkdir -p "$STEAM/steamapps" "$T/app" "$T/sd/steamapps/common"
printf '"libraryfolders"\n{\n\t"0"\n\t{\n\t\t"path"\t\t"%s"\n\t}\n\t"1"\n\t{\n\t\t"path"\t\t"%s"\n\t}\n}\n' "$STEAM" "$T/sd" \
  > "$STEAM/steamapps/libraryfolders.vdf"
cp "$SRC/StolenHours-Deck.sh" "$T/app/" && touch "$T/app/StolenHours.exe" && chmod +x "$T/app/StolenHours-Deck.sh"

for v in "Proton 8.0" "Proton 10.0" "Proton 9.0 (Beta)"; do
  d="$T/sd/steamapps/common/$v"; mkdir -p "$d/files/bin"
  cat > "$d/proton" <<EOF
#!/usr/bin/env bash
echo "\$STEAM_COMPAT_DATA_PATH" > "$T/compat_used"; echo "$v" > "$T/proton_used"; echo "\$STOLENHOURS_STEAM_DIR" > "$T/steam_dir"
shift 2; port="\$2"; sleep 1; exec python3 -m http.server "\$port" --bind 127.0.0.1 >/dev/null 2>&1
EOF
  printf '#!/usr/bin/env bash\necho "$WINEPREFIX $*" > "%s/wineserver_called"\npkill -f "http.server" || true\n' "$T" > "$d/files/bin/wineserver"
  chmod +x "$d/proton" "$d/files/bin/wineserver"
done

printf '#!/usr/bin/env bash\ncurl -fsS -o /dev/null "$1" && echo "$1" > "%s/url_opened"\n' "$T" > "$T/browser"
chmod +x "$T/browser"
STOLENHOURS_BROWSER="$T/browser" PATH="/usr/bin:/bin" bash "$T/app/StolenHours-Deck.sh"
rc=$?
fail=0
check() { if eval "$2"; then echo "ok   $1"; else echo "FAIL $1"; fail=1; fi; }
check "script exit 0 (got $rc)" '[ $rc -eq 0 ]'
check "newest numbered Proton picked: $(cat "$T/proton_used" 2>/dev/null)" '[ "$(cat "$T/proton_used")" = "Proton 10.0" ]'
check "own compat folder" '[ "$(cat "$T/compat_used")" = "$XDG_DATA_HOME/StolenHours/compat" ]'
check "Steam dir handed over as Z: path: $(cat "$T/steam_dir")" 'grep -q "^Z:\\\\" "$T/steam_dir"'
check "browser got a live URL with token: $(cat "$T/url_opened" 2>/dev/null)" 'grep -Eq "^http://127.0.0.1:[0-9]+/\?t=[0-9a-f]{32}$" "$T/url_opened"'
check "editor prefix shut down: $(cat "$T/wineserver_called" 2>/dev/null)" 'grep -q "compat/pfx -k" "$T/wineserver_called"'
check "log written" '[ -s "$XDG_DATA_HOME/StolenHours/deck.log" ]'
rm -rf "$T"
exit $fail
