# Progress

## 2026-11-11: Ship 0.6.5 — IndoorDesigen mesh pass (Tock)
- Loom dumps: 307/307 mesh index, house_design_preview, paint→glb, 00 tex fallback, brick/royal/thatch extracts, Size W/D/H CONFIRMED.
- Village: `design_preview` + theme shell glbs + craft3d 00-tex aliases; wallsFloors `previewGlbs`. Dig write HOLD.
- Transmorph A+B confirmed to Loom; Bag UI HOLD until live SET proof.

## 2026-11-11: Ship 0.6.4 (Tock)
- Loom RR: IndoorDesigen part→mesh still digging; transmorph apply-path drafting (Bag UI HOLD); Water HOLD.
- Shipped banked: `encode_map_id` CRC32 UTF-32LE + outdoor Map_000100_01_env sun retarget. No new mesh dump yet.

## 2026-11-11: Tick 31 — mapId encode CONFIRMED (Tock)
- Loom: `mapId` = CRC32(UTF-32LE). Wired `village.encode_map_id`; FINDINGS updated; NPCEmptyRoom_01=2625512011.
- House look spine + transmorph catalog banked by Loom — no Bag skin UI until apply path; IndoorDesigen Path next Emperor pass.
- Buddy houses not editable early (no new place pairs). Dig CLOSED; Water HOLD stands.

## 2026-11-10: Tick 24 — outdoor light P2 + transmorph bank (Tock)
- Loom: Dig offline leftovers CLOSED; Water/Road Hagram gated early — water HOLD stands.
- Transmorph Dig A/B/C banked — no Bag skin UI until apply path agreed (sidecar/mod hook).
- Village outdoor sun retargeted toward Map_000100_01_env (#F0DBC5 / SkyLight stand-in). Map dual-tex mats still open.
- Chloe ACK island track ownership.

## 2026-11-10: Ship 0.6.3 (Tock)
- House P0 theme (designId Diff/Nml/Rse + floor Vertex_Color + room_env00) + Dig peel-only + Apply preview.
- pytest 142; portable_check clean.

## 2026-11-10: Emperor House P0 (tick 23) (Tock)
- Loom WORK: game-identical House look. Shipped P0: save `defaultIndoorDesignId` → `theme_for_design`
  (walls_floors 117/118); Diff+Nml+**Rse** + floor Vertex_Color 0.25; room_env00 lights kept;
  Walls&floors catalog **Apply preview** (`api_village_theme`); handoff RSE copied into craft3d/t.
- Not yet: IndoorDesigen Wall/Floor glb parts (still planes), real window/door BPs, outdoor P2 sun/map mats.
- HOLD: wallpaper write-to-save, Dig water, weapon-skin.

## 2026-11-10: Dig CONFIRMED + House theme pass (tick 22) (Tock)
- Loom: Craft raise + Excavate peel CONFIRMED; Dig≠water. Editor Dig no longer land→water at floor.
- House look step 1: Tropical `ide_thatch_00` wall/floor dif+nml via MeshStandard + room_env00 lights
  (kill myhouse PNG MeshBasic default). Water Hagram + full IndoorDesigen parts still open.
- HOLDs: Dig-sync water-fill, MapCraft CALL, weapon-skin. Apply-to-room write still UNVERIFIED.

## 2026-11-10: Dig UI note (tick 21) (Tock)
- Loom live Base Camp: Excavate gray on flat Ground, live on elevated; Dig-at-floor→water
  may be UI-gated. Updated Island Dig note + `DIG_PROOF_FOR_UNHOLY.json`. HOLDs until Dig proof banked.

## 2026-11-10: M2 agree + pack mesh resolve (Tock)
- Loom tasking (Unholy): read `ISLAND_SHARED_MODEL_M2.md` — **AGREED** (mapId trio, XY=50/Z=150,
  bitflags, pack-sole mesh source). No island reconstruction write until Dig proof.
- Wired `resolve_pack_mesh` + `api_village_mesh` (read-only). craft.json `meshIndex` 1186 ids.
- MAP_ID_NUMERIC already in 0.6.2. Weapon-skin / MapCraft CALL still HOLD.

## 2026-11-10: Ship 0.6.2 (Tock)
- Unshipped after 0.6.1: full Loom `basecamp_pack_index` (89 keys vs 26 in EXE) + `MAP_ID_NUMERIC`
  trio in `village.py`. Reddit Decivre reply+DM done (PC/Steam only; asked Switch/mobile intent).
- Dig live + weapon-skin still parked. 30m Loom loop stays.

## 2026-11-10: Full Loom pack_index merge (Tock)
- Unholy nudge: editor pack was thin (33 keys) vs Loom index (85). Merged full
  `basecamp_pack_index` into `basecamp_pack.json` + surfaced slices on `craft.json`
  (furniture pack, live ExeCmds, development, npc_rooms, reform/bridge groups, shape,
  mapcraft UI model, stand ranges, size access, water VPC, leftovers, kits…).
- Dig live proof + weapon-skin still parked; 30m loop stays.

## 2026-11-10: 30m Loom tick — mapId + Paint pack (Tock)
- Pulled Loom `ready_for_tock`: `MAP_ID_NUMERIC` trio in `village.py`; `basecamp_pack`/`craft`
  got 14 Paint LAND ids, hagram ops, dig water Z, shape summary, dig playbook, mapid lookup.
- Dig/MapCraft live still blocked (Loom on Map_200000). Weapon-skin parked. 30m loop stays armed.

## 2026-11-10: Ship 0.6.1 to GitHub (Tock)
- Version **0.6.1** / mod **0.8.2**: EVENTS `ActiveEventInfo` ForEach now `unwrap(k)` (was userdata-only;
  broken on table RemoteUnrealParam wrappers). pytest **138 passed**; portable_check clean; GitHub zip.

## 2026-11-10: 30m Loom loop + editor debug pass (Tock)
- Loom check-in retargeted to **every 30 minutes** (`$interval = 1800`); loop stays armed until
  Loom jobs done + last handoff applied. Weapon-skin dig parked by Loom until Base Camp leftovers clear.
- Full editor pytest: **138 passed**. Fixed live-map/lua tests for mod **0.8.1** + FakeBridge.ping /
  snapshot `control`/`mod_version`. Real bug: EVENTS `ActiveEventInfo` ForEach used userdata-only
  unwrap — now `unwrap(k)` so table RemoteUnrealParam mocks (and any table wrappers) work. Added
  `set_gear` unit test.

## 2026-11-10: Ship 0.6.0 to GitHub (Tock)
- Version **0.6.0**: Live Map (map decrypt + AE spawn 0.8.1), Bag beyond-normal gear editor, Base Camp pack
  pull (cook-absent / fence VPC / shave / outdoor / buildings / land / indoor 307).
- Portable: `survey_root` no longer prefers `G:\Stolen Hours` — uses exe folder or `%LOCALAPPDATA%\StolenHours\survey`.
  `portable_check` also flags `G:\Stolen Hours` needles. Live Map / saves / key still Steam-discovered per PC.
- GitHub release zip + source push (agents/ Loom sandbox stays local / gitignored).

## 2026-11-10: Loom hourly tick — outdoor/buildings/land/indoor parts (Tock)
- Loom still continuing (cook-absent fallbacks next). Kept 1h loop.
- Synced `basecamp_pack_index` → `game/village/basecamp_pack.json` + `craft.json`: outdoor
  BRIDGE/FENCE/SLOPE/ROAD/farm 105, buildings HOUSE 81 + guild 18, LAND pads 14, indoor parts
  307/307, furniture coverage, planned_construct 10. Copied into running EXE `_internal`.

## 2026-11-10: Early Loom tick — Base Camp pack (Tock)
- Interrupted ~39m into hour (~21m left); ran early sync; re-armed sleep **1273s** then hourly.
- Loom Base Camp packs → `game/village/basecamp_pack.json` + craft.json wallsFloors/landmarks.
- Terrain UI = Hagram Pile Up / Dig / **Shave** (bit0) / Level; Z±150 labeled Loom-proven.
- House tab: Walls & floors catalog (74 Type 117/118). Apply-to-room write still UNVERIFIED.

## 2026-11-10: Hourly Loom sync + map decryption tick 1 (Tock)
- Armed 1h wake loop (`AGENT_LOOP_TICK_loom_check`, PID in terminals) — check Loom, implement proven
  dumps, re-arm until Loom’s map jobs are done (then stop).
- Applied Loom map scrape: AE icon picker (MAP_SYSTEM), **244** game map icons shipped, **Snoozaland**
  `Map_200100` (Dream group), Base Camp Dark Don / Bed to Dreams / guide pins, craft-pad HUD crop
  (`GDSCraftMiniMapSetting` 475×380 @786,832) as Live Map ⚒ toggle. In-game textures only.

## 2026-11-10: Live Map event spawn blueprint (Tock)
- Wired Loom-proven mailbox verbs into the editor: `EVENT_DRAW_UNTIL` / `EVENT_END` / `EVENT_SWAP` /
  lottery WithReset via `live.py` + `api_mapview_event_control`.
- Live Map side panel: control_worthy catalog picker (181 from `game/events/control.json`), Spawn /
  draw-until, Redraw all, End on each open event. Needs StolenHours mod **0.8.0+**.
- Live proof on Unholy's running game: spawn Mining Mania (`007_01`) → OK try=5.

## 2026-11-09: PetDesigner lessons + brother-ready ship (Tock)
- Read `G:\Archives\petdesigner-book` (NMS techniques). Wrote `research/refs/petdesigner-lessons.md`.
- Adopted: no-store for JS/JSON/manifests (server + fetches); Look already correct for FLi bone scale
  (bind inverses — do **not** copy NMS scale override). Ship `START HERE.txt`.
- Portable story for handoff: double-click EXE, auto Steam/save/key, WebView2 prompt or browser fallback,
  silent MOTW clear, Live Map one-click. Rebuild + zip after this note.

## 2026-11-09: EXE Just Works + Live Map setup (Tock)
- Testers still needed Unblock-File / a command, couldn't find saves, Live Map dead.
- Root causes: GitHub release still 0.3.0; MOTW; soft-deps MessageBox that exited on Yes;
  title "Other file" used prompt() instead of native picker; Live Map needs UE4SS which we never installed.
- Fixes in 0.5.0: silent MOTW clear every launch; only hard blockers prompt; deeper userdata scan;
  native Open dialog (webview or Win32); clearer key/save errors; ship `tools/ue4ss/dist` and
  **Install Live setup** (UE4SS + StolenHours mod + EAC skip) from the Live Map pane.

## 2026-10-26: GitHub MOTW unblock (Tock)
- Tester (Khilents): crash after GitHub zip until `Unblock-File`; had to redo every reopen; Live Map
  idle without the game (expected — clarified in UI veil).
- New `stolenhours.motw`: detect Zone.Identifier, prompt once, silent unblock on later launches.
- Ship `Run Stolen Hours.cmd` next to the exe (unblock + start). Crash dialog mentions it.
- README: "just unzipped and it crashes" → Run Stolen Hours.cmd.

## 2026-10-22: Portable deps + Luby crash fix (Tock)
- Luby's `editor_crash.log`: pythonnet / `Python.Runtime.dll` failed on WinForms UI — no browser fallback.
- Native UI now prefers **Edge WebView2** (`edgechromium`); skips WinForms unless .NET 4.8 is present;
  any native failure opens the system browser with a clear message.
- New `stolenhours.deps`: WebView2 / .NET 4.8 / browser / game+save checklist, writes
  `%LOCALAPPDATA%\StolenHours\setup_check.txt`, MessageBox with install link or continue.
- Flags: `--check`, `--browser`. Crash dialog hints WebView2 / `--browser` for pythonnet errors.
- Goal for next GitHub zip: zero ties to Unholy's PC; stranger PCs get told what's missing.

## 2026-10-17: Village blank blue sky fix (Tock)
- Outdoor Village showed only clear-color sky: custom water `ShaderMaterial` (Three r186) could
  abort craft-sector build after the scene was cleared. Reverted water to `MeshStandardMaterial`,
  try/catch around craft mesh, clear `craftTexCache` on hardReset. Exe rebuilt.

## 2026-10-17: Single exe + cleanup (Tock)
- Rebuilt `G:\Stolen Hours\StolenHours.exe` (includes Village water/lighting stand-in pass).
- Removed duplicate source `G:\StolenHours-repo`, old `StolenHours-0.{1,2,3}.0-win64.zip` on G:\,
  leftover `build/` under the project. Kept: source `E:\Fantasy Life i - Stolen Hours` + one exe folder.

## 2026-10-17: Customization look — honest limit + stand-in pass (Tock)
- Unholy asked for foliage/grass/rubble/cliff/water/lighting **100% identical** to Customization.
- **Cannot** — Village is Three, not the game’s UE materials/foliage. Documented in FINDINGS.
- What we did improve: softer outdoor lighting, animated stylized water ripples, denser grass
  tufts + cliff grooves, keep map3d surroundings + save craft (ruins/rubble when placed).
- Reload Village to see; no exe rebuild required for web assets if running from source.

## 2026-10-17: Wipe useless UE orbit data (Tock)
- Deleted all 448 survey PNGs (~700 MB) + UE `Saved/Logs`, `Intermediate`, `E:\SMW` junction.
- Re-exported math-only truth: `grid.json`, `objects.json`, `import_manifest.json`, per-cell `meta.json`.
- **UE role (decision):** blank UE 5.8 cannot close schematic↔Customization — no FLi cooked map/craft
  content. Keep `survey_math` (Python). Park orbit capture until/unless we import real glTF into UE for
  debug; finishing Village stays Three.js + save/live + extracted meshes. Game’s own UE (UE4SS live) is
  already the useful runtime path.

## 2026-10-17: UE Math Worker survey (Tock)
- `tools/SurveyMathWorker/` scaffold remains (Cmd + Python import/capture) but orbit PNGs abandoned as empty.
- `stolenhours.survey_math` / `stolenhours survey export` writes truth tables (no UE required).
- Village pane loads `survey_truth` API: yellow cell rings + green door-forward arrows.

## 2026-10-17: Village outdoor 90° axis lock (Tock)
- Matched shots: guild/mountain are **north** in Customization but were **west** in the editor (full 90° off).
- Outdoor map is now `X=−UE_Y`, `Z=UE_X`; map3d `rotation.y = −90°`; default cam looks north. Rebuilt exe.

## 2026-10-17: Village outdoor N/S axis fix (Tock)
- Matched-angle shots showed houses/water/hills mirrored N/S vs Customization (looking west: houses should be right/north).
- Outdoor Three Z is now `+UE_Y` (was `−UE_Y`); map3d no longer Z-mirrors. Rebuilt `G:\Stolen Hours\StolenHours.exe`.

## 2026-10-17: Village view vs Customization fix (Tock)
- Editor was a bare craft heightfield in the sky; in-game Customization has map3d surroundings + overhead diamond cam.
- Re-enabled Base Camp `map3d` env by default; Customization-like 45° high cam; brighter yellow pad rim; larger N/E/S/W.
- Rebuilt `G:\Stolen Hours\StolenHours.exe` (close/reopen editor, hit Reload).

## 2026-10-17: Source published to GitHub (Tock)
- Pushed editor + hook + docs + research helpers to https://github.com/UnholyScribe/StolenHours (`49c8669`).
- Scrubbed Steam id / personal paths; kept keys, `web/game` art, and game BGM oggs out of the repo.
- README now has a **Source** section (run-from-source steps).

## 2026-10-17: Village map hard refresh + N/E/S/W (Tock)
- Reload now hard-resets Village3D (meshes/caches/static map3d env) and re-fetches terrain + placements from the open save.
- Outdoor craft rebuilds from save heightfield only (`loadEnv` off by default).
- Compass: world N/E/S/W sprites + HUD rose (N = −Z, E = +X, S = +Z, W = −X).

## 2026-10-17: NH Discord showcase posts (Tock)
- Posted Stolen Hours showcase (Reddit + GitHub + Look/Live Map image links; **no** invite) in Nintendo Homebrew `#off-topic` and `#nintendo-discussion` (staff-cleared).
- Reveria invite already on Reddit post + GitHub README Community section.

## 2026-10-17: Exe rebuild + Reddit check (Tock)
- Rebuilt `G:\Stolen Hours\StolenHours.exe` (0.4.0, village live + presets). Portable check: no leaks/missing. Mod in game **0.7.0** `current: true`. Village tests 5/5.
- Reddit u/TheHourThief: live post `1x7wmw7` still up (score 1); no DMs, no replies on the post or to the outreach comments. Inbox only old AutoMod on deleted `1x4ld1z`.

## 2026-10-16: Exe 0.4.0 + Reddit skim (Tock)
- UE4SS StolenHours mod force-reinstalled; game has **0.7.0**, hashes match repo (`current: true`).
- `__version__` → **0.4.0**; rebuilt `G:\Stolen Hours\StolenHours.exe` (bundles mod 0.7.0). GitHub release still
  v0.3.0 (not pushed). Selftest roundtrip OK.
- Reddit (u/TheHourThief): promo post still AutoMod-removed (“account too new”, 3 days ago); no modmail reply.
  Recent r/fantasylife: gameplay / DLC-save path help / islander recipes — no rival FLi save editor.
- Reveria Guild Hall invite (never-expire #welcome): `https://discord.gg/YvAJJ9kpzu`. Subreddit Discord:
  `https://discord.gg/ZAyEZ3W` (FantasyLife). Newer FLi community Discord: `https://discord.gg/fantasy-life-898413081070272542`.
- Outreach hold (rules check 2026-10-16): Fantasy Life `#rules-and-info` has **No Spam** (and no explicit save-editor
  ban). Dropping Reveria invites there = spam/recruiting → skip. r/fantasylife has **No blatant advertising**; promo
  post still AutoMod-removed. No invites sent.

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

## 2026-10-11: Dump feature, first live contact (Tock)
- Mod 0.2.0: `DUMP` (values of every DP1Project / `/Game` object + singletons with engine fields, schema of all
  DP1Project classes/structs/enums with offsets), `DUMP_BUILTIN` (UE4SS object dump, C++ SDK, usmap), Ctrl+F9 in game.
  `FIND_PROP` now also searches structs.
- Editor: `live dump`, `live dump-all`, `analyze-dump` (cross-references the dump with the save: Money, name, island,
  life levels/exp, getOrderCount; lists game properties with stat-like names). GUI "Dump everything" button.
- Mod is now tested by running the real Lua in Lua 5.4 (lupa) against a mocked UE4SS API (`editor\tests\lua_mock.lua`).
  That caught a CRLF bug in the mailbox that would have broken every command. 38 tests pass.
- In game: UE4SS loads, mod 0.1.0 answered PING. `Money` not on any reflected class; `SaveData` class is reflected.
- Mod 0.2.0 copied into the game; UE4SS hot reload enabled (Ctrl+R). Needs one game restart to take effect.
- Stale-save guard: writes refuse if the save changed on disk since it was loaded. Appearance editing added.

## 2026-10-11: Live Dosh found, crash-safe dump (Tock)
- First full dump found the live data: `GDDPlayData.m_permanent.Money` etc. (see FINDINGS). The dump then crashed
  the game on a menu widget; the save was checked (verify OK, sha A2E38F58...) and backed up (`after-crash`).
- Mod 0.3.0: dump skips UI/animation objects and writes `GDD*` first; `GET`/`SET` take paths
  (`m_permanent.Money`, `m_stAvatarP[0].m_name`); `SET` re-reads and returns ERR if the write did not stick.
  Deployed to the game. 39 tests pass.

## 2026-10-11: Game-styled editor, standalone exe (Tock)
- Web GUI (`editor\stolenhours\webgui`, pywebview) styled with art, fonts and data pulled from the paks
  (`uiassets.py`, `tools\asset_extract`). Item catalog from the game's item tables: names, icons, pocket per category;
  icon-less and `_EX`/`_BOX`/`_BT` copies hidden, search limited to the open pocket.
- Shippable exe: `editor\build_exe.py` -> `G:\Stolen Hours\StolenHours.exe`. No key inside: the save key is a 32-char
  UTF-16LE string in `NFL1-Win64-Shipping.exe`; `container.resolve_key` tests every such string against the save
  (~5 s). `StolenHours.exe --selftest` on Unholy's PC: Steam at `C:\Null\Grave`, key from game, roundtrip exact.
  Backups go to `%LOCALAPPDATA%\StolenHours\backups` in the exe. Time Hook still needs UE4SS installed by hand.
- Look tab 3D preview (`webgui\web\look3d.js`, data from `avatar3d.py`): the game's avatar meshes rebound onto one
  skeleton, toon shaders using the game's masks and colour tables, body-size bones, face sliders mapped through the
  head material's limits (units and direction UNVERIFIED: compare a slider extreme in game). Poses are the game's own
  animations (`cmn_charaMakeIdle` default, `cmn_changeCostumeLoop`, `cmn_idle`) via the extractor's `anim` mode. UE
  to glTF verified on the reference pose: position (X, Z, Y)/100, rotation (-x, -z, -y, w); played as offsets from
  the skeleton's reference pose because `*_add*` helper bones rest differently per mesh.
- Exe diagnostics: `StolenHours.exe --serve PORT TOKEN` runs the backend headless; unexpected API errors now return
  their message and log to `%LOCALAPPDATA%\StolenHours\editor_errors.log` instead of "Failed to fetch".

- Per-life Equipment-screen idles: `Avatar_Equipment_AnimBP` maps tool type to sequence (b00 Stick, b01 Blade,
  b02 Sword, b03 Bow, b04 Rod, c01 Felling, c02 Mining, c03 Fishing, c04 Harvesting, w01 Saw, w02 Hammer, w03 Pan,
  w04 Needle, w05 Flask, w06 Pen; the Pen state is labelled w04 but plays w06). Life ids to tools from GDSLifeData
  starter tools; this also settles life0000 = Brand New and life0014 = Artist. Unholy's screenshots match (Paladin,
  Miner). All 72 avatar idle anims are dumped; `cmn_climbIdle` is ACL-compressed and needs CUE4Parse-Natives.

## 2026-10-12: Held weapons, Adventurer/Licenses 3D (Tock)
- Equipment-screen poses hold the life's weapon/tool and shield (save `m_viewEquipInvInfo` over
  `m_abilityEquipInvInfo`, else GDSLifeData rental gear). Adventurer: pose dropdown under the name plate;
  Licenses: the clicked life's pose; both have a 2D/3D toggle. Exe rebuilt.
- Weapons were drawn ~1.4-1.9x too big: body sizes were applied as bone scales, which carry down the arm. The game
  applies them in component space (see FINDINGS), so the preview now puts them in the bind matrices. Checked
  against Unholy's Miner and Paladin Equipment screenshots.
- Unholy ran "Dump everything" (16,442 objects, 0 errors) and a Dosh read (14,633, matches the save). No live
  Dosh write in the log yet.
- Mod bug: `LIST_PROPS` and `GET` fail on struct values (`ToString` on FVector / PointerToUberGraphFrame);
  dotted paths (`RelativeScale3D.X`) work. Fixing it means editing the installed mod: ask Unholy first.

- Skill boards dumped (`skillboard.py`, part of `build-ui`): `game/skillboard/boards.json` (14 boards, 950 panels,
  399 skills with English names/descriptions/params) plus 73 board images/icons. Save side read-only for now:
  `SaveFile.skill_panels()` and `/api/skill_panels`. Exe rebuilt and smoke-tested headless.
- Exe: image bursts dropped connections (keep-alive + backlog 128 fix); real-window CDP pass over every tab, 0 errors.
- 3D armour: Adventurer and Look wear the main character's gear in every pose (`gear.py`: live hook, else the last
  live reading in `USER_DATA\last_gear.json` while it is newer than the save, else the save's current-life gear);
  Licenses wear each life's starter armour (GDSLifeData defaults) plus its weapon. Hats/capes on body sockets, hair
  swaps to the hat's type, gloves/boots/tops/bottoms replace the bare parts. 568 wear models (armour-referenced
  only); avatar3d is now ~200 MB. Glasses not drawn yet (socket unknown).

## 2026-10-12: Side project, Reveria Guild Hall Discord + Flutter bot (Tock)
- Unholy's own Fantasy Life server (the official one bans mods). Login: Unholy's Discord session lives in Cursor's
  built-in browser; if it's logged out or asks for 2FA, Unholy signs in himself. Never store his credentials.
- Bot "Flutter" (app 1559310901189021716, private, guild-install only), code in `discord_bot\`: chat XP + license
  ranks (Fledgling..Legend at lv 75, ~835k XP), owner security DMs, AutoMod strikes/timeouts, Report to the Guild,
  /rank /leaderboard /ranks /rules /givexp. Token only in `discord_bot\.env` (gitignored); reset it with
  `set_token.py` (clipboard, never printed). Runs only while `run_bot.cmd` / `bot.py` is running.
- Permissions: the owner account is the only full power; every role is cosmetic except Guild Officer (moderation, no
  ban) and Mustang's Guard (private Mustang's Hold text + voice). Flutter sits under Guild Officer with Manage Roles,
  Timeout Members, View Audit Log. 2FA required for moderation; all channels but #welcome/#rules age-restricted (18+).
- Setup scripts (re-runnable, need temporary extra perms on Flutter, see their docstrings): `setup_server.py`,
  `setup_security.py`, `setup_rules.py`. Rules text and AutoMod word lists: `moderation.py`.

## 2026-10-12: Skill board editor, Map tab, Records (Tock)
- Text sweep: ribbons, buttons, hints and dropdowns no longer clip or stick out (every tab checked).
- Skill board editor (Licenses > Skill Board): the game's board art, wheel zoom / drag pan, left-click learn,
  right-click remove (cascades), Learn all / Reset, "Ignore game rules" (learns the path, raises max SP). SP =
  level table (verified); unlock flags follow the save's rule (verified). `skilltree.py`, 8 tests.
- Map tab (`mapevents.py`, `game/events/events.json`, part of `build-ui`): 679 solo map events in 15 areas with
  names, type, weight, conditions and gold rewards; put any event on the map / take it off, clear the map, random
  draw with the game's weights (one per place, one legendary, optional rules and category filter), reset cleared
  events, set time of day / Day-Night / weather. 6 tests. In-game effect UNVERIFIED (see FINDINGS).
- Records tab (`records.py`): all play counters (editable, range-checked), currencies, collection counts, plus the
  editor's own snapshot history per save (changes since tracking began). 3 tests.
- 62 tests pass. Exe rebuilt and smoke-tested headless (events, records, skill board, assets).
- Later: live clock in the Map tab (installed mod 0.3.0 GET/SET); mod 0.4.0 (PROBE / MAP_KEYS) in the repo only,
  install needs Unholy's OK. `build_exe.py` refuses to build while the editor runs from the target folder (a
  rebuild under the open window had deleted its files). Skill board restyled after the game's board (amber glow,
  grey links, lit paths in the Life's colour); double-clicking a License opens its board. 65 tests.
- Discord: `setup_info.py` (rerunnable, edits its own posts) writes the #welcome guide, #roles ladder,
  #fli-news (2.2.0 / 2.2.1 / 2.2.2, The Celestial Express DLC), #fli-gift-codes (all 11 codes; no region or
  platform split exists; reward effects/stars/sell prices from the item tables via `research/gift_items.py`),
  links in #fli-help-and-tips and an #announcements note. Creating the two new channels needs Manage Channels on
  the bot role for the run. `list_channels.py` prints the server layout (read-only).
- Discord per game (Unholy): news for each title and codes where they exist. `info_classic.py` holds the 3DS
  posts (status: Origin Island unbuyable since the eShop closed 2023-03-27, online ended 2024-04-08; all 42
  password rewards in 6 language columns + 2 Japanese) and Fantasy Life Online (shut down 2021 JP / 2023 global,
  expired code archive). Without Manage Channels the posts sit in each game's general/help channels; a run with
  it creates #fl-news, #fl-passwords, #flo-news, #fli-news, #fli-gift-codes and moves them (copies deleted).
  Done 2026-10-12: Unholy re-authorized the bot (OAuth URL adding Manage Channels to the Flutter role); all five
  channels created at the top of their categories, read-only, posts moved; #roles locked. `check_perms.py` shows
  the bot's roles and permissions (read-only).

## 2026-10-12: Backups tab (Tock)
- Asked for by players worried about corrupted saves. New Backups tab: the automatic backups (newest first, each
  re-hashed against its SHA256.txt, older PowerShell-written records with a BOM read too) with Restore on each,
  Back up now, Save a copy to... (native Save As dialog; copy kept only if its SHA-256 matches), Restore from
  file... (native Open dialog), Open folder. The exe keeps backups in `%LOCALAPPDATA%\StolenHours\backups`, the
  dev run in `backups\saves`.
- Restore (`savefile.restore_save`): the copy must decrypt and repack byte-exact before anything is touched, the
  game must be closed, the current save is backed up ("before-restore"), then an atomic swap and a byte check.
  The confirm dialog names the copy (character, island, Dosh, play time, in-game save date) and warns if it's
  from a different adventure (start date + island differ), identical to the current save, or if unsaved edits
  would be lost. Any account's save opens (the key is the game's, not per account), so restoring someone else's
  save onto yours is allowed after that warning; whether the game accepts a save from another Steam account is
  UNVERIFIED (check: restore a friend's copy, load in game).
- 72 tests (`tests/test_backups.py`: exact copy, list/intact flags, restore round trip, damaged copy refused with
  the save untouched, locked while the game runs). Exe rebuilt and smoke-tested.
- Unholy renamed his character to "Frank Jaeger" (with a space); the game loaded it and saved it back, so spaces
  in the avatar name work from a save. The game's text checker has "Text cannot include spaces"
  (`chat_error_include_space`); which inputs use it is UNVERIFIED (check: type a space in the in-game name entry).
- Apply vs Save to file confused him (the toast read like it saved), then the stale-file guard refused the save
  because the game had saved meanwhile. Fixes: the toast says "Not in your save yet: press Save to file", the Save
  button pulses while there are unsaved edits, and `api_state` reports `stale` (file on disk differs from what was
  loaded); with no edits the editor reloads by itself, with edits it says to Revert. Source done and tested in the
  preview; exe rebuilt and smoke-tested after Unholy closed the editor.

## 2026-10-12: Island name and play time editable (Tock)
- Unholy: a renamed island must look like it was the name from the start; play time likewise.
- `research/island_time_probe.py` and `research/playtime_copies.py` (read-only) checked the whole decrypted body:
  the island name occurs once (`m_PlayData.islandName`, ASCII, no UTF-16 copy), the header holds only version and
  save time, and there's no rename flag or history field. The game has its own rename ("Change the island's
  name? ... can be changed later"), so a changed name is a normal state. Play time is one u32 of seconds
  (`m_PlayData.playTime`); a u32 that matched the minutes near byte 1,137,000 in all three saves turned out to
  be a placed-object record number (326, 328, ... before `land_obj` / `Connect_All`). Other clocks:
  `startDateTime` / `saveDateTime` / header `realTime` are real-world dates; `envInfo.gameTime` is story-driven
  world time, not time played. Steam's hours are server-side.
- Editor: Island and Play time (hours + minutes) are editable on the Adventurer tab. Rename changes only
  `islandName`; play time only `playTime`, capped at the real time between start and last save (511 days on
  Unholy's save). The island name limit is 16 characters, no leading or trailing spaces, until the in-game
  limit is known (UNVERIFIED: check the in-game rename keyboard). Apply validates every field before changing
  any. Tests prove the rest of the save is byte-identical after each edit. 76 tests, exe rebuilt.

## Live Map viewer (2026-10-12)
- New Live Map tab: read-only view of the running game's map events and the player, drawn with the game's own map
  art (`minimap_Map_200000_000000`, 8192px), event icons, area glows and player arrow (`GDSMapIconData` ->
  `GDSMenuIconTexture`), in the game's draw order and per-zoom icon scales. The viewport is a scaled 1920x1080 game
  screen with the game's three zoom steps (1.2 / 2.5 / 4.0) and scroll margins from `Map_200000_GDSMapMinimap`.
  Polls every 1.5 s only while the tab is open; shows nothing while the game or mod is down, and says so when the
  installed mod is too old. Built by `mapview.py` (part of `build-ui`).
- World -> map: u = (maxY - Y) / range, v = (X - minX) / range with the table's +-120000 bounds; fitted on the art
  (`research/map_fit.py`: 99% of event places on land, zero offset). UNVERIFIED in game: check the player arrow.
- Active-event icons get material `mat_map_000012` (found via Blueprint bytecode: the extractor now reads script
  data for JSON exports; `MenuLayer_Map_Icon` class default `ExtMat_ActiveEvent`), a `basemat_ui_ripple_01` instance
  (RippleColor 0.6 grey, TimeSpeed 0.15, ripple count 1-6.5, MaskRadius 0.15). The shader is compiled, so the
  viewer's ripple is a stand-in. UNVERIFIED: ripple look, glow size, event -> icon rule (only 12 events carry
  `OverrideMapIconType`; the rest is native code; legendary = purpose point mapIconType 114). Check side by side.
- Mod 0.5.0, installed with Unholy's OK (old 0.3.0 main.lua + SHA-256 in `backups\mod\2026-10-12_214922_main.lua-0.3.0`): `EVENTS` (m_permanent.Active phase 1-3 + openActiveEventList) and `PLAYER`
  (pawn location, yaw, map). Lua tests cover both against the mock; the real container layout is UNVERIFIED until
  it runs in game. Live bridge now serialises commands (one mailbox).
- Tests 93 pass. Exe rebuilt and smoke-tested.
- Portable mod: the exe now carries the StolenHours mod (`hook/ue4ss_mod/StolenHours`) and installs/updates it on
  any PC from the Live Map or Time Hook tab (`modinstall.py`): needs UE4SS already in the game, game closed, backs up
  the old copy + mods.txt with SHA-256 (`%LOCALAPPDATA%\StolenHours\mod_backups` in the exe), copies, verifies
  hashes, adds `StolenHours : 1` before Keybinds in mods.txt. UE4SS itself is not shipped.
- Portability check (`research/portable_check.py`): no keys, mappings, Steam id or project paths in the build;
  a copy run from another folder with an empty LOCALAPPDATA finds the save, game and mod by itself. 97 tests.

## Promo video and Reddit draft (2026-10-12)
- Tour video: `Pictures\Stolen Hours\Stolen Hours - Tour.mp4` (1080p30, 68 s, captions under each tab, silent
  track). Built by `research/video/make_video.py` from the scene shots in `Pictures\Stolen Hours\video\` (temp
  save copy; Steam id and user paths masked on Records). Re-run the script after changing captions.
- Drafts for r/fantasylife and YouTube: `Pictures\Stolen Hours\Promo posts.md` (download link left as `<LINK>`).
- Released (Unholy's go): public repo https://github.com/UnholyScribe/StolenHours (README + screenshots only, no
  source; the local history has the Steam id and paths in docs/tests and needs a scrub before any source push).
  Release v0.1.0 = `G:\StolenHours-0.1.0-win64.zip` (206 MB, SHA-256 9D8A6E4A...AC521, matches GitHub's digest),
  built from `G:\Stolen Hours` after `portable_check.py` passed. Staging clone: `G:\StolenHours-repo`.
- Still open: a download host (the build is ~360 MB, 288 MB of it extracted game assets,
  mostly 3D models), permission/licence for the bundled Niedzielan fli_save_editor lists, and whether to ship the
  extracted game assets publicly.

## Live Map: every map and everything on it (2026-10-12)
- Side-by-side with the game at Medium zoom: player and event spots match; icon and glow size now take the
  minimap's mapIconScale (0.8 on Ginormosia).
- `mapview.py` now builds all 8 world maps (Ginormosia, Eternia Village, Capital of Mysteria, Faraway Island,
  Tropica Isles, Swolean Island, The Depths, Base Camp), each with its own art, bounds, zoom steps and scroll from
  `<map>_GDSMapMinimap`. `mapmarkers.py` adds what the map tables place: towers (15) and towns (6) from
  `GDSFastTravel`, campfires/workbenches/shops/statues/other places from `<map>_GDSMapFuncPoint`, shrines
  (`GDSTamagemonoShrineData`), dungeon entrances, Leafe, requesters, gathering spots (`GDSMapPickPoint`) and monster
  groups (`GDSMapEnemyPlacementConfig`, area-rank/quest variants dropped, Gold = strong, boss icon).
  UNVERIFIED: which of these the game hides until found/unlocked, shrine icon (138), and monster groups that
  depend on area rank (read area ranks from the save to fix).
- Live Map tab: map picker (auto-follows the player's map), toggle chips per kind with counts, searchable side list
  grouped by kind (click to centre), hover names, viewport culling. The map is usable with the game closed; live
  events show only on Ginormosia. Tests 97 pass.
- Released v0.2.0 (Unholy's go): exe rebuilt into `G:\Stolen Hours`, `portable_check.py` passes (now checks the
  per-map art instead of the old map.jpg), `G:\StolenHours-0.2.0-win64.zip` (213 MB, SHA-256 83CA5C09...CD0870,
  matches GitHub's digest). README: every tab screenshotted (Steam id/paths masked), credits "Unholy with his
  friend Tock". `__version__` 0.2.0.
- Reddit: account u/TheHourThief made for posting. The r/fantasylife post was auto-removed (account under 24 h);
  modmail sent asking about rule 4. Repost after 24 h once the mods answer.
- YouTube: tour video re-rendered (new Live Map caption, "Made by Unholy and Tock" card) and published public:
  https://youtu.be/HJLNRAUg9rw. Linked at the top of the GitHub README.

## Collection tab: recipes, library, gifts (2026-10-12)
- New `collection.py` (+ `build-ui` step -> `game/collection/collection.json`) and a Collection tab with three parts:
  Recipes (per Life, learned / not learned, kind filter, search, Unlock one or all shown), Library (monsters,
  gathering spots, Strangelings, characters, items; Fill in one or all shown), Gifts (add-on packs, LEVEL5 ID
  bonus content, built-in gift code, redeemed gift codes; Claim again / Claim everything again).
- Formats in FINDINGS (2026-10-12 recipes, library, gifts). Tests 101 pass (unlocks repack byte-checked, new recipe
  book handles follow the bag's pattern). Checked in the preview; nothing written to the save.
- Exe rebuilt into `G:\Stolen Hours` (portable_check: no leaks, nothing missing). Not released.
- Records: "Tamagemono" labels are now "Strangelings" (the game's English name).
- In-game menu (Unholy's screenshots): the Library is called Encyclopedia; Recipes, Outfits and Gifts (menu page 2)
  are their own menu entries. Tab labels follow the game.
- Unholy to test in game (on a backup): unlock a few recipes (crafting list), fill in a Library entry, Claim again
  on one add-on pack (Menu > Gifts). Redeem one gift code, then Claim again and re-enter it.
- Gift codes: the 11 public codes (same list as the Discord bot) with their rewards, Copy and Add to bag (puts the
  rewards straight in the bag, no code used). AF579XS2 (Raccoon set) is the game's built-in code rompass_0001
  (password_recieve_002): checked offline, so Claim again + re-entering it should work. The others are downloaded;
  which download flag (password_recieve_download_NNN) each one sets is unknown until Unholy redeems one.
  Tests 103 pass; exe rebuilt.
- Privacy audit (Unholy's ask): GitHub repo files + all 4 commits + commit messages/authors (noreply email), image
  pixels and metadata, release notes, repo description, both release zips (6669 files, ASCII + UTF-16 scan, no
  save/.bin/.hex/.env/history files, no key bytes; GitHub digests match), tour video file, promo text: no Steam id,
  account name, Windows user, paths, phone or keys. Collection state is read from whichever save is loaded.
- Outfit export: possible (30 look sets in `m_MySetStatus.viewEquipList`), on hold until Unholy wants it.

## Off-PC backup and rebuild blueprint (2026-10-13)
- Unholy's ask: a copy of the project plus a full rebuild guide in his Google Drive, in case the PC dies.
- `docs\REBUILD.md`: restore from backup, rebuild from scratch (toolchain, third-party pins, save format, editor
  layout, build-ui, exe, Mode B, tests), how to get each secret back, open UNVERIFIED items.
- Drive > My Drive > `Stolen Hours backup` (private): Google Doc "Stolen Hours - Rebuild Blueprint" (converted from
  REBUILD.md) and `StolenHours-project-2026-10-13.zip` (722 files, 41.8 MB, SHA-256 DD14DA9D...93518F).
  Left out: `aes_key.hex`, `pak_key.hex`, `discord_bot\.env`, and the 2.8 GB `build-ui` rebuilds. Scan: no
  token or key-file bytes; the save key does appear in Niedzielan's public editor scripts (already public).
- Drive's "Convert uploads" setting was switched on for the Doc upload and switched back off.

## Vulcan's Forge: craft out of game, pick the grade (2026-10-13)
- Unholy's ask: an out-of-game crafter named after the first game's blacksmith, where you choose what grade the
  item comes out as instead of guessing. Tab "Vulcan" (screen title "Vulcan's Forge", game hammer icon 000130).
- New `forge.py` (+ `build-ui` step -> `game/forge/forge.json`): 1633 recipe products, 850 of them gear with stats
  per grade, the grades they come in, the bonus stat and the skills that can roll per grade; 697 with a + version.
- Pick a Life and a recipe. Gear: pick Ordinary..Legendary (only the grades the item exists in, with the stat at
  each), bonus stat on/off, up to 3 skills from that grade's pool (shown as "+10% critical hit damage" etc.).
  Food/potions/etc.: Normal or + result. How many (1-99). Materials are shown, not taken. Marks the item obtained.
- Bug fixed on the way: `add_item` cloned the last item of a bag, so new gear (Bag tab and gift-code Add to bag)
  copied that item's grade, bonus stat, skills and equipped mark. Gear now starts from the bag's blank record;
  the Bag tab gives it the lowest grade the item comes in.
- Tests 109 pass (6 new: grade/bonus/skills written and repacked byte-checked, handles, stacks cap and full-stack
  refusal, rejects grades/skills the item can't have). Checked in the preview on a temp copy of the save.
- Unholy to test in game (on a backup): forge a Notable Bronze Sword with a skill, a Legendary armor piece and
  HP Potion +, Save to file, load, look at them in the bag.
- Quality added (Unholy's ask, after comparing with the first game): gear has two results in FLi, rank
  (Ordinary..Legendary, capped per item) and quality (Normal/Good/Great/Top from the minigame; save `Quality`
  0-3, names `name_item_quality_00N`). The forge now picks both (quality defaults to Top). The first game had one
  quality scale up to Divine (Divine Orb at Creator rank) on any item; FLi has no Divine. No item in Unholy's
  save has a quality yet, so Good/Great/Top showing and their stat boost are UNVERIFIED. Tests 109 pass.
- Released v0.3.0 (Unholy's go): `__version__` 0.3.0, exe rebuilt, portable_check passes,
  `G:\StolenHours-0.3.0-win64.zip` (213 MB, SHA-256 6C85F100...EC69A4, matches GitHub's digest; privacy scan of
  zip and images clean). README: Collection and Vulcan's Forge rows + screenshots. YouTube/Reddit not touched.
- Drive backup refreshed (project zip + Rebuild Blueprint Doc); the old copies went to Drive's trash.

## Bag shows what every item is (2026-10-13)
- Unholy's report: the Bag panel showed no stats, even for his forged Bronze Pickaxe. Item descriptions in the
  game tables are all the generic `desc_itm_common`, so the details come from the tables instead: new
  `game/items/details.json` (built with forge.json): stats per grade for 1168 gear items, effect lines for 306
  consumables (`effParam0..2` -> `GDSItemEffDescData` -> text, e.g. "Heal +300 HP"), 280 equipment skill texts.
- `/api/items` now sends each gear record's grade, quality, bonus stat, skills and equipped mark. The panel
  shows grade and quality tags, the stat at that grade, the bonus stat, skill texts and potion effects. The
  pickaxe reads Notable, Top quality, Power 200, Gathering, +10 Mining, +30 Max SP, -10% Charge-up time.
- Stat shown is the base for the grade; how much quality adds is UNVERIFIED (check: compare the in-game stat
  of a Top item with the table value).
- The dashed line above "Add to ..." (looked like a rendering strip) is gone; the band has a margin instead.
- Tests 110 pass (new: details table and the gear fields /api/items returns). portable_check needs details.json.

## Steam Deck and controller support (2026-10-13)
- Unholy's ask: fully runnable on his Steam Deck (Proton) and fully navigable with a controller, Xbox or
  PlayStation.
- Controller: new `web/pad.js`. D-pad/left stick move a blue highlight to the nearest control (anything with a
  click handler counts, so future tabs work without wiring); A press, B back, LB/RB screens, LT/RT page, right
  stick scroll, Start jumps to Save, View to the screen list. Dropdowns open a big list; number fields change
  with the D-pad; text fields take the Steam keyboard. Y gives a pointer for the maps, skill board and 3D preview
  (hold A to drag, right stick zooms). Hint bar with Xbox or PlayStation glyphs. Arrows/Enter/Escape do the same.
  Checked in the preview at 1280x800 with a simulated pad: title, Bag, Vulcan (dropdown, count), dialogs,
  Live Map drag/zoom, skill board panels and details, keyboard.
- Layout: the board's middle row no longer grows past the window (Save bar was off-screen below ~1000 px since
  the 11th tab); nav buttons shrink to fit; tighter frame under 860 px tall.
- Proton: new `deck.py` (Wine detection, Linux Steam folders and SD-card libraries as `Z:` paths, game-running
  check through /proc); under Wine the exe skips WebView2 and serves. `editor/deck/StolenHours-Deck.sh` +
  `STEAM_DECK.txt` ship next to the exe: the script picks the newest Proton, runs the exe in its own prefix,
  shows a "Starting" box, opens a kiosk browser (Edge/Chrome/Chromium/Brave/Firefox flatpak), and on exit stops
  only its own prefix. User data on Linux goes to ~/.local/share/StolenHours.
- Tests: `test_deck.py` (fake Deck under Z:, SD card library, flatpak Steam, /proc check, save lock) and
  `research/deck_launcher_check.sh` (WSL dry run with stub Proton and browser, all checks ok).
- UNVERIFIED until Unholy tries it on the Deck: real Proton run, Game Mode window, controller in the flatpak
  browser, game-running check. Live features (mod) not set up for Proton.

## Deck-synced save: buddies + houses (2026-10-15)
- Unholy synced the Steam Deck save. Probe: Kunugi + Duglas in `m_stFriendP` (handles 0x11000/0x11001),
  both in the party; Kunugi living on Base Camp. Three houses in `exParamHouse` (yours, guild, Kunugi's).
  Debris flags cleared for reclaim_01, guild, myhouse, and Depths B1 reclaim 00/01.
- Companions: friend handle base fixed to `0x11000`; add fills HP/SP/lifeStatus and seats party; remove clears
  party + island friend rows. Island tab lists houses. `rewalk --force --rebuild` refreshed UI tables (~246 s).
- UNVERIFIED: add a third buddy in the editor and load in game; gear handles for new buddies.

## Update failsafe: rewalk (2026-10-15)
- Unholy's ask: after a game update the editor must re-find the install and repopulate itself.
- New `rewalk.py`: fingerprints Steam `buildid` + shipping exe; on change (or Records > Rewalk game /
  `stolenhours rewalk`) re-discovers Steam/game/saves, re-scans the save AES key from the binary (stale
  `aes_key.hex` no longer blocks), optionally pulls FLi-FModel LATEST pak key + usmap into
  `%LOCALAPPDATA%\\StolenHours\\game_cache`, optional `--rebuild` for build-ui on the project PC.
- Startup: `ensure_assets` calls `ensure_current`. CLI: `rewalk` / `rewalk --status`. Tests: 4 pass.
- Portable exe: save key always recoverable from the game. Bundled UI tables still need a project rebuild to
  refresh after a content patch; cache still holds fresh pak/usmap for that.

## Island tab: debris, terrain, buddies (2026-10-15)
- Unholy's ask: all three maps (personal / past / big), clear debris for building, figure out terraforming,
  full companion list to edit in/out. Don't report until it's in the tool.
- Maps: Base Camp (`Map_000100`), The Depths + craft floors B1–B3, Ginormosia (`Map_200000`). Live Map already
  had the art; Island tab edits the save-side build state.
- New `island.py` + `companions.py` (build-ui -> `game/island/island.json`, `game/companions/companions.json`).
  Debris: 59 sync-flag sites; clear sets flag 255, zeros the craft object, drops the area handle (matches the
  cleared house on Unholy's save). Terrain: Shave-bit counts + reset. Buddies: 50 encyclopedia + extras, follower
  set/clear (Trip), add/remove friend slots (add path UNVERIFIED in game).
- UI: Island nav tab with Debris / Terrain / Buddies. Tests: 6 new (island + companions) pass.
- UNVERIFIED in game: clear a reclaim pile and load; reset Shave; add a buddy and load.

## Dashboard music (2026-10-15)
- Unholy's two *Last Chance Haven* loops converted to OGG under `web/music/`, listed in `playlist.json`.
  `music.js` cycles the list on end; Music on/off on the title screen and top bar (mute remembered).
  Add more tracks by dropping files in `web/music/` and appending to `playlist.json`.

## Village live editor (2026-10-15)
- Unholy's ask: edit the village like the guild build / decorate menus offline — map + live house view, place
  furniture and houses, in-game graphics, Legal/Free placement toggle.
- New `village.py` + `craft3d.py` + `village3d.js` (build-ui → `game/village/craft.json`, `game/craft3d/`).
  Catalog 1581 craft objects / 114 houses. Place/move/rotate/remove furniture; Legal consumes `invCraft`, Free
  ignores bag. Base Camp 2D footprints on Live Map art; My House 3D decorate (glb when extracted, else Size box).
  House place writes shell + `exParamHouse` (MyHouse room clone still UNVERIFIED — shell-only for forceMap houses).
- Island tabs: Debris / Terrain / Village / House / Buddies. API: `village`, `village_catalog`, `village_edit`.
- Tests: 5 village tests pass (grid roundtrip, state, free place/move/remove outdoors + indoors).
- UNVERIFIED in game: place furniture Legal + Free and load; move a house; new house shell with empty indoor list.

## Village / House UX pass (2026-10-15, later)
- Client loads full `game/village/craft.json` (English names). Village: pan + scroll zoom on Base Camp map;
  Build / House kits / Placed tabs; houses-on-island list. House: opaque room 3D, full orbit + zoom + pan,
  Furniture / Placed / Houses tabs (catalog was empty because API capped at bridges). Legal/Free kept.
- Boyle/Cooke research → FINDINGS (resident admin vs infrastructure kit shop). Kit-buy / plot UI still next.
- Cameras: Unholy asked zoom + 360° for house/village placement — on the list and wired for House 3D + Village map.

## Float-above Craft Mode (2026-10-15, evening)
- Unholy's refs: in-game Customization (Hagram float) + My House decorate + cyan footprint grid.
- Village tab is now outdoor Craft Mode: Base Camp map texture as terrain, orbit/zoom/pan above the craft pad,
  stylized thatched huts (wrong terrain glTF for houses skipped), cyan place cursor, Customization/Ground tabs.
- House: cutaway room (herringbone floor, wallpaper, open front), grid place, furniture by corrected indoor
  `gridIdx` (ix-major — earlier FINDINGS iy-major was wrong). Iterated in-browser against refs.
- Floor pass (2026-10-16): honey herringbone planks (not tile/checker); visual room is (N−1)×(N−1) so Wooden
  Bucket at grid (0,10) sits flush in the back-left corner like Screenshot 220942. Exe rebuilt.
- Craft glTF export names materials but leaves PBR empty; sibling Mat/*.json + Tex/*_dif.png are the real
  maps (same gap Look solved). craft3d.build packs WebP diffs into `game/craft3d/t/` + `_materials`,
  village3d binds them (MeshBasic — baked toon). Tropical Bed (`cft130001`) + Wooden Bucket (`cft000d0d`)
  on My House. Bulk ObjBP + Map child BP dump → ~1156 craft objects with meshes / 665 materials.
- My House shell (2026-10-16): no south doorway notch — continuous wood sill + exterior threshold decal
  (decorate mode). Wallpaper: ClampToEdge V, repeat.y=1, ~11/16 U slats; floor herringbone repeat ×0.25.
  Furniture drag: recursive raycast (outermost handle), OrbitControls gated in capture phase, Y=0 snap.
  Thick wall fill + inward wallpaper planes; cursor/drag clamped to floor cells.
- Village outdoor (2026-10-16): UE→Three `Z = −Y/100` (−Z north, +Z south); yaw `−saveYaw` (doors south after
  the Z flip). Removed soft X-marks; guild square is a flat decal; structures ray-snap to terrain; craft rim
  is an elevated LineLoop with polygonOffset (no filled craft-pad plane).
- Outdoor house yaw (2026-10-16): craft glTF doors sit on local **+X** (not +Z). Outdoor Three yaw is
  `−90° − saveYaw` so saveYaw 0 faces south (+Z); Thatched 90 faces west toward the guild; islander 180
  faces north. Stub hut door moved to +X to match.
- Base Camp env extract (2026-10-16): `asset_extract world` mode (CUE4Parse `WorldExporter` → USD) on
  `Map_000100` + mod/obj/env; `mesh` export of `mdl_map000100_*` → glTF. `map3d.py` packs 58 island
  chunks into `web/game/map3d/`; Village outdoor loads them (Z-mirrored to match craft `Z=−Y`) under the
  craft heightfield. `Map_000100_env` alone is mostly sky — real land is world-baked map meshes + BP
  props in `_mod`/`_obj` (many BP instances still lack per-actor mesh refs in the USD).
- Live Village + loadouts (2026-10-16): mod **0.7.0** adds `CRAFT_STATUS` / `CRAFT_LIST` / `CRAFT_TELEPORT`
  (move live `CraftObjActorBase` while Customization is up — persist with in-game Save). Village UI shows
  Live linked banner + unlock craft cam. Offline **village loadouts** in `%LOCALAPPDATA%/StolenHours/village_presets/`
  (export/import Base Camp placeables; quit game before Apply). Ship meshes dropped from map3d pack.
- Procedural Base Camp terrain (2026-10-16): `village.terrain_grid` packs even-cell `land_obj`/`water_obj`
  stacks into a height field; Island → Terrain shows plateaus + 2-segment cliff bevels + cyan water plane
  (world-space UVs on craft grass/cliff Diff textures). Raise/Lower/Level write stacked tiers via
  `terrain_raise`/`terrain_lower`/`terrain_level` (in-game parity UNVERIFIED) and rebuild the craft sub-mesh in place.
  Village outdoor also loads the same grid so houses snap to hills.
- In-game house shells (2026-10-16): ObjBP thatched houses child to `BP_MJFp_Building_cft00030x` —
  those glbs ARE the house bodies (door/bird/propeller), not bare land. Extracted cft000300–30b + guild
  cft000b*; craft3d manifest now 1238 meshes. Village loads house glTFs with Diff bind; stylized hut is
  fallback only. Placement cursor cyan/red by footprint tier/water check. Walk/Explore toggle (WASD
  capsule on terrain) additive beside Build view. Room `setWallpaper`/`setFloor` APIs tagged on shell.
- Buddies / Guild desk (2026-10-16): outdoor buddy stubs with nameplates near assigned houses; Village
  side panel Boyle strip (island name, residents, debris jump) + Cooke kits note. Direct kit shop and
  buddy→house assign write still next (UNVERIFIED wiring).
- White village houses fix (2026-10-16): server served craft3d `.webp` Diff maps as `application/octet-stream`
  (MIME unset) so WebView2 TextureLoader left MeshBasic maps blank → white shells. Registered `image/webp`.
  Also prefer `Base_Texture`/`Diff_Texture` over RSE-stuffed `PM_Diffuse` for thatch grass mats.
- Village is a 3D island now (2026-10-16): dropped the big static map JPG as walkable ground. Craft height
  field + cliff skirts + ocean hull are the Base Camp; map art is a faint undersea hint only. Oblique
  Customization camera, stronger sun shadows, grass Diff (not RSE) on plateaus. Full `Map_000100_env`
  level mesh still not extracted (UE sublevel) — procedural craft island is the stand-in.
- Customization ref pass (2026-10-16): Unholy’s in-game screenshots in `notes/refs/customization/`.
  Soft 3-segment cliff lips + stratified soil tex, shore foam, cyan tile cursor + gem, occupancy X marks.
- Static-looking island fix (2026-10-16): save already had height tiers (h=0/1/2) + 1361 water cells, but water
  sat coplanar with grass and land→water edges skipped cliffs — read as a flat stamp. Water now recessed
  0.42 m, land cliffs drop into canals/ocean. Brown slabs cause: house `*_grass_dif` is thatch foliage on
  black, not ground — replaced with procedural Customization carpet (`grassCarpetTex`). Map env (beaches /
  volcano outside yellow pad) still not extracted.
- Free camera zoom (2026-10-16): StolenHours UE4SS 0.6.3 — F8 on/off, **F6 zoom in / F7 zoom out**
  (Ctrl+ = big step). Craft cams use CameraLenBase (no Max) — one-shot Base write, tick never rewrites
  Base. Survey shots in `notes/refs/customization/survey_*` = full Base Camp + yellow craft pad.
- Pad surveys `pad_01`…`pad_05` (2026-10-16): frame Village on yellow craft AABB (not house cluster).
  Save layout: Guild north of thatched huts matches pad_* with −Z = north.
- Close-ups `close_01`…`close_08`: felt grass carpet, dark + cell marks, blue flower tufts, cyan gear
  cursor (not plain octahedron).
- Next (Mode B, after Village look): **Celestia vacuum** — sparkly island flowers (`Q` Collect Celestia /
  “Celestia's Gift” in Customization) are goddess currency and respawn. Unholy wants live collect-all while
  the game is rendering (track spawned pickups → one button). Offline save edit may not cover world spawns.

## Next (Unholy's order, 2026-10-12)
0. Side-by-side: in-game map vs Live Map (icons per event kind, glow size, ripple, player arrow position and
   facing). Mod 0.5.0 is installed.
1. Unholy: test in game. Put a rare event on the map (e.g. a legendary hunt with "Follow the game's rules" off),
   Save, load the game, check the map. Same for time/weather. Learn a panel behind a blank in the board editor.
2. Live Map/time hub: read and set the running game's events and clock through the mod (`GDDQuestData.m_volatile
   .ActiveEventStatusV.openActiveEventList`, `m_permanent.ActiveEventInfo`, `envInfo.gameTime`). Needs an update
   to the installed mod: ask Unholy first. Mod GET also needs the struct-value fix (below).
- 3D preview: glasses socket; `ModelId2` second tool piece (socket UNVERIFIED).
- Ship to Unholy's brother: test the exe on a second PC (needs WebView2, standard on Win10/11).
- Unholy: launch the game, load the save. Tock: `live dump` (crash-safe now), then the reversible test
  `live get GDDPlayData m_permanent.Money` / set +1 / restore, and check Dosh on screen.
- Map properties (life levels/exp) in the dump and GET.
- Unholy: first real edit (e.g. `set-money`), launch, confirm Dosh in game. Then try `add-item`.
- Unholy: compare the Life menu with `StolenHours.cmd lives` to confirm life id names.
- Unholy: launch through Steam, load the save. Then Tock reads `ue4ss\UE4SS.log` and runs `live ping`, `live find Money`.
- Map `m_AvatarStatus` (appearance) once the above works.

