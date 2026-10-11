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
- UE4SS downloaded to `tools\ue4ss`; NOT installed. `hook\install_live.ps1` ready, waiting on Unholy's OK.
- Live save not written. Game install not modified.

## Next
- Unholy: first real edit (e.g. `set-money`), launch, confirm Dosh in game. Then try `add-item`.
- Unholy: compare the Life menu with `StolenHours.cmd lives` to confirm life id names.
- After OK: run `hook\install_live.ps1`, launch through Steam, check `ue4ss\UE4SS.log`, then `live ping` and `live find Money`.
- Map `m_AvatarStatus` (appearance) once the above works.
