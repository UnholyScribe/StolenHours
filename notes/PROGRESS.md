# Progress

## 2026-10-11: Project set up (by Watchtower)
- Folder, agent rule (Tock), README, blueprint, findings, workspace file created.
- Save backed up to `backups\saves\2026-10-11_initial\` with SHA-256.
- Read-only checks found the blueprint's container header, file paths and file list do not match the real game. See `docs\FINDINGS.md`.
- Nothing written to the game install or the live save.

## Next
- Research phase: identify the real save encryption from the file and the shipping binary (see `docs\FINDINGS.md`).
- Open decision for Unholy: how Mode B (live DLL) should work given Easy Anti-Cheat is present.
