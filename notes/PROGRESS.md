# Progress

## 2026-10-11: Project set up (by Watchtower)
- Folder, agent rule (Tock), README, blueprint, findings, workspace file created.
- Save backed up to `backups\saves\2026-10-11_initial\` with SHA-256.
- Read-only checks found the blueprint's container header, file paths and file list do not match the real game. See `docs\FINDINGS.md`.
- Nothing written to the game install or the live save.
- Unholy removed the anti-cheat restriction from the rules; this is a personal save editor.

## 2026-10-11: Format solved, Mode A built (Tock)
- Container: AES-256-ECB + PKCS#7 over `u32 size | zlib | footer(u32 1, MD5, 14 zero)`. Repack is byte-exact on the real save.
- Body: native serialization of `/Script/DP1Project.SaveData`, parsed with the community pattern file; byte-exact.
- `editor\stolenhours`: CLI + Tk GUI. Dosh, name, life level/exp/rank, item stock, add item, JSON export/import,
  backup/restore. Game-running lock, SHA-256 backup before every write, verify-after-pack, atomic replace.
- 19 tests pass (`editor\tests`). Fast serializer (bytearray) replaces the community one: load+verify ~4 s instead of ~24 s.
- Mode B: UE4SS Lua mod (`hook\ue4ss_mod\StolenHours`) + file mailbox client. Blueprint ProcessEvent signature has
  0 hits in the binary, so the hand-written proxy DLL was dropped in favour of UE4SS reflection.
- Live save not written.
- With Unholy's OK, ran `hook\install_live.ps1`: GameBootstrapper.ini now launches `NFL1-Win64-Shipping.exe` (EAC skipped),
  UE4SS + StolenHours mod installed in `Game\Binaries\Win64`. Original ini backed up to
  `backups\game_install\2026-10-11_194144\` (SHA-256 `DD2A5155...7204D1`). Undo: `hook\install_live.ps1 -Uninstall`.
  A Steam update or "verify files" will undo the ini change.

## 2026-10-11: Portable path discovery (Tock)
- `editor\stolenhours\steam.py`: Steam root from registry (drive scan only as fallback), libraries from
  `libraryfolders.vdf`, game from `appmanifest_2993780.acf` / shipping exe, saves per account with
  `loginusers.vdf` to pick the default. Env overrides. `where` command; GUI save dropdown; install script auto-detects.
- 9 new tests on fake Steam layouts (other drive, renamed folder, old VDF format, no registry, no Steam). 28 total pass.

## Next
- Unholy: first real edit (e.g. `set-money`), launch, confirm Dosh in game. Then try `add-item`.
- Unholy: compare the Life menu with `StolenHours.cmd lives` to confirm life id names.
- Unholy: launch through Steam, load the save. Then Tock reads `ue4ss\UE4SS.log` and runs `live ping`, `live find Money`.
- Map `m_AvatarStatus` (appearance) once the above works.
