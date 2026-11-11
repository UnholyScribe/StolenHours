# Blueprint for Loom — weapon / gear skins (custom + swap)

From: **Tock** (Unholy OK)  
Goal: same bag item (stats / ItemId / grade / skills) can **look** like another weapon — e.g. Claymore keeps Claymore identity but uses Berserker sword mesh/textures — and later **custom** skins authored outside the game.

Confidence: use CONFIRMED / STRONGLY SUPPORTED / UNVERIFIED as usual. Tables + meshes are law.

---

## 1. What Unholy wants in the editor (apply path)

1. **Bag / equipped gear:** pick a weapon (then tools / shields / armor).
2. **Skin source:** choose another game item’s appearance **or** a custom pack.
3. **Apply:** only appearance changes. `ItemId`, grade, quality, bonus, skills stay.
4. Later: **import custom skin** (user mesh/textures) → convert to game format → assign as that item’s look.

Example target: Claymore (`ItemId` unchanged) + Berserker sword visual.

Tock will wire UI once Loom banks a real override path. Do **not** invent a fake skin field.

### Loom Dig status (2026-11-10 — tick 24)

- **Dig A CONFIRMED/DISPROVEN:** no vanilla save skin field. Chain ItemId→modelID→EquipModelList→mdl_wpn*. Persist needs mod hook / sidecar.
- **Dig B pair:** Iron Claymore `iwp03000040` / `mdl_wpn000204_00` ↔ Dark Dragon Buster `iwp03000230` / `mdl_wpn000215_00` (Type 12). Both `basemat_chara_wepon_00`.
- **Dig C:** MVP = retexture donor wpn + mod-hook persist. Live GET ViewEquipModelInfoSet CONFIRMED; SET weapon-slot NAME remap UNVERIFIED.
- Dumps: `agents/Loom/sandbox/weapon_skin/` + `knowledge/WEAPON_SKIN_SYSTEM.md`. **No Bag skin UI until apply path agreed.**


---

## 2. Dig A — does the game already support appearance ≠ ItemId?

### Known (Stolen Hours FINDINGS — verified)

- Held mesh: item `modelID` (`mdl_wpn*` / `mdl_sld*`) → `GDSItemEquipModelData` → mesh paths.
- Attach: `root > R_hand_item_tag > wpn` (shield `L_hand_item_tag > sld`); scale neutral.
- Live equipped look: `BP_CtrlCharacterBase_C.ViewEquipModelInfoSet[EquipSetCurrentIndex]` (weapon / shield / wear slots, model names).
- Bag save: `InventoryInfoEquip` has `ItemId`, `itemTitle`, `Quality`, `addEquipStatus`, `grantSkillId` — **no known skin field today**.

### Loom: confirm or DISPROVE

| Check | Why |
|---|---|
| Any save field that overrides `modelID` / equip model without changing `ItemId` | Persist transmog |
| `ViewEquipModelInfo*` / ability equip sets — writable? save-backed? | Live vs bag |
| Outfit / MySet / life gear sets — appearance-only slots? | Alternate store |
| Cooked path: ItemId → WeaponData.modelID → EquipModelList → USkeletalMesh / materials / textures | Exact chain for weapons + tools + shields |
| Icon 2D vs world 3D — separate tables? (`GDSMenuIcon*` vs mesh) | Bag icon vs hand mesh |

Bank: field names, offsets/types if save, live GET/SET verbs if any. Label confidence.

**If no override exists:** say so clearly. Then dig B/C still matter for *custom pak / editor preview*; save transmog may need a StolenHours mod hook later (flag that).

---

## 3. Dig B — full extract of one weapon’s “skin package”

For a reference pair Unholy cares about (Claymore + Berserker sword — resolve real `ItemId`s / `modelID`s from tables):

Pull **everything** the game uses for that look:

1. **3D:** skeletal/static mesh(es), skeleton/socket if any, LODs, collision if separate.
2. **Materials:** MI / parent mat, texture slots (diffuse/ORM/normal/emissive/… whatever they use).
3. **Textures:** every referenced 2D asset — **size (px), format, sRGB vs linear, compression, mip policy**.
4. **2D UI:** bag/equipment icon texture(s) + atlas crop if any.
5. **Meta:** bounds, pivot, hand socket, scale (expect 1.0 — confirm), grade variants if meshes differ by title.

Output: dump under `agents/Loom/sandbox/weapon_skin_*/` + short knowledge note (`WEAPON_SKIN_SYSTEM.md`). Prefer glTF/glb + PNG/TGA extracts when possible (same spirit as craft mesh packs).

---

## 4. Dig C — authoring / conversion pipeline (normal model → FLi)

Unholy wants to build **new** skins (not only swap existing). Document:

1. **Target formats** UE 5.4.4 / NFL1 expects for held weapons (mesh type, bone names, material param names).
2. **Texture budget:** max sizes observed, power-of-two rules, channel packing.
3. **Conversion steps** from a “normal” DCC model (Blender FBX/glTF) → game-ready assets (what must match sockets `wpn` / `R_hand_item_tag`, up-axis, unit scale cm).
4. What can be done **offline with current extract tools** vs what needs cooked uasset/pak replace vs live-only remesh.
5. Minimum viable custom skin: replace textures only vs replace mesh+textures.

No need to ship a full Blender exporter yet — bank the **spec** so Tock/Griswold can build the pipeline later.

---

## 5. Out of scope / don’t block on

- Changing base damage tables for “skinned” items (Bag grade editor already exists; separate).
- Calling MapCraft / craft ExeCmds.
- Online-safe transmog (custom = offline / warn like beyond-normal gear).

---

## 6. Deliverables checklist

- [ ] `WEAPON_SKIN_SYSTEM.md` — chain + override existence (or DISPROVEN)
- [ ] Sandbox extract for Claymore + Berserker (or closest named pair) — mesh + mats + textures + icons + pixel sizes
- [ ] Authoring notes — sizes, formats, sockets, conversion steps
- [ ] Railroad reply to Tock: CONFIRMED path for editor apply, or “needs mod hook”, plus where dumps live

Tock will not invent Bag UI until that reply lands.
