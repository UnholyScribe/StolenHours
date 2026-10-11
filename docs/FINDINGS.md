# Findings: blueprint vs. the real game

Verified facts only. Each entry: date, what was checked, result.

## 2026-10-11 (setup, read-only checks)

| Blueprint says | Real game | Status |
|---|---|---|
| Save dir `C:\Program Files (x86)\Steam\userdata\<id>\2993780\remote\` | `C:\Null\Grave\userdata\235938730\2993780\remote\` (custom Steam path) | Verified |
| Two save files: `gamedata.bin`, `systemdata.bin` | Only `002DAE74-00-gamedata.bin` exists (153,360 bytes). No `systemdata.bin`. | Verified |
| Binary `FLiGame\Binaries\Win64\FLiGame-Win64-Shipping.exe` | `Game\Binaries\Win64\NFL1-Win64-Shipping.exe` (project name `NFL1`) | Verified |
| (not mentioned) | Game ships Easy Anti-Cheat (`EasyAntiCheat\`, `EACLauncher.exe`, Epic Online Services) | Verified |

Backup of the save taken before any work: `backups\saves\2026-10-11_initial\` (SHA-256 `D2CAF0A8...CDF2A3`).

## 2026-10-11 (save format, solved)

Evidence: the backed-up save, the shipping binary (read-only), and the community tools
[Niedzielan/fli_save_editor](https://github.com/Niedzielan/fli_save_editor) and
[uesave-rs issue #69](https://github.com/trumank/uesave-rs/issues/69). Reproduced by `editor\tests`.

| Blueprint says | Real game | Status |
|---|---|---|
| 64-byte plaintext header, magic `L5SV`, 32-byte seed | No header. Whole file is ciphertext from offset 0. | Blueprint wrong |
| Layer 1: cyclic XOR `A4 6A 8F F1` | Not present | Blueprint wrong |
| Layer 2: AES-128-ECB, static key | **AES-256-ECB**, static 32-byte key (in `research\private\aes_key.hex`). Independent sign before the key was known: 2,084 duplicate 16-byte blocks at 16-byte alignment = ECB over repetitive plaintext. | Verified |
| Layer 3: AES-256 counter keystream XOR from seed | Not present (would have destroyed the duplicate blocks) | Blueprint wrong |
| Oodle Kraken compression | **zlib** (`78 9C`), level 6, memLevel 8, wbits 15: recompression is byte-identical | Verified |
| PKCS#7 padding | PKCS#7, yes (sample ends in 11 x `0B`) | Verified |
| 20-byte "SHA-256" at 0x2C | 34-byte **footer** after the zlib stream: `u32 1`, `MD5(u32 size + zlib stream)`, 14 x `00` | Verified |
| GVAS header, UE 5.4 | `GVAS`, SaveGameVersion 3, UE4 522, UE5 1012, engine 5.4.4, 120 custom versions | Verified |
| Save class `/Script/FLiGame.FLiSaveGameInstance` | `/Script/DP1Project.SaveData` (`DP1Project` also appears in the binary) | Verified |
| Tagged properties, `None` terminators | **Not tagged.** After the class name the body is native field-by-field serialization. Generic GVAS parsers (uesave) fail on it. Parsed with the community pattern file; parse + reserialize is byte-exact on the sample. | Verified |
| `CharacterData.Dosh` (Int64) | `saveData.m_PlayData.Money`, **s32** (sample: 14,633) | Verified |
| `LifeStats` map | `m_CharaStatus.m_stAvatarP[0]`: `m_lv` Map<Name,u16>, `m_exp` Map<Name,u32>, `m_lifeStatus` (licenseRank, star, skillMaxPoint); ids `life0000`-`life0014` | Verified (structure). Id-to-life-name mapping UNVERIFIED: check by comparing the in-game Life menu with `stolenhours lives` |
| `InventoryData.Items` (Quantity Int32, Quality Byte) | `m_InventoryStatus.inv*` fixed-size arrays per category; stackables have `stockNum` **u16**; equipment has `Quality` enum, no stack | Verified |
| `AppearanceData` mesh/colour arrays | Not mapped yet (`m_AvatarStatus` exists) | UNVERIFIED |

Sample totals: gvas 8,098,851 bytes, zlib 153,311 bytes, 142 items, character "N30Killer", island "Grimfang".

Open questions (each needs one in-game check by Unholy):
- In-game caps for Dosh, stack size and level. The editor only enforces field type limits (s32, u16, u16).
- Does the game accept a new item cloned from the last item in its category (the community editor's method)? Check: add one item, load the save, open the bag.

## 2026-10-11 (runtime / Mode B)

| Blueprint says | Real game | Status |
|---|---|---|
| ProcessEvent sig `40 55 56 57 41 54 41 55 41 56 41 57 48 8D 6C 24 ? 48 81 EC` | **0 matches** in `NFL1-Win64-Shipping.exe` | Blueprint wrong |
| `version.dll` / `dxgi.dll` proxy in `FLiGame\Binaries\Win64` | Directory is `Game\Binaries\Win64`. The community uses UE4SS via `dwmapi.dll` there. | Verified (path); UE4SS on the current build UNVERIFIED until first launch (check `ue4ss\UE4SS.log`) |
| EAC "bypass" | Community method: `GameBootstrapper.ini` `ApplicationPath=EACLauncher.exe` -> `Game\Binaries\Win64\NFL1-Win64-Shipping.exe`. Steam launch keeps the normal save folder; multiplayer is lost. Launching the exe by hand uses `%LOCALAPPDATA%\Game\Saved\SaveGames` instead. | Source: Steam guide 3485522937; current ini is `ApplicationPath=EACLauncher.exe` (verified) |
| `AFLiWorldManager` etc. | Unknown. Runtime class/property names must be discovered in game (`live find Money`). Save structs (`PLAY_DATA_P`, ...) look native and may not be reflected at all. | UNVERIFIED |
