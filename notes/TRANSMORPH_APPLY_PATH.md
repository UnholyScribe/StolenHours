# Transmorph apply path (Loom → Tock)

Bag UI HOLD until this path is agreed. Loom owns RE; Tock owns editor/Live impl.

## Goal

Keep bag `ItemId` / stats / skills. Swap **look** (mesh + mats + icon optionally).

## Why not save-only

- `InventoryInfoEquip` has **no** skin field (**DISPROVEN**).
- Reload remaps from `ItemId → modelID` (**CONFIRMED** pipeline).
- Therefore persist needs **sidecar and/or live remap**.

## Recommended MVP (two layers)

### A — Live remap (preview / session)

1. Resolve look source → `modelID` / `EquipModelList` path / icon (`tex_icon_*`).
2. `SET` on `BP_CtrlCharacterBase_C.ViewEquipModelInfoSet[EquipSetCurrentIndex]`:
   - weapon → `weapon` slot
   - shield → `shield` slot (`L_hand` / `sld`)
   - tools → same weapon-hand path (`mdl_wpn1002*`)
   - armor Type 60–67 → matching wear slots (labels POSSIBLE)
3. Live **GET** weapon slot **CONFIRMED**; **SET** weapon transmorph **UNVERIFIED** (needs one live proof).
4. Session-only: quit restores vanilla from ItemId.

### B — Sidecar persist (StolenHours)

JSON next to save (or under `%LOCALAPPDATA%/StolenHours/`):

```json
{
  "version": 1,
  "skins": {
    "<itemHandle or bagSlotKey>": {
      "hostItemId": "iwp03000040",
      "lookItemId": "iwp03000230",
      "lookModelId": "mdl_wpn000215_00",
      "lookIcon": "iwp03000230",
      "slot": "weapon"
    }
  }
}
```

On load / equip: mod reads sidecar → applies A. Editor writes sidecar; does **not** mutate bag ItemId.

### C — Custom authored skins (later)

- Retexture / replace donor `mdl_wpn*` / `mdl_sld*` / `mdl_wea*` (Dig C).
- Sidecar points at pack id under Loom `sandbox/weapon_skin/extract/` or user pack dir.
- Full custom mesh still needs mod remesh; no pak by default.

## Editor UI (Tock)

1. Bag row → “Transmorph…”
2. Pick look: another owned item **or** Loom pack.
3. Preview: glb+tex from pack / EquipModel path (craft3d-style).
4. Apply → write sidecar + if Live connected, fire SET.
5. Clear → delete sidecar entry + refresh from ItemId.

## Out of scope for MVP

- Changing grade/skills/stats
- Shipping cooked pak overrides
- Anti-cheat / multiplayer (offline personal editor only)

## Evidence dumps

- `knowledge/WEAPON_SKIN_SYSTEM.md`
- `sandbox/weapon_skin/transmorph_catalog.json`
- `sandbox/weapon_skin/icons_tools_shields_chain.json`
- `sandbox/weapon_skin/armor_wear_chain.json`
- Extract pairs: claymore/buster, sld000100/sld000b00, wpn100201/100202

## Ask for Tock

Confirm A+B as apply path → Loom helps with Live SET smoke when Unholy boots; Tock can unpark Bag UI.
