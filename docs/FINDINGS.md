# Findings: blueprint vs. the real game

Verified facts only. Each entry: date, what was checked, result.

## 2026-10-11 (setup, read-only checks)

| Blueprint says | Real game | Status |
|---|---|---|
| Save dir `C:\Program Files (x86)\Steam\userdata\<id>\2993780\remote\` | `<Steam>\userdata\<account>\2993780\remote\` (custom Steam path) | Verified |
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
| UE4SS on the current build | Works: UE4SS experimental 3.0.1-1164 detects UE 5.4, all Lua mods start, StolenHours mod answers PING (2026-10-11 19:47 log). | Verified |
| Money as a reflected property | No reflected **class** declares `Money`/`Dosh`/`Gold`. `/Script/DP1Project.SaveData` **is** a reflected class with `m_PlayData`, `m_CharaStatus`, `m_InventoryStatus` (same names as the save), but no live instance exists in the field. `Money` is likely a field of the reflected struct behind `m_PlayData`; the live owner is still unknown. | Verified (class); owner UNVERIFIED: check with `live dump` |
| Live owner of Dosh | Transient `GDD*` objects mirror each save section (`GDDPlayData`, `GDDCharaStatus`, `GDDInventoryStatus`, `GDDAvatarStatus`, `GDDFlagStatus`, ...). Dosh = `GDDPlayData.m_permanent.Money` (dump value matched the save, 14633). Character = `GDDCharaStatus.m_permanent.m_stAvatarP`. | Verified (read, from the 19:57 dump); writing it UNVERIFIED: check with `live set GDDPlayData m_permanent.Money` and the in-game Dosh display |
| Dumping every object | Reading `ObjectProperty m_basePanel` on a `NumPrimitive` widget inside a menu `WidgetTree` crashed the game (ACCESS_VIOLATION in UE4SS). Mod 0.3.0 skips UMG/Slate/Anim classes and `WidgetTree` paths and dumps `GDD*` first. | Crash verified; fix UNVERIFIED until the next in-game dump |
| `AFLiWorldManager` etc. | Unknown. Runtime class/property names must be discovered in game (`live find Money`). Save structs (`PLAY_DATA_P`, ...) look native and may not be reflected at all. | UNVERIFIED |
| Crash-safe dump | Mod 0.3.0 dump finished in game twice (16,442 objects, 0 errors, 2026-10-12 06:28). | Verified |

## 2026-10-12 (3D preview, held items)

| Question | Answer | Status |
|---|---|---|
| Equipment handle | `(slot+1)<<18 \| pocket<<12 \| slot`; pocket = category index (1 weapon, 2 life tools, 3 shield, 4 armour). | Verified on Unholy's save (all equipped handles decode to the right items) |
| Held item mesh | Item `modelID` (`mdl_wpn*`/`mdl_sld*`); skeleton `root > R_hand_item_tag > wpn` (shield `L_hand_item_tag > sld`), all identity. In the menu, `CaptureMenuAvatarActor.RHandWeaponMeshComponent` / `LHand...` attach to `BodyMeshComponent` at socket `R_hand_item_tag` / `L_hand_item_tag`, relative scale 1. | Verified (assets + live GET) |
| Weapon scale | No per-item, per-type or socket scale: `GDSItemEquipModelData`/`OffsetData`, skeleton sockets, anim tracks all neutral; `GDCharaModelData.RHandSocketScale` is 1.0 for avatars and live. | Verified |
| Body sizes (GDSAvatarBodyData) | Applied by `Avatar_BoneModify_AnimBP`: `LocalToComponentSpace -> CharamakeBoneModify -> ComponentToLocalSpace`, so a bone's size scale does not carry to its children (hands, held items). | Graph verified; exact native math UNVERIFIED (matches Unholy's Miner/Paladin screenshots) |
| Equipment-screen idle per life | `Avatar_Equipment_AnimBP` state machine per tool type, `<prefix>_idleEquip`. | Verified |
| Armour mesh chain | `GDSItemArmorData.modelID` -> `GDSItemEquipModelData[model].EquipModelList` (mesh paths). Slot from the `GameData/Wear/GDSWear{Hat,Body,Bottom,Hand,Feet,Cape,Accessory}ModelData` tables (`Body.IsDress`). Gloves list 4 meshes (TypeName 0-3: right, left, right open, left open, like the bare hands). | Verified (data) |
| Hats / capes | Skinned to `root > hat` / `root > cape...`; the avatar skeleton has sockets `hat_item_tag` (under head) and `cape_item_tag` (under spine). Preview attaches them there like held items. | Bones verified; socket use matches the screenshots, native attach UNVERIFIED |
| Hair under hats | `GDSItemEquipModelHairTypeData[model].HairModelInfoList`: `None` = default type, or per-hair overrides; types A (bare), B, C, D (shared `Avt1001_hair/mdl_avt_hair_typeD`). | Verified (data) |
| Dress tops | `IsDress` tops: preview hides the bare bottoms. | UNVERIFIED: wear a dress with bottoms equipped and compare in game |
| Glasses (`mdl_acs*`) | Unskinned static meshes; socket not found. Not drawn. | UNVERIFIED: find the glasses mesh component's AttachSocketName live |
| Main character's live gear | `BP_CtrlCharacterBase_C` (field player) `ViewEquipModelInfoSet[EquipSetCurrentIndex]` (6 sets; slots weapon, shield, Head, tops, bottoms, arm, foot, mantle, glasses, sub; model names, appearance applied). The `RPG_MainChara` menu actor reports the same sets. | Verified live (Paladin starter set, matches the save's life0001 gear) |
| Life starter armour | `GDSLifeData.default{Head,Tops,Bottoms,Arm,Foot,Mantle,Glasses}Id` -> armour items. | Verified (data) |

## 2026-10-12 (skill boards)

| Question | Answer | Status |
|---|---|---|
| Board layout | `GDSSkillBoard`: `sb_life0001`..`sb_life0014` (no board for Brand New); panels with hex cell `indexX/indexY`, `parentNo`, `skillPoint` cost, `flagNo` (life N: N*100-99 upward), `isLifelimit`. Panel content: `GDSSkillPanel.contentID` -> `GDSSkillData` (`skillIconType` 1 stat, 2 technique, 3 unique). | Verified (data) |
| `m_autoBin` args | 16-byte header; argument at 16 + `m_offset` = tag byte + int32; tag 0x34 = offset into `m_autoStr`, 0x32 = integer. Conditions: `LicenseRank_Over(para, life, rank)`, `GainedSkillPanelNum_Greater(board, n)`. | Verified (decodes to sensible ids/values; "SP +10 Max SP" matches the game) |
| Learned panels in the save | `m_FlagStatus.skillPanelBitFlag[flagNo]` = 1 (one element per flag). Unholy: 11 Miner panels, matching "11/64" on screen; their costs sum to 51 = Miner `skillMaxPoint`. | Verified |
| Grid | Square grid (parent/child offsets are axis-aligned; the start panel's first branches sit 2 cells away), not hex. | Verified (data, matches Unholy's screenshots) |
| `skillPanelUnlockBitFlag` | Set on a conditional panel whose parent is open and whose condition holds; recomputing it from the rule reproduces the save exactly. | Verified on Unholy's save (`test_unlock_rule_reproduces_save`) |
| Spendable SKL points | `skillMaxPoint` = running total of `GDSCharaLevelConfig.skillPoint` up to the life's level (lv 11 = 43, lv 13 = 51, lv 100 = 500); free = that minus the costs of learned panels. "SP +" skills are battle SP. | Verified (Brand New and Miner match) |
| Blank panels | `isBlankPanel`, cost 0, not counted (Miner "11/64" = 73 - start - 8 blanks). Treated as pass-through; their flag is never set. | Count verified; pass-through UNVERIFIED: learn a panel behind a blank in game, diff its flagNo |
| `GainedSkillPanelNum_Greater n` | Treated as >= n (like `LicenseRank_Over`, which is >= on the save). | UNVERIFIED: no panel on the save sits at the boundary |
| Board art | `tex_icon_skillboard_0000<family><shape>`: shape 0 technique, 1 unique, 2 stat; family 0 dark, 10 gold lock, 11 open lock, 2/4/6 grey available, 3/5/7 learned blue/green/pink (combat/gather/craft); halo `00020x`; paper `tex_skillboard_001000`. | Verified (matches the game's board screenshots) |

## 2026-10-12 (map events, time, records)

| Question | Answer | Status |
|---|---|---|
| Event types | `GDSActiveEventTarget.ActiveEventType` = EActiveEventType: 1 Battle, 2 Pick, 3 Delivery, 4 PickThenBattle (5-11 dream dungeon). | Verified (live schema dump enum) |
| Event draw | `GDSActiveEventLottery`: `lottery_qsf_common` (solo overworld), `_multi`, `_gauge_event` (the `_multi` legendary gauge events). Per lot: `Rate`, `rateOnFar`, conditions `GameTimePeriod_IsNight/IsDay`, `AreaRankRelease_Greater(area, rank)`, `LicenseRank_Over`, `IsWeatherType(2 = Rainy)`, `GetGlobalBitFlag_True(flg_enemy_village_0N, GlobalBitFlag idx 3300+)`, `IsPlayingRoguelike_True` (dream only). Weights: legendary hunts 10-39, rare bosses (Evil Primeval, Dragon Dare, Lordly Shark?) 26, deliveries 32, "Take Down All Monsters!" 40, gathering 146, named monster events 166-1000, specials 890. | Verified (data) |
| Live draw parameters | `appearActiveEventNum` 10 (solo) / 25, `excludeClearedActiveEventPlaceFromLottery` true, `preventLegendEventMultipleEmergingOnSolo` true, `initialActiveEventAppearNum` 2, `activeEventIncreaseNumByOpenArea` 2, `condCmdActiveEventTimePeriodChangeDefaultThreshold` 1. No event lifetime in the tables. | Verified (live values dump) |
| Event state in the save | `m_QuestStatus.Active[id]` {phase, isNew, tmpFlagList}; phase = ETemplateActiveEventPhase 0 None, 1 Emerge, 2 Progress, 3 second phase, 254 Achieve, 255 End. `m_QuestStatus.ActiveEventInfo` = Map<id, {s8 timePeriodChangeCount}>. Unholy's save: all 1392 at phase 0, ActiveEventInfo empty (story chapter 3, only 15 areas, all rank 1). | Fields verified; "on the map = phase 1 + ActiveEventInfo entry" UNVERIFIED: emerge one in the editor, load, look for the map icon (or let the game spawn one, save, diff) |
| Game time | `m_PhaseInfo.envInfo`: `gameTime` float, `gameTimePeriodType` (0 Day, 1 Night), `overwriteGameTime` FLT_MAX = unset. Read as game minutes: 2110.58 = day 2, 11:10, Day. Story phases pin the clock (`GDSWeatherTimeZoneLimitConfig` hour/min); across three live dumps it only moved 2110 -> 2125. | Units UNVERIFIED: set a time, load, compare the in-game clock |
| Weather | `m_WeatherStatus.WeatherInfo[3].weatherType` = EWeatherType 1 Sunny, 2 Rainy, 3 Cloudy. | Enum verified; what each of the 3 entries is for UNVERIFIED |
| Area names | `GDSAreaDef.m_areaNameId` -> `GDSMapText_Noun`: map200000_area001..015 (West Dryridge Desert .. Fangshore Isles). | Verified (data) |
| Play counters | `m_PlayData.playCountData` (PLAY_DATA_COUNT, 43 fields: u32 counters, `developmentRank` s32, `islandPurchaseNums` Array<u32>, Map<u8,u32> per enemy type / weapon). Plus `m_PlayData` goddessHerbBlue/Gold, sweetChestnut, interactionPoint (s32), ArenaRank (u8), plantdungeonMaxReachGen, playTime, start/saveDateTime (.NET ticks). | Verified (pattern + save). On Unholy's save only pickOreNum 37 and instantCharaJoinNum 1 are non-zero, so when each counter starts counting is UNVERIFIED |
| Lifetime totals | The save keeps no Dosh-earned or similar totals; the editor snapshots each save it opens (`USER_DATA\records_history.jsonl`) and shows changes since the first snapshot. | n/a |
| Achievements | `GDSAchievementList` does not decode with the current mappings; `GlobalAchievementReceiveFlag` is all 0 on the save. | UNVERIFIED: needs a newer usmap or a save with an achievement |

## 2026-10-12 (recipes, library, gifts)

| Question | Answer | Status |
|---|---|---|
| Recipes | `GDSRecipeData`: 2012 recipes `recipe_lifeNN_<item>` (Cook 150, Blacksmith 558, Carpenter 466, Tailor 475, Alchemist 143, Artist 220), product `ItemId`, rarity, Category = `GDSRecipeTabData` tab. `GDSItemRecipeData`: 2011 recipe book items `irp_...` with `flagNo` (only `recipe_life13_iam01009000` has no book). Save: `m_RecipeStatus.recipeInfoMap` has all 2012 with `bitFlag`. | Verified (data + save) |
| A learned recipe | All 10 learned recipes on Unholy's save have bitFlag 9, `GlobalItemGetFlag[flagNo]` 1 and the book in `invRecipe` (2048 slots); the other 2002 have none of the three. The editor's unlock sets all three. | Pattern verified; that the game accepts it UNVERIFIED: unlock one, load, open that Life's crafting list. Meaning of bits 0 and 3 unknown |
| Item handles | Every bag: handle = `((slot + 1) * 4) << 16 | (bag base + slot)`; bases: Consume 0x0000, Weapon 0x1000, Material 0x7000, Recipe 0x8000, Important 0x9000. Same as `add_item`'s neighbour +0x40001. | Verified (save, 5 bags) |
| Library | `GDSLibraryListData` 385 entries (Category 0 monsters 148, 1 gathering spots 138, 2 Strangelings 49, 3 characters 50), FlagID -> `GDSLibraryFlag.idx` -> `GlobalLibraryFlag` (seen) and `GlobalLibraryNewFlag` (new mark; on the save, set for the seen entries not opened yet). `GDSLibraryItemData` (875) is "where to find" hints per item; items count through `GlobalItemGetFlag`. Names: monsters/characters `GDSCharaText_Noun name_<id>`, gathering spots `GDSPickParamData.namePlateIconInfo.textId` -> item nouns, Strangelings `GDSTamagemonoData.charaID` -> chara nouns ("tamagemono" is "Strangeling" in English). | Verified (data + save: 14 flags set, all resolve); filling entries in UNVERIFIED in game |
| Gifts | Receive flags in `GlobalBitFlag` (`GDSGlobalBitFlag`): add-on packs `aoc_recieve_01..32` (7500+; `GDSAOCCommonData`: 01 New Adventurer's Pack, 02 Deluxe Edition, 05 Pegasus, 06 Unicorn, 07 True Gentleman's, 08 Jibanyan) with `aoc_new_NN` (7400+), LEVEL5 ID bonus content `level5_id_status_recieve_001..010` (8300+), built-in gift code `rompass_0001` -> `password_recieve_002` (7601; `GDSPasswordData`, codes stored as 16-byte hashes), downloaded gift codes `password_recieve_download_001..299` (7700-7998), compensation `compensation_receive_001..300` (5500+). Contents in `GDSAOCAddItemData`. Gift-code packs (`name_PasswordPack_00..31`) have no local table: they come down when a code is redeemed. Unholy's save: aoc 01/02/05/07/08 received, no gift code yet. | Flags verified (data + save). Re-claiming by clearing the flag UNVERIFIED: clear one, load, Menu > Gifts (packs), re-enter a code (gift codes; the server may also refuse) |
| Built-in gift code | `rompass_0001` gives Raccoon Head/Outfit/Mittens/Boots (iam02000070-100) = public code AF579XS2. Its stored password `4HViuFrkz/++OfIvXfyfpw==` is not a plain MD5/SHA1/SHA256 of the code (UTF-8 or UTF-16). | Match by rewards; hash scheme unknown |
| Outfit sets | `m_MySetStatus.viewEquipList[life0000].equipList` has 30 look sets (`abilityEquipList` 10 per life) with weapon..glasses handles. | Layout verified (save); not used yet |

## 2026-10-13 (crafting results, Vulcan's Forge)

| Question | Answer | Status |
|---|---|---|
| Item grade | `itemTitle` on every gear record = `EItemTitleType` 1 Rag "Ordinary", 2 Normal "Fine", 3 Masterpiece "Notable", 4 Supreme "Supreme", 5 Legend "Legendary" (`GDSItemTitleData` -> `name_item_title_00N`). Starter weapon has 0. | Verified (data + save) |
| Grade per item | Stats per grade (index grade-1): Weapon `physicalOffenseList`/`magicOffenseList`, LifeTools `lifeParamList`, Armor (shields too) `physicalDefenseList`/`magicDefenseList`. Value <= 1 on every list = not made in that grade (Bronze Sword 180/210/250/1/1). Weapons/tools have one recipe per grade (`_01`..`_03`, `titleType` = that grade); armor recipes have titleType 0 and the craft decides; armor stats are the same at every grade. | Verified (data) |
| Bonus stat and skills | Per grade: `addStatusLotTableList` -> `GDSAddStatusLotTable` (EEquipStatusType: 1 HP, 2 SP, 3 PhysicalOffense, 4 PhysicalDefense, 5 MagicOffense, 6 MagicDefense, 7 Crafter, 8 Gatherer); `addSkillLotTableList` -> `GDSAddSkillLotTable` (284 tables, `lotWeight` > 0 can roll). Save: `addEquipStatus` [{Type, Value 0}], `grantSkillId` 3 names. Unholy's Fine Bronze Sword: Type 3 + es_elements_fire_attack_up01; Fine Bronze Hammer: Type 7 + es_recipe_up_blacksmith_04; Ordinary Bronze Shield: Type 4 + es_damage_alleviation_02. Value is 0 everywhere. | Layout verified (save). Game accepting any grade in the window, any pool skills (up to 3) and computing the bonus from Value 0 UNVERIFIED: forge one, load, open it in the bag |
| Better consumables | Separate item ids: `GDSRecipeData.rewardData.rank2_itemId` (700 recipes) e.g. ics01000580 HP Potion -> ics01000590 HP Potion +; `GDSItemQualityGroup` has the same pairs (729). | Verified (data) |
| Craft quality | Separate from grade: `Quality` on gear = `EItemQualityType` 0-3, names `name_item_quality_000..003` Normal, Good, Great, Top. Players report the minigame gives Good with 3+ turns left, Great 5+, Top 7+. Every gear item in Unholy's save has 0. | Names verified (data); Quality 1-3 showing and raising stats UNVERIFIED: forge Top, load, check the item |
| Blank gear record | Every empty gear slot holds a full default `InventoryInfoEquip` (title 0, Type 0, skills None, not equipped); `add_item` now builds new gear from it. | Verified (save) |
| Item details | Item `DescId` is `desc_itm_common` (empty) on every item, so the Bag shows table data: gear stats per grade (as above), consumable effects `effParam0..2` {val, Time, effDescId} -> `GDSItemEffDescData`.DescId -> `GDSItemText` with `<ITEM_EFF_VAL>`/`<ITEM_EFF_TIME>` (ics01000590 "Heal +300 HP"), skill text from `GDSSkillData`. | Verified (data) |
| Item prices | `priceInfo.priceSellRichList` / `priceBuyRichList` are 5-entry lists; gear indexes by grade-1 (ilt02000020 sell [550,920,1480,0,0]), other items use entry 0 (ics01000590 sell 60, buy 190). Whether quality changes the price is UNVERIFIED (check: sell a Top-quality vs Normal copy in game). | Verified (data) |

## 2026-10-15 (update failsafe / rewalk)

| Question | Answer | Status |
|---|---|---|
| Detect game update | Steam `appmanifest_2993780.acf` `buildid` + shipping exe size/mtime, stored under `%LOCALAPPDATA%\\StolenHours\\game_cache\\fingerprint.json`. | Verified (buildid 24685570 on this install) |
| Save key after update | `resolve_key` only keeps `aes_key.hex` if it still unpacks the save; otherwise re-scans every install's shipping exe. Startup `ensure_current` rewalks when the fingerprint changed. | Verified (offline rewalk source `game:...`) |
| Pak key / usmap | Optional fetch of FLi-FModel LATEST into `game_cache\\pak_key.hex` + `mappings.usmap`; `build-ui` prefers the cache. | Fetch path coded; LATEST match to every Steam build UNVERIFIED |

## 2026-10-15 (island build, debris, companions)

| Question | Answer | Status |
|---|---|---|
| Three maps | Personal = Base Camp `Map_000100`; Past = The Depths `Map_000101` (craft floors `Map_000202`/`212`/`222`); Big = Ginormosia `Map_200000`. Live Map already had all three plus the story islands. | Verified (GDSWorldMapData + obstacle tables) |
| Debris clear | `GlobalSyncByteFlag[idx]` = 255 when cleared (`GDSGlobalSyncByteFlag`); matching `craftObjStatusP` (`refCraftObjId`) is zeroed and its handle drops from `craftObjStHdlArray`. Sample: `obstacle_Map_000100_myhouse` flag 255 and `obstacle_myhouse` gone after Unholy cleared the house in game. `obstacleReleaseNum` still 0 there — counter vs flags UNVERIFIED. | Flag + craft wipe verified (save); editor clear load-tested UNVERIFIED |
| Terraform | `craftObjStatusPArray` `land_obj`/`water_obj`; `objStatusBitFlag` bit 1 = `Shave`. 314 Shave cells on Unholy's Base Camp. Exact raise/lower meaning UNVERIFIED (toggle one cell, load, compare height). | Structure verified (pattern + save) |
| Companions | Follower = Trip `chr100400`. Friends = `m_stFriendP` (64). Deck-synced save: Kunugi `para_chr002500` handle `0x11000`, Duglas `para_chr000a00` handle `0x11001`; both in party slots 1–2. Kunugi also in `CraftAreaInhabitantInfo` + `CraftAreaFriendNpcInfo` (living on Base Camp). Friend handle base = `0x11000` + slot. | Layout verified (Deck sync); editor add-friend load-test UNVERIFIED |
| Houses | `CraftExParamP.exParamHouse`: your house `house_icf01020030` → `Map_MyHouse`, guild `house_guild_thatch`, buddy house `house_icf01021030` → `NPCRoom_002500` (Kunugi). Matching craft objs `obj_icf01020030` / `obj_icf01021030` on Base Camp. | Verified (Deck sync) |

## 2026-10-15 (village live editor)

| Question | Answer | Status |
|---|---|---|
| Placeable catalog | `GDSItemCraftData` (1483, Category 70 → `invCraft`) → `GDSCraftObjData` (1629) → `GDSCraftObjVisualData` (Size + ObjBP). Editor `game/village/craft.json`: 1581 placeables, 114 houses. | Verified (tables) |
| Craft area lists | `m_CraftAreaStatus` map / outdoor / indoor / wall / ceiling (256 each). Base Camp map area 160×128×6, voxel 50×50×150. My House indoor 12×12×4, voxel 50×50×100. | Verified (save) |
| Numeric `mapId` | `craftObjStatusP.mapId` is int (Base Camp `1807587003`, MyHouse `535592167`, NPCEmptyRoom `616711470`). Not CRC32/FNV of the string id; not in GDSMapData. Editor learns it from existing objects on each area. Hash algorithm UNVERIFIED. | Observed; encode UNVERIFIED |
| gridIdx | Outdoor and indoor both use ix-major: `ix * Width + iy + iz * Width * Depth`. (Earlier indoor iy-major note was wrong — MyHouse Tropical Bed grid 25 + Wooden Bucket grid 10 confirm ix-major.) Location = origin + cell × voxel. Base Camp origin = land_obj at grid 0 `(-3150,-3950,-150)`. | Verified outdoor 6574 cells; indoor re-verified 2026-10-15 |
| Craft handles | `(serial << 16) \| arrayIndex` (signed int32). New place: empty slot + max(serial)+1. House exParam handles `0xFF010000+n`. | Verified (save pattern); new alloc load-test UNVERIFIED |
| Legal / Free | Legal consumes/restores `invCraft` stock; Free ignores bag. Default Legal. | Coded; in-game place sync UNVERIFIED |
| Meshes | Visual `bpPath` → ObjBP → often ChildActor under `Program/Map/{Bench,Bed,…}` → `Graphics/3D/Craft/cft*/Mdl`. Preview uses extracted glb or Size box. | Partial extract; full catalog mesh wire UNVERIFIED |
| House exterior meshes | Thatched / islander houses (`BP_icf01020xxx`) child to `MapJumpFp/Building/BP_MJFp_Building_cft00030x`. The `mdl_cft00030x_*` glbs are the house shells (nodes: door, bird, propeller, base) with thatch grass mats — not the craft land pad. Guild offices use `cft000b00`/`cft000b01` StaticMesh soft paths directly. Door nodes sit on local **+X** (guild doors at X≈1.05, Z=±0.65). | Verified (ObjBP + glTF node/mat inspection 2026-10-16) |
| Outdoor craft yaw | Save Rotation[1] with outdoor `Z=−Y`: Three Y quat = `−90° − saveYaw` so yaw 0 faces south (+Z). Matches door-on-+X meshes (Thatched 90 → west toward guild; islander 180 → north; guild 0 → south). | Verified vs door node axis + save yaws 2026-10-16; shot-for-shot Customization still UNVERIFIED |
| Base Camp level mesh | Persistent `Map_000100.umap` streams `_mod` / `_obj` / `_env` / walls / events. `_env` ≈ sky + 3 StaticMeshActors. Island land is `Graphics/3D/Map/Map000100/**/mdl_map000100_*` (world-baked verts) plus hundreds of BP `GameStaticMeshComponent`s in `_obj`/`_mod`. CUE4Parse World→USD exports SMA + streaming; BP mesh refs often missing. | Verified export 2026-10-16; full BP prop parity UNVERIFIED |
| map3d pipeline | `asset_extract` modes `world` (USD) + `mesh` (glTF); `stolenhours.map3d` builds `web/game/map3d/` for Village. | Coded; in-editor framing vs Customization UNVERIFIED |
| Live craft actors | `CraftObjManagerSubsystem` lists `CraftObjActorBase`; layout state on `CraftObjLayoutManagerSubsystem`. Mod 0.7 teleports actors by handle. New place spawn via UFunction still UNVERIFIED — offline save place + in-game Save for new objects. | Status/list/teleport coded; end-to-end in Customization UNVERIFIED |
| Village loadouts | JSON snapshots of Base Camp placeables under `village_presets/`. Import refuses while game running. House shell replace is best-effort (exParam). | Coded; load-test UNVERIFIED |
| House place | Shell craft obj + `exParamHouse` row. Indoor area clone for second MyHouse still UNVERIFIED (shell-only when forceMap is Map_MyHouse). | Structure verified; new house load-test UNVERIFIED |
| Noun display | `GDSItemText_Noun` keys are `name_ico…` / `name_icf…`; bare item ids also resolve. Editor `_display_name` tries both. | Verified (craft.json ~95% English names) |
| Boyle `chr903700` | Guild admin NPC (maps `Map_500001` / `Map_500011`). Talk: place residents, organize party, change appearance, island name. Not a craft shop. | Verified (NPC talk + `GDSCharaText_Noun`) |
| Cooke `chr903800` | Infrastructure NPC on same guild maps. Talk: expand / build / remodel / relocate / remove; Building Kit + Relocation Kit. Shop config: `shop_infrastructure_kit_sell` (`Shop/Map/Map_500011/…GDSMapShopConfig`). Menu strings under `infrastructure_*` / `dialog_text_infrastructure_*` (Build, Expand, Bridge, Stairs, Farm, Gallery, Islander House, Relocate, Remodel, Remove). | Verified (tables); editor UI for kit buy / plot land still TODO |
| Display cameras | Village Base Camp: 2D map pan + scroll zoom. My House: Three.js OrbitControls (full azimuth, near-full polar, zoom + pan) for placement. | Coded; in-game parity UNVERIFIED |

## 2026-10-13 (Steam Deck / Proton)

Nothing here was run on a Deck or under Wine yet (no Wine on this PC). Checks: Unholy follows `STEAM_DECK.txt`.

| Question | Answer | Status |
|---|---|---|
| Save on the Deck | Steam keeps it outside the game's Proton prefix, same layout as Windows: `~/.local/share/Steam/userdata/<account>/2993780/remote/*gamedata.bin`. The editor (own prefix) reads it as `Z:\home\deck\...`; libraryfolders.vdf holds Linux paths (SD card `/run/media/...`), mapped to `Z:`. | UNVERIFIED: start the editor on the Deck, title screen lists the save |
| Game-running check | The game runs in its own prefix, so tasklist can't see it; the editor also reads `/proc/<pid>/cmdline` and `comm` (15 chars, `NFL1-Win64-Ship`) through `Z:\proc`. | UNVERIFIED: game open, Save to file must refuse |
| Window | pywebview needs WebView2, which rarely works under Proton (it would fall back to the IE engine). Under Wine the exe serves only; `StolenHours-Deck.sh` runs it with `proton run` in `~/.local/share/StolenHours/compat` and opens a Chromium/Edge/Firefox flatpak in kiosk mode, which Game Mode shows. Flatpak browsers see controllers only with `--filesystem=/run/udev:ro` (Valve's cloud-gaming setup); the script adds it. | Launcher dry run passes in WSL (`research/deck_launcher_check.sh`, stub Proton/browser); real Proton + Game Mode UNVERIFIED |
| Controller | Browser Gamepad API, standard mapping (Xbox order; PlayStation ids `054c`/DualSense get PS glyphs). Steam Input's default layout shows as an Xbox 360 pad. Keyboard templates work too (arrows, Enter, Escape). | Verified in the editor with a simulated pad and keys; on a real Deck UNVERIFIED |
