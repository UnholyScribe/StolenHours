# SurveyMathWorker (parked)

Blank UE project + Editor Python for Base Camp **math** and optional orbit capture.

**Status (2026-10-17):** Orbit PNGs abandoned — empty `Template_Default` with no FLi craft/map3d.
Truth tables come from Python only. Do not run capture until real glTFs are imported into the level.

Fantasy Life i shipping is UE **5.4.4**. A separate install under `E:\Unreal Engine` (e.g. 5.8) cannot load the game’s cooked content; it only helps if we import extracted meshes ourselves.

## Useful path (no UE)

```powershell
cd 'E:\Fantasy Life i - Stolen Hours\editor'
py -3.12 -m stolenhours.survey_math export
```

Output: `G:\Stolen Hours\survey\Map_000100\` → `grid.json`, `objects.json`, `axes.md`, `import_manifest.json`, per-cell `meta.json`.

Village consumes those via `survey_truth` (cell rings + door-forward arrows).

## Optional UE (debug only)

1. `Scripts\find_ue54.ps1` → `ue_path.txt`
2. Import craft/map3d glTFs at native UE poses (`smw_import_level.py` — mesh import still best-effort)
3. Only then: `Scripts\run_orbit_capture.ps1` (uses `E:\SMW` junction to avoid path/`\t` argv bugs)

## Grid (craft pad)

- Origin UE cm: `(-3150, -3950, -150)`
- Size: 160×128 × 50 cm → **80 m × 64 m**
- Tiles: **10 m** → `A`…`H` × `1`…`7` (`A1` = SW corner)
