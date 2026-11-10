# Stolen Hours

Save editor and live runtime controller for **Fantasy Life i: The Girl Who Steals Time** (Steam app 2993780).
Agent: **Tock** (rules in `.cursor\rules\tock.mdc`). Watchtower ID: WT-026.

**Engine RE peer:** station **Loom** (WT-037) lives at `agents\Loom\` — deep UE/engine understanding (Cipher Bench toolbelt shared). Tock keeps editor + Live; Loom does not own the product UI. Workspace: `G:\Cursor\Work Projects\Fantasy Life i - Loom (Engine RE).code-workspace`.

## Goal
- **Mode A, game closed:** unpack `gamedata.bin`, edit properties (Dosh, Lives, stats, inventory, appearance), repack, write back.
- **Mode B, game running:** the editor locks file writes and sends commands to an in-game component that applies them on the game thread.

Full brief: `docs\BLUEPRINT.md`. What is actually confirmed: `docs\FINDINGS.md`.

## Use
Needs Python 3.12 (`py -3.12 -m pip install -r editor\requirements.txt`), the key in `research\private\aes_key.hex`,
and the community tools in `tools\` (see `tools\README.md`).

| Command | Does |
|---|---|
| `StolenHours.cmd` | Desktop editor (Overview, Lives, Inventory, Live tabs) |
| `StolenHours.cmd verify` | Decrypt + byte-exact roundtrip checks on the live save |
| `StolenHours.cmd info` / `lives` / `items [category]` / `find-item <text>` | Read-only views |
| `StolenHours.cmd set-money 500000` | Edit Dosh (also `set-name`, `set-life`, `set-stock`, `add-item`) |
| `StolenHours.cmd export-json x.json` / `import-json x.json` | Full save as JSON, for anything the UI doesn't cover |
| `StolenHours.cmd backup` / `restore <file>` | Manual backup / restore |
| `StolenHours.cmd live status|ping|find|get|set|props ...` | Mode B |

Edits add `--dry-run` (pack and verify only) or `--out file.bin`. Every write: refuses if the game is running,
re-verifies the packed output, backs up the current save with SHA-256 to `backups\saves\`, then replaces it atomically.
A save is only editable if decrypt/repack and parse/reserialize are both byte-exact.

Tests: `cd editor; py -3.12 -m pytest -q tests`

## Mode B setup (changes the game folder)
`hook\install_live.ps1` backs up what it touches to `backups\game_install\`, switches Steam launch to skip EAC,
installs UE4SS and the `StolenHours` Lua mod. `-Uninstall` reverts it. Then in game: `live ping`, `live find Money`,
`live set <object path> Money 500000`.

## Finding Steam, the game and the save on any PC
Nothing is hardcoded. `StolenHours.cmd where` shows what was detected:
- Steam: registry (`HKCU\Software\Valve\Steam\SteamPath`, then HKLM `InstallPath`). Only if that fails, common
  folders on every drive (`Program Files (x86)\Steam`, `X:\Steam`, `X:\Games\Steam`).
- Game: every library in `steamapps\libraryfolders.vdf` (new and old format), `installdir` from
  `appmanifest_2993780.acf`, else any `steamapps\common\*` folder holding `Game\Binaries\Win64\NFL1-Win64-Shipping.exe`,
  else `X:\SteamLibrary` style folders on every drive. Renamed folders and other drives are fine.
- Save: `userdata\<account>\2993780\remote\*gamedata.bin` for every account. Default is the most recent
  Steam login (`config\loginusers.vdf`), then the newest file. Direct-launch saves
  (`%LOCALAPPDATA%\Game\Saved\SaveGames`) are listed after Steam ones. The GUI dropdown lists all of them.
- Overrides: `STOLENHOURS_STEAM_DIR`, `STOLENHOURS_GAME_DIR`, `STOLENHOURS_SAVE`, or `--save` / `-GameDir`.
- Under Proton (Steam Deck): also `~/.local/share/Steam` and flatpak Steam through `Z:`, Linux library paths
  mapped to `Z:`, and the game-running check reads `/proc` (`stolenhours\deck.py`).

## Portable Windows exe (any PC)
Current release: **0.6.1** — Live Map (Ginormosia events + spawn control with mod 0.8.2), Bag beyond-normal gear
editor, fuller Village / Base Camp packs. Hand someone the zip folder (`StolenHours.exe` + `_internal` +
`START HERE.txt`). It does **not** ship Unholy’s paths, Steam id, or keys. On their PC it finds Steam /
Fantasy Life i / saves itself and reads the save key from **their** game install.

**Brother test (yes, this is the point):**
1. Unzip anywhere → double-click **`StolenHours.exe`**. No console, no Python, no “run as admin.”
2. Needs: Windows + a Steam Fantasy Life i install + at least one save (play once).
3. If **Microsoft Edge WebView2 Runtime** is missing, it says so and offers the official install (or continue in
   the normal browser — same editor).
4. Windows download-block (Mark of the Web) is cleared automatically on launch.
5. Live Map is optional: close the game → Live Map → **Install Live setup** once → start game → load save.

Useful flags: `--check` (setup checklist), `--browser` (force browser UI).

On first run it checks what this PC has:

| Check | If missing |
|---|---|
| **Edge WebView2 Runtime** (recommended) | Editor offers the official Evergreen installer link, then asks you to reopen Stolen Hours. Without it, it opens in your browser instead of a native window. |
| **.NET Framework 4.8** | Only needed for a legacy UI path; browser / WebView2 mode works without it. |
| **A web browser** | Required fallback UI — install Edge/Chrome/Firefox if somehow none is available. |
| **Fantasy Life i + a save** | Soft warning: install/play once so the editor can find a save and the AES key. |

Useful flags:

| Flag | Does |
|---|---|
| `StolenHours.exe --check` | Print / show the setup checklist (`%LOCALAPPDATA%\StolenHours\setup_check.txt`) |
| `StolenHours.exe --browser` | Skip the native window; always use the system browser |
| `StolenHours.exe --selftest` | Write discovery + roundtrip results to `%LOCALAPPDATA%\StolenHours\selftest.txt` |

If you see a crash about `Python.Runtime.dll` / pythonnet: install WebView2, or run with `--browser`.

## Steam Deck
The exe build ships `StolenHours-Deck.sh` and `STEAM_DECK.txt`: add the script as a non-Steam game; it runs the exe
through Proton and opens the editor full screen in a browser for Game Mode. Controller and keyboard navigation
(`web\pad.js`) work everywhere, Windows too. Launcher dry run: `wsl bash research/deck_launcher_check.sh`.

## Locations on Unholy's PC (checked 2026-10-11)
| What | Path |
|---|---|
| Save folder | `C:\Null\Grave\userdata\235938730\2993780\remote\` (Steam is installed at `C:\Null\Grave`) |
| Save file | `002DAE74-00-gamedata.bin` (153,360 bytes) |
| Game install | `D:\SteamLibrary\steamapps\common\FANTASY LIFE i\` |
| Shipping binary | `Game\Binaries\Win64\NFL1-Win64-Shipping.exe` (217.5 MB) |
| Live mailbox | `%LOCALAPPDATA%\StolenHours\live\` |

## Layout
| Folder | Holds |
|---|---|
| `docs\` | Blueprint, findings |
| `notes\` | `PROGRESS.md` |
| `editor\` | `stolenhours` package: container codec, save model, safety, CLI, Tk GUI, live client; `tests\` |
| `hook\` | Mode B: UE4SS Lua mod (`ue4ss_mod\StolenHours`) and `install_live.ps1` |
| `research\` | Format notes, dumps; `research\private\` for extracted keys (git-ignored) |
| `tools\` | Third-party tools (git-ignored; source and license in `tools\README.md`) |
| `backups\` | Save and game-file backups, one dated folder each, with SHA-256 |
