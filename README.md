# Stolen Hours

Save editor and live runtime controller for **Fantasy Life i: The Girl Who Steals Time** (Steam app 2993780).
Agent: **Tock** (rules in `.cursor\rules\tock.mdc`). Watchtower ID: WT-026.

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

## Real locations (checked 2026-10-11)
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
