# Findings: blueprint vs. the real game

Verified facts only. Each entry: date, what was checked, result.

## 2026-10-11 (setup, read-only checks)

| Blueprint says | Real game | Status |
|---|---|---|
| Save dir `C:\Program Files (x86)\Steam\userdata\<id>\2993780\remote\` | `C:\Null\Grave\userdata\235938730\2993780\remote\` (custom Steam path) | Verified |
| Two save files: `gamedata.bin`, `systemdata.bin` | Only `002DAE74-00-gamedata.bin` exists (153,360 bytes). No `systemdata.bin`. | Verified |
| Binary `FLiGame\Binaries\Win64\FLiGame-Win64-Shipping.exe` | `Game\Binaries\Win64\NFL1-Win64-Shipping.exe` (project name `NFL1`) | Verified |
| Save class `/Script/FLiGame.FLiSaveGameInstance` | Module is probably `NFL1`, not `FLiGame` | UNVERIFIED: confirm from decrypted GVAS or binary strings |
| Header magic `L5SV` at 0x00, plaintext 64-byte header | First 64 bytes look like ciphertext: `2D C8 0A E1 D0 FA FD B9 ...`. No `L5SV`, no readable sizes at 0x24/0x28. | Blueprint layout **not matched** |
| Payload at 0x40, PKCS#7-padded | File size 153,360 = 16 x 9,585: whole file is 16-byte aligned, consistent with whole-file block encryption | Observation, not proof |
| Header field 0x2C, 20 bytes, "SHA-256" | A SHA-256 is 32 bytes; 20 bytes would be SHA-1. Internal inconsistency in the blueprint. | Blueprint error |
| (not mentioned) | Game ships Easy Anti-Cheat (`EasyAntiCheat\`, `EACLauncher.exe`, Epic Online Services) | Verified |

Backup of the save taken before any work: `backups\saves\2026-10-11_initial\` (SHA-256 `D2CAF0A8...CDF2A3`).

## First real research steps
1. Entropy/structure scan of the whole save to confirm it is encrypted end to end.
2. Find the save routine in `NFL1-Win64-Shipping.exe` (static analysis, read-only copy) and identify the actual cipher, key and compression.
3. Look for existing community work on this game's save format before reinventing it.
