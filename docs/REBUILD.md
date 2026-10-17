# Stolen Hours: disaster recovery and rebuild blueprint

Written 2026-10-13 by Tock for Unholy. Use it if the PC dies, the drive fails, or the project folder is lost.
It covers two cases: restoring from the Google Drive backup (fast), and rebuilding from nothing (slow, but every
fact needed is here). Everything marked UNVERIFIED was never confirmed in game; the check that would confirm it
is next to it.

---

## 1. What exists, and where

| Thing | Where it lives | Survives a dead PC? |
|---|---|---|
| Project source (editor, mod, research, docs, notes, Discord bot) | `<project root>` | Only via the Google Drive zip |
| Google Drive backup | Drive > My Drive > `Stolen Hours backup` folder: `StolenHours-project-<date>.zip` + this document | Yes |
| Public GitHub repo (source + README + screenshots + releases) | https://github.com/UnholyScribe/StolenHours | Yes |
| Released builds | GitHub Releases v0.1.0, v0.2.0 and v0.3.0 (latest: Collection and Vulcan's Forge; zips of the `StolenHours.exe` folder) | Yes |
| Local copy of the latest build | `<portable build dir>` (same as v0.3.0) | No (download the release or rebuild from source) |
| Tour video | YouTube https://youtu.be/HJLNRAUg9rw (channel "Frank Jaeger") | Yes |
| Reddit account | u/TheHourThief (post to r/fantasylife pending mod approval) | Yes |
| Discord server + Flutter bot | Discord (server and bot app live online); bot code in the zip | Server yes; token no (reset it) |
| Game save | Steam Cloud keeps it; also `backups\saves\` in the zip | Yes |

Not in the backup on purpose (secrets; get them again as described in section 4):
- `research\private\aes_key.hex` (save key) and `research\private\pak_key.hex` (game pak key).
- `discord_bot\.env` (Discord bot token).

Not in the backup because they are rebuilt automatically (about 2.8 GB):
- `assets\game\` (raw extraction from the game paks), `editor\stolenhours\webgui\web\game\` (editor art/data),
  `build\scratch\`, `tools\asset_extract\bin` + `obj`, `__pycache__`, `.pytest_cache`.

---

## 2. Fast path: restore from the Google Drive backup

1. Install the toolchain (section 3.1).
2. Download `StolenHours-project-<date>.zip` from Drive, extract it to `<project root>`
   (any path works; nothing in the code is hardcoded to E:).
3. Get the keys back (section 4) into `research\private\`.
4. `py -3.12 -m pip install -r editor\requirements.txt pywebview pyinstaller pillow numpy lupa`
5. Build the extractor: `dotnet build -c Release tools\asset_extract`
6. Rebuild the art and data: `cd editor; py -3.12 -m stolenhours build-ui` (reads the game paks read-only; takes a
   while; writes `assets\game` and `editor\stolenhours\webgui\web\game`).
7. Test: `py -3.12 -m pytest -q tests` (103 tests at the time of writing).
8. Run: `StolenHours.cmd` (desktop window) or `StolenHours.cmd verify` (checks the save roundtrip).
9. Build the exe: `py -3.12 build_exe.py "<portable build dir>"` then
   `py -3.12 ..\research\portable_check.py "<portable build dir>"` (must report no leaks, nothing missing).
10. Cursor: open the folder, the rules in `.cursor\rules\` (Tock, Watchtower) come back with it. Agent memory
    lives in the docs: `README.md`, `docs\FINDINGS.md`, `notes\PROGRESS.md`, this file.

---

## 3. Rebuilding from scratch (no backup at all)

### 3.1 Toolchain

| Tool | Version used | Why |
|---|---|---|
| Windows 10/11 | Win 11 | WebView2 runtime ships with it (the editor window uses it) |
| Python | 3.12 (`py -3.12`) | Editor, tests, build |
| pip packages | pycryptodome 3.24, pywebview 6.2, pyinstaller 6.22, pillow 12, numpy 2.5, lupa 2.8, pytest 9 | AES, window, exe, images, 3D data, Lua tests |
| .NET SDK | 10.0 (8.0 also installed) | `tools\asset_extract` (CUE4Parse) |
| CUE4Parse NuGet | `CUE4Parse` + `CUE4Parse-Conversion` 1.2.2.202610 | Reads the game's IoStore paks |
| Git, GitHub CLI `gh` | any | Repo and releases |
| Cursor | any | The agent (Tock) |

Game facts: Fantasy Life i: The Girl Who Steals Time, Steam app **2993780**, Unreal Engine **5.4.4**, project name
`NFL1` / module `DP1Project`, shipping exe `Game\Binaries\Win64\NFL1-Win64-Shipping.exe`, ships Easy Anti-Cheat.
Save: `<Steam>\userdata\<account id>\2993780\remote\<hex>-00-gamedata.bin` (about 150 KB). No `systemdata.bin`.

### 3.2 Third-party pieces to fetch

| Piece | Source | Pin |
|---|---|---|
| Community save layout + parser | https://github.com/Niedzielan/fli_save_editor | commit `124135c6dd520afbd7af541ccf390478e52b9008` ("2.2.0 fix"). Files used: `fli_sav_pattern.txt`, `fli_sav2json.py`, `itemlist.txt`, `skilllist.txt`, `flaglist.txt`. No licence: personal use only. Put in `tools\fli_save_editor\` |
| UE4SS (runtime mod loader) | https://github.com/UE4SS-RE/RE-UE4SS/releases/tag/experimental-latest | `UE4SS_v3.0.1-1164-g5e627997.zip`, SHA-256 `3C72142A383E25E9F9553AC9E4D5677AA572E98CB369CAC57200EFB2E381E603`. Expand to `tools\ue4ss\dist` |
| Pak AES key + usmap mappings | https://github.com/DRayX/FLi-FModel (site https://drayx.github.io/FLi-FModel/) | Per game version. Mappings used: `FLi-2.2.0.usmap` |
| three.js | https://threejs.org (npm `three`) | `three.module.js`, `three.core.js`, addons OrbitControls, GLTFLoader, BufferGeometryUtils, SkeletonUtils; in `webgui\web\vendor\three` |

Re-fetch commands:

```powershell
git clone https://github.com/Niedzielan/fli_save_editor.git tools\fli_save_editor
git -C tools\fli_save_editor checkout 124135c6dd520afbd7af541ccf390478e52b9008
Invoke-WebRequest https://github.com/UE4SS-RE/RE-UE4SS/releases/download/experimental-latest/UE4SS_v3.0.1-1164-g5e627997.zip -OutFile tools\ue4ss\UE4SS_v3.0.1-1164-g5e627997.zip
Expand-Archive tools\ue4ss\UE4SS_v3.0.1-1164-g5e627997.zip tools\ue4ss\dist
```

### 3.3 Folder layout

```
StolenHours.cmd            starts the GUI; with arguments runs the CLI (StolenHours.cmd info)
README.md                  overview, commands, where things are
docs\BLUEPRINT.md          the original brief (a hypothesis; much of it turned out wrong)
docs\FINDINGS.md           verified facts, blueprint vs real game
docs\REBUILD.md            this file
notes\PROGRESS.md          dated log of everything done
editor\                    Python package `stolenhours`, tests, build_exe.py, launcher.py
hook\                      Mode B: UE4SS Lua mod + install_live.ps1
research\                  probe scripts; research\private\ = keys and mappings (git-ignored)
tools\                     third-party tools + asset_extract (C#)
backups\                   save / game-file / mod backups, each with SHA-256
assets\                    extracted game art (rebuilt)
discord_bot\               Flutter bot for the Reveria Guild Hall server
.cursor\rules\             tock.mdc (agent rules), watchtower-chloe.mdc
```

### 3.4 The save container (verified, byte-exact)

```
gamedata.bin = AES-256-ECB( PKCS#7( u32 gvas_size | zlib(gvas) | footer ) )
footer (34 bytes) = u32 1 | MD5(u32 gvas_size + zlib stream) | 14 x 0x00
zlib: level 6, memLevel 8, wbits 15  -> recompression is byte-identical
```

- No plaintext header, no XOR layer, no Oodle (the original blueprint was wrong on all three).
- The 32-byte AES key is a 32-character ASCII string stored as UTF-16LE inside `NFL1-Win64-Shipping.exe`.
  `container.key_from_game()` scans the exe for every run of 32 printable UTF-16LE chars, tries each as the key on
  the first block (decrypted bytes 4-5 must be a valid zlib header), then fully unpacks to confirm. About 5 s.
  This is how the shipped exe works without any key file.
- Rule: a save is only editable if decrypt -> repack gives the original bytes exactly.

### 3.5 The save body (GVAS)

- Header: `GVAS`, SaveGameVersion 3, UE4 522, UE5 1012, engine 5.4.4, 120 custom versions, class
  `/Script/DP1Project.SaveData`.
- After the class name the body is **native field-by-field serialization, not tagged properties**. Generic GVAS
  tools (uesave) fail. Parse with Niedzielan's pattern file (`fli_sav_pattern.txt`) via `fli_sav2json.SaveData`.
  Parse -> reserialize must be byte-exact. Stolen Hours has its own fast bytearray serializer (load+verify about
  4 s instead of 24 s).
- Uncompressed body about 8.1 MB.

Key fields (all verified on Unholy's save unless marked):

| What | Path in the parsed save |
|---|---|
| Dosh | `saveData.m_PlayData.Money` (s32) |
| Character name, island name | `m_CharaStatus.m_stAvatarP[0].m_name`, `m_PlayData.islandName` (ASCII, one copy) |
| Play time | `m_PlayData.playTime` (u32 seconds); start/save dates are .NET ticks |
| Lives | `m_CharaStatus.m_stAvatarP[0]`: `m_lv` Map<Name,u16>, `m_exp` Map<Name,u32>, `m_lifeStatus` (licenseRank, star, skillMaxPoint). Ids `life0000` Brand New, 0001 Paladin, 0002 Mercenary, 0003 Hunter, 0004 Magician, 0005 Miner, 0006 Woodcutter, 0007 Angler, 0008 Farmer, 0009 Cook, 0010 Blacksmith, 0011 Carpenter, 0012 Tailor, 0013 Alchemist, 0014 Artist |
| Inventory | `m_InventoryStatus.inv*` fixed arrays per pocket; stackables `stockNum` u16; equipment has `Quality`. Item handle = `((slot+1)*4) << 16 OR (bagBase + slot)`; bag bases Consume 0x0000, Weapon 0x1000, Material 0x7000, Recipe 0x8000, Important 0x9000. Item category -> pocket: 10 Weapon, 20 LifeTools, 30 Shield, 40 Armor, 60 Consume, 80 Kit, 90 Material, 95 Recipe, 100 Important, 110 Mount, 130 PowerUp |
| Equipped gear | handle `(slot+1)<<18 OR pocket<<12 OR slot`; pocket 1 weapon, 2 life tools, 3 shield, 4 armour |
| Appearance | `m_AvatarStatus.playerP[0].BodyParam` (BodyModelId, HeadModelId, HairModelId, colours, eye/nose/mouth/ear parts, VoiceId) |
| Skill boards | learned panel = `m_FlagStatus.skillPanelBitFlag[flagNo] = 1`; `skillPanelUnlockBitFlag` recomputed from parent-open + condition. SP = running sum of `GDSCharaLevelConfig.skillPoint` to the life's level |
| Map events | `m_QuestStatus.Active[id]` {phase, isNew, tmpFlagList}; phase 0 None, 1 Emerge, 2 Progress, 254 Achieve, 255 End; `m_QuestStatus.ActiveEventInfo`. On-map = phase 1 + info entry: UNVERIFIED |
| Time / weather | `m_PhaseInfo.envInfo.gameTime` (float, game minutes, UNVERIFIED units), `gameTimePeriodType` 0 Day 1 Night; `m_WeatherStatus.WeatherInfo[3].weatherType` 1 Sunny 2 Rainy 3 Cloudy |
| Play counters | `m_PlayData.playCountData` (43 fields) |
| Recipes | `m_RecipeStatus.recipeInfoMap[key].bitFlag` = 9 when learned, plus `GlobalItemGetFlag[book flagNo]` = 1 and the `irp_` book in `invRecipe` (2048 slots). Game accepting an unlock: UNVERIFIED |
| Encyclopedia | `GlobalLibraryFlag[idx]` (seen) + `GlobalLibraryNewFlag[idx]`; items via `GlobalItemGetFlag` |
| Gifts | `GlobalBitFlag` (one u8 per bit): add-on packs `aoc_recieve_01..32` (idx 7500+) with `aoc_new_NN` (7400+); LEVEL5 ID `level5_id_status_recieve_001..010` (8300+); built-in code `rompass_0001` -> `password_recieve_002` (7601) = public code AF579XS2 (Raccoon set); downloaded codes `password_recieve_download_001..299` (7700-7998); compensation 5500+. Re-claim by clearing the flag: UNVERIFIED |
| Outfit sets | `m_MySetStatus.viewEquipList[life0000].equipList` (30 look sets) |

### 3.6 Game data tables (from the paks)

Extracted as JSON by `tools\asset_extract` (`json` mode) under `assets\game\Game\Content\GameData\...`:
- Items: `Item/GDSItem{Armor,Consume,Craft,Important,Kit,LifeTools,Material,PowerUp,Recipe,Weapon,Vehicle,Treasure}Data`,
  names `Item/GDSItemText_Noun`. Hide icon-less items and `_EX`/`_BOX`/`_BT` variants.
- Lives: `Life/GDSLifeData` (starter tools/armour per life). Levels: `GDSCharaLevelConfig`.
- Avatar: `Avatar/*` tables, `Chara/GDSCharamakeText`; wear models `GameData/Wear/GDSWear{Hat,Body,Bottom,Hand,Feet,Cape,Accessory}ModelData`, `GDSItemEquipModelData`, `GDSItemEquipModelHairTypeData`.
- Skill boards: `GDSSkillBoard`, `GDSSkillPanel`, `GDSSkillData` (`m_autoBin` args: 16-byte header, tag 0x34 = string offset, 0x32 = int).
- Map: `GDSActiveEventTarget`, `GDSActiveEventLottery`, `GDSAreaDef`, `GDSMapText_Noun`, `<map>_GDSMapMinimap`,
  `GDSMapIconData`, `GDSMenuIconTexture`, `GDSFastTravel`, `<map>_GDSMapFuncPoint`, `GDSTamagemonoShrineData`,
  `GDSMapPickPoint`, `GDSMapEnemyPlacementConfig`. World -> map: u = (maxY - Y)/range, v = (X - minX)/range, bounds +-120000.
- Collection: `GDSRecipeData` (2012), `GDSItemRecipeData` (2011 books), `GDSRecipeTabData`, `GDSLibraryListData` (385),
  `GDSLibraryFlag`, `GDSLibraryItemData` (875), `GDSAOCCommonData`, `GDSAOCAddItemData`, `GDSLevel5IdStatusRewardData`,
  `GDSPasswordData`, `GDSGlobalBitFlag`.
- Vulcan's Forge: `GDSRecipeData` (`titleType`, `rewardData.rank2_itemId` = the + version, `itemList` materials),
  `GDSItemWeaponData`/`LifeToolsData`/`ArmorData` (5-entry stat lists per grade, value <= 1 = grade not made;
  `addStatusLotTableList`, `addSkillLotTableList`), `GDSAddStatusLotTable`, `GDSAddSkillLotTable` (lotWeight > 0),
  `GDSItemTitleData` (grade names), `GDSSkillData`/`GDSSkillText`/`GDSSkillText_Noun` (skill text with params).
  Save gear: `itemTitle` 1-5, `Quality` 0-3 (Normal/Good/Great/Top), `addEquipStatus` [{Type EEquipStatusType, Value 0}], `grantSkillId` x3.
- UI art: `Graphics/2D/UI/...` textures to PNG; fonts `L5_Latin_DP1_SF01-Bold`, `FOT-RodinNTLGPro-M/DB`.
- 3D: avatar meshes to glTF (`mesh` mode), animations (`anim` mode), e.g. `cmn_charaMakeIdle`, per-tool `<prefix>_idleEquip`.

Extractor usage: `asset_extract <paksDir> <aesKeyHex> <mappings.usmap> list|export|raw|json|mesh|anim <regex> [outDir]`.
Paks dir: `<game>\Game\Content\Paks`.

### 3.7 Editor architecture (`editor\stolenhours`)

| Module | Job |
|---|---|
| `paths.py`, `steam.py` | Find Steam (registry, then drive scan), libraries (`libraryfolders.vdf`), game (`appmanifest_2993780.acf`), saves per account (`loginusers.vdf` picks the default). Env overrides `STOLENHOURS_STEAM_DIR`, `STOLENHOURS_GAME_DIR`, `STOLENHOURS_SAVE` |
| `container.py` | AES/zlib/MD5 container, key from file or from the game exe |
| `savefile.py` | Parse/serialize, typed accessors (money, lives, items, add_item, appearance, play time, island), write with safety |
| `safety.py` | Refuse writes while the game runs (`tasklist`), SHA-256 backup before each write, atomic replace, stale-file guard |
| `cli.py`, `__main__.py` | All commands (`info verify lives items find-item set-money set-name set-life set-stock add-item appearance set-appearance export-json import-json unpack pack backup restore live analyze-dump where gui build-ui`) |
| `webgui\server.py` | Local HTTP server on 127.0.0.1, per-session token, `POST /api/<method>` -> `Backend.api_*` |
| `webgui\app.py` | pywebview window (WebView2), browser fallback |
| `webgui\web\` | `index.html`, `app.js` (all tabs), `style.css`, `look3d.js` (three.js preview), `game\` (built art/data) |
| `uiassets.py` | build-ui step 1/2: extract and pick UI art, fonts, item catalog |
| `avatar3d.py`, `gear.py` | 3D avatar data, current gear (live hook > last live reading > save) |
| `skillboard.py`, `skilltree.py` | Board data and the learn/remove rules |
| `mapevents.py`, `mapview.py`, `mapmarkers.py` | Map events editor, Live Map art/markers for all 8 maps |
| `records.py` | Play counters + per-save snapshot history |
| `collection.py` | Recipes, Encyclopedia, Gifts, 11 public gift codes and rewards |
| `forge.py` | Vulcan's Forge: any recipe's item at a chosen grade, bonus stat and skills, or its + version |
| `live.py`, `dumpscan.py` | Mode B mailbox client, dump analysis |
| `modinstall.py` | Installs the bundled Lua mod into a game that already has UE4SS |
| `gui.py` | Old plain Tk editor (`gui --classic`) |

Tabs in the window: Adventurer, Licenses (with Skill Board), Bag, Look (2D/3D), Map, Live Map, Time Hook,
Collection, Vulcan (Vulcan's Forge), Records, Backups.

`build-ui` runs extract + build for: uiassets, avatar3d, skillboard, mapevents, mapview, collection, forge.

### 3.8 Safety rules (keep these)

- Back up the save with SHA-256 before every write; never write while the game runs; only trust an edit after a
  byte-exact unpack/repack roundtrip; refuse if the file changed on disk since it was loaded.
- Test on copies of the save, never the real one.
- Never change the game install without Unholy's OK (the mod installer and `install_live.ps1` back up first).
- Keys and mappings never go into git, the exe, or anything public. `build_exe.py` and `portable_check.py` refuse
  `.hex`/`.usmap` files and scan for the Steam id, Windows user name and project paths.

### 3.9 Mode B (live, game running)

- `hook\install_live.ps1`: backs up to `backups\game_install\`, changes `GameBootstrapper.ini`
  `ApplicationPath=EACLauncher.exe` -> `Game\Binaries\Win64\NFL1-Win64-Shipping.exe` (skips EAC, loses multiplayer),
  installs UE4SS (`dwmapi.dll` proxy in `Game\Binaries\Win64`) and the mod. `-Uninstall` reverts. A Steam update
  or "verify files" undoes the ini change.
- Mod `hook\ue4ss_mod\StolenHours\Scripts\main.lua` (v0.5.0) + `stolenhours_dump.lua`. Mailbox
  `%LOCALAPPDATA%\StolenHours\live\`: `cmd.txt` in, `ack.txt` out, `heartbeat.txt`. Line format
  `<id>\t<VERB>\t<args>`, reply `<id>\tOK|ERR\t<text>`. Verbs: PING, FIND_PROP, GET, SET, PROBE, MAP_KEYS, EVENTS,
  PLAYER, LIST_PROPS, DUMP. All object access inside `ExecuteInGameThread`.
- Live data owners: `GDDPlayData.m_permanent.Money` (Dosh), `GDDCharaStatus`, `GDDPhaseStatus...envInfo.gameTime`,
  `GDDWeatherStatus`, `GDDQuestStatus`. Dumping UMG widgets crashes the game; the dump skips UI/anim classes.
- Lua is tested offline with lupa against `editor\tests\lua_mock.lua`.

### 3.10 Building and shipping the exe

- `cd editor; py -3.12 build_exe.py "<portable build dir>"`: PyInstaller one-folder, windowed, bundles `web\`, the
  community parser files and the mod. Refuses to build while the editor runs from the target.
- `py -3.12 ..\research\portable_check.py "<portable build dir>"`: no keys/mappings/Steam id/paths; a copy run from another
  folder with an empty LOCALAPPDATA still finds save, game and mod.
- Release: zip the folder as `StolenHours-<ver>-win64.zip`, record its SHA-256, `gh release create` on
  UnholyScribe/StolenHours, check GitHub's digest matches. Bump `editor\stolenhours\__init__.py` `__version__`.
- Before anything public: privacy scan for the Steam id, Windows user name, character name, user paths, phone.

### 3.11 Tests

`cd editor; py -3.12 -m pytest -q tests`. Covers container roundtrip, parser byte-exactness, every edit
(rest of save byte-identical), Steam discovery on fake layouts, backups/restore, skill tree rules, map events,
records, collection unlocks, Lua mod against the mock. Tests that need the real save/key skip without them.

---

## 4. Getting the secrets back

| Secret | How to recover |
|---|---|
| Save key (`research\private\aes_key.hex`) | Not needed for the exe (it reads the key from the game). For the dev tree: run `py -3.12 -c "from stolenhours import container, paths; import pathlib; raw=pathlib.Path(r'<save path>').read_bytes(); print(container.resolve_key(raw).hex())"` from `editor` with no key file present, and save the output as `aes_key.hex`. It is also published in Niedzielan's `fli_bin2sav.py` (public repo) |
| Pak key (`research\private\pak_key.hex`) | DRayX/FLi-FModel lists the AES key per game version (https://drayx.github.io/FLi-FModel/). Test it with `asset_extract ... list Game` |
| Mappings (`research\private\FLi-2.2.0.usmap`) | Same site (`<build id>/Mappings.usmap`), or UE4SS "dump usmap" in game (`live dump-all`) |
| Discord bot token (`discord_bot\.env`) | Discord Developer Portal > app "Flutter" (1559310901189021716) > Bot > Reset Token, then `py -3.12 discord_bot\set_token.py` (reads the clipboard, never prints it) |
| GitHub | Log in to `gh` again (`gh auth login`); repo UnholyScribe/StolenHours |

---

## 5. Side projects in the zip

- **Discord, Reveria Guild Hall + bot Flutter** (`discord_bot\`): discord.py 2.x, python-dotenv. XP + license
  ranks, AutoMod strikes, reports, `/rank /leaderboard /ranks /rules /givexp`. Run with `run_bot.cmd`. Setup
  scripts (`setup_server.py`, `setup_security.py`, `setup_rules.py`, `setup_info.py`) are re-runnable; some need
  temporary extra bot permissions (see their docstrings). `list_channels.py`, `check_perms.py` are read-only.
- **Promo**: tour video built by `research\video\make_video.py` from scene shots (kept in Pictures, not in the zip).
- **Reddit**: u/TheHourThief. Post to r/fantasylife was auto-removed (new account); modmail sent. Repost with the
  YouTube link once allowed.

---

## 6. Open items (UNVERIFIED, needs Unholy in game)

- Collection tab: recipe unlock shows in the crafting list; Encyclopedia fill-in; Claim again on an add-on pack;
  re-entering a gift code after Claim again; Add to bag items.
- Vulcan's Forge: the game shows a forged item at the chosen grade with its bonus stat and skills, and works out
  the bonus amount from Value 0.
- Map tab: an event put on the map shows up in game; time/weather units.
- Skill board: a panel behind a blank panel.
- Look tab: face slider units; glasses socket.
- Mod: struct-value GET fix needs Unholy's OK before touching the installed mod.
