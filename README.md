# Stolen Hours

Save editor and live runtime controller for **Fantasy Life i: The Girl Who Steals Time** (Steam app 2993780).
Agent: **Tock** (rules in `.cursor\rules\tock.mdc`). Watchtower ID: WT-026.

## Goal
- **Mode A, game closed:** unpack `gamedata.bin`, edit properties (Dosh, Lives, stats, inventory, appearance), repack, write back.
- **Mode B, game running:** the editor locks file writes and sends commands over a named pipe to an in-game DLL that applies them on the game thread.

Full brief: `docs\BLUEPRINT.md`. What is actually confirmed: `docs\FINDINGS.md`.

## Real locations (checked 2026-10-11)
| What | Path |
|---|---|
| Save folder | `C:\Null\Grave\userdata\235938730\2993780\remote\` (Steam is installed at `C:\Null\Grave`) |
| Save file | `002DAE74-00-gamedata.bin` (153,360 bytes) |
| Game install | `D:\SteamLibrary\steamapps\common\FANTASY LIFE i\` |
| Shipping binary | `Game\Binaries\Win64\NFL1-Win64-Shipping.exe` (217.5 MB) |

## Layout
| Folder | Holds |
|---|---|
| `docs\` | Blueprint, findings |
| `notes\` | `PROGRESS.md` |
| `editor\` | Desktop editor (offline save pipeline + UI + pipe client) |
| `hook\` | In-game proxy DLL (Mode B) |
| `research\` | Format notes, dumps; `research\private\` for extracted keys (git-ignored) |
| `tools\` | Third-party tools (record source and license) |
| `backups\saves\` | Save backups, one dated folder each, with SHA-256 |
