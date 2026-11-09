# Lessons from PetDesigner (NMS) for Stolen Hours (FLi)

Source: `G:\Archives\petdesigner-book` (2026-11-09), friend’s private repo
`whiteshark-1975/petdesigner`. Different game — steal **methods**, not NMS offsets.

## What they built (one line)

Game files → per-type JSON packs → offline ports of the game’s own rolls → one
**generic** Three.js viewer with **no creature special-cases**. Preview ≠ game →
fix the pipeline with screenshots, don’t hack one pet.

## Adopted in Stolen Hours

| Lesson | What we did |
|--------|-------------|
| Packs + no stale cache | Local HTTP: only heavy `game/` binaries cache; JS/CSS/JSON are `no-store`. Client fetches for manifests use `cache: "no-store"`. |
| Pipeline over special-cases | Same rule for Look / Village: fix export + shared viewer, no “one house” hacks. |
| Bone scale is engine-specific | **Do not** copy NMS’s non-inheriting scale override. FLi Look already puts body size into **bind inverses** (component-space), which matches the game. Documented in `look3d.js`. |
| VertexLayout / clip names are law | Keep using named entity clips / real mesh layout; never “first idle alphabetically.” |
| Serial handoffs | Prefer `handoff-*.md` + fresh agent over parallel edits on one viewer. |
| Honesty log | Proven vs approximate stays in `docs/FINDINGS.md` / PROGRESS. |

## Do not port

- NMS MBIN / HGPAK / fauna RNG walks / `pose-roll` channel math
- Blind `updateMatrixWorld` scale override (wrong for FLi Look)
- Per-seed tables (we don’t have NMS-style creature seeds)

## If Village/Look still diverge from Customization

Use their handoff shape:

1. In-game screenshot + editor screenshot  
2. Hard rule: no special-case in shared `village3d.js` / `look3d.js`  
3. Fix extract/pack/viewer so every asset of that class benefits  
4. Prove on one map/house, then a second  

## Portable EXE (brother test)

See README “Portable Windows exe” and `G:\Stolen Hours`. Double-click
`StolenHours.exe`. No Unholy paths. Steam/save discovery at runtime. WebView2
prompt if missing (browser fallback). Live Map = optional one-click setup with
game closed.
