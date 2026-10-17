#!/usr/bin/env bash
# Stolen Hours on a Steam Deck (or any Linux PC with Steam). See STEAM_DECK.txt.
# Runs StolenHours.exe through Proton as the editor's engine and shows the editor full screen in a browser, so it
# works in Game Mode with the Deck's controls or an Xbox / PlayStation controller.
#
# Optional settings (environment, or Steam launch options such as  STOLENHOURS_PORT=47615 %command%):
#   STOLENHOURS_PROTON   the proton script to use      STOLENHOURS_BROWSER  browser command (gets the URL last)
#   STOLENHOURS_PORT     local port for the editor

set -u
HERE="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
EXE="$HERE/StolenHours.exe"
DATA="${XDG_DATA_HOME:-$HOME/.local/share}/StolenHours"
LOG="$DATA/deck.log"
mkdir -p "$DATA/compat"
exec > >(tee "$LOG") 2>&1

say() {  # a message box that also shows in Game Mode
  echo "$*"
  if command -v zenity >/dev/null 2>&1; then zenity --error --title="Stolen Hours" --width=460 --text="$*" 2>/dev/null
  elif command -v kdialog >/dev/null 2>&1; then kdialog --title "Stolen Hours" --error "$*" 2>/dev/null
  fi
}

[ -f "$EXE" ] || { say "StolenHours.exe isn't next to this script ($HERE)."; exit 1; }

STEAM=""
for s in "$HOME/.local/share/Steam" "$HOME/.var/app/com.valvesoftware.Steam/.local/share/Steam" "$HOME/.steam/steam"; do
  if [ -d "$s/steamapps" ]; then STEAM="$(readlink -f "$s")"; break; fi
done
[ -n "$STEAM" ] || { say "Steam's folder wasn't found under $HOME."; exit 1; }

libraries() {
  echo "$STEAM"
  sed -n 's/^[[:space:]]*"path"[[:space:]]*"\(.*\)".*/\1/p' "$STEAM/steamapps/libraryfolders.vdf" 2>/dev/null
}

find_proton() {  # newest numbered Proton, else Experimental, else a custom one (GE etc.)
  if [ -n "${STOLENHOURS_PROTON:-}" ]; then echo "$STOLENHOURS_PROTON"; return; fi
  local lib p
  while IFS= read -r lib; do
    for p in "$lib"/steamapps/common/Proton\ [0-9]*/proton; do
      [ -f "$p" ] && printf '%s\t%s\n' "$(basename "$(dirname "$p")")" "$p"
    done
  done < <(libraries) | sort -t $'\t' -k1,1V | tail -n 1 | cut -f 2 | grep . && return
  while IFS= read -r lib; do
    p="$lib/steamapps/common/Proton - Experimental/proton"
    [ -f "$p" ] && { echo "$p"; return; }
  done < <(libraries)
  for p in "$STEAM"/compatibilitytools.d/*/proton; do
    [ -f "$p" ] && { echo "$p"; return; }
  done
}

PROTON="$(find_proton)"
if [ -n "$PROTON" ]; then
  export STEAM_COMPAT_DATA_PATH="$DATA/compat" STEAM_COMPAT_CLIENT_INSTALL_PATH="$STEAM"
  RUN=("$PROTON" run)
  WINESERVER="$(dirname "$PROTON")/files/bin/wineserver"
  [ -x "$WINESERVER" ] || WINESERVER="$(dirname "$PROTON")/dist/bin/wineserver"
elif command -v wine >/dev/null 2>&1; then
  export WINEPREFIX="$DATA/compat/pfx"
  RUN=(wine)
  WINESERVER="$(command -v wineserver || true)"
else
  say "Proton wasn't found. In Steam, open the Library, search for Proton, install Proton Experimental (or any Proton), then start Stolen Hours again."
  exit 1
fi
echo "steam: $STEAM"
echo "runner: ${RUN[*]}"
export WINEDEBUG=-all
export STOLENHOURS_STEAM_DIR="Z:${STEAM//\//\\}"

PORT="${STOLENHOURS_PORT:-$(( 30000 + RANDOM % 20000 ))}"
TOKEN="$(od -An -N16 -tx1 /dev/urandom | tr -d ' \n')"
URL="http://127.0.0.1:$PORT/?t=$TOKEN"

ZEN=""
if command -v zenity >/dev/null 2>&1; then
  coproc zenity --progress --pulsate --no-cancel --title="Stolen Hours" --width=420 \
    --text="Starting the editor...\nThe first start sets up Proton and can take a minute." 2>/dev/null
  ZEN="${COPROC_PID:-}"
fi
stop_progress() { [ -n "$ZEN" ] && kill "$ZEN" 2>/dev/null; ZEN=""; }

BACK=""
cleanup() {
  stop_progress
  [ -n "$BACK" ] && kill "$BACK" 2>/dev/null
  # ends only the Wine processes of the editor's own prefix
  [ -n "$WINESERVER" ] && [ -x "$WINESERVER" ] && WINEPREFIX="$DATA/compat/pfx" "$WINESERVER" -k 2>/dev/null
}
trap cleanup EXIT
trap 'exit 130' INT TERM

"${RUN[@]}" "$EXE" --serve "$PORT" "$TOKEN" &
BACK=$!

up() { (exec 3<>"/dev/tcp/127.0.0.1/$PORT") 2>/dev/null; }
for _ in $(seq 1 360); do
  up && break
  if ! kill -0 "$BACK" 2>/dev/null; then
    stop_progress; say "The editor stopped while starting. Details are in $LOG"; exit 1
  fi
  sleep 0.5
done
up || { stop_progress; say "The editor didn't start within three minutes. Details are in $LOG"; exit 1; }
stop_progress
echo "editor up on port $PORT"

udev_access() {  # a flatpak browser sees controllers only with /run/udev (Valve's cloud-gaming guide does the same)
  flatpak override --user --show "$1" 2>/dev/null | grep -q '/run/udev' || flatpak override --user --filesystem=/run/udev:ro "$1"
}

open_browser() {
  if [ -n "${STOLENHOURS_BROWSER:-}" ]; then
    # shellcheck disable=SC2086  # the setting is a command line
    $STOLENHOURS_BROWSER "$URL"; return
  fi
  local id c
  if command -v flatpak >/dev/null 2>&1; then
    for id in com.microsoft.Edge com.google.Chrome org.chromium.Chromium com.brave.Browser; do
      if flatpak info "$id" >/dev/null 2>&1; then
        udev_access "$id"
        flatpak run "$id" --user-data-dir="$HOME/.var/app/$id/data/stolenhours" --no-first-run --noerrdialogs \
          --disable-features=Translate --kiosk --app="$URL"
        return
      fi
    done
    if flatpak info org.mozilla.firefox >/dev/null 2>&1; then
      udev_access org.mozilla.firefox
      mkdir -p "$HOME/.var/app/org.mozilla.firefox/data/stolenhours"
      flatpak run org.mozilla.firefox --new-instance --profile "$HOME/.var/app/org.mozilla.firefox/data/stolenhours" \
        --kiosk "$URL"
      return
    fi
  fi
  for c in microsoft-edge google-chrome chromium chromium-browser brave; do
    if command -v "$c" >/dev/null 2>&1; then
      "$c" --user-data-dir="$DATA/browser" --no-first-run --noerrdialogs --kiosk --app="$URL"; return
    fi
  done
  if command -v firefox >/dev/null 2>&1; then
    mkdir -p "$DATA/firefox"; firefox --new-instance --profile "$DATA/firefox" --kiosk "$URL"; return
  fi
  say "No web browser found. In Desktop Mode open Discover, install Google Chrome or Microsoft Edge, then start Stolen Hours again."
  return 1
}

open_browser
