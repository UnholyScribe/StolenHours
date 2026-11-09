"""
Import Base Camp glTFs at native UE poses + draw named 10 m craft-pad grid.

Run in UE 5.4 editor: File → Execute Python Script → smw_import_level.py
Requires: Editor Scripting Utilities, GLTFImporter (or Datasmith).

If glTF import APIs are unavailable, spawns labeled grid + empty targets at craft poses
so orbit capture still has cell centers.
"""
from __future__ import annotations

import unreal

from smw_paths import load_json, survey_dir

TILE_CM = 1000.0  # 10 m


def _log(msg: str) -> None:
    unreal.log(f"[SMW] {msg}")


def spawn_grid_labels(grid: dict) -> None:
    """Debug text + floor planes for each survey cell."""
    for cell in grid.get("cells") or []:
        cx, cy, cz = cell["center_cm"]
        loc = unreal.Vector(cx, cy, cz + 20.0)
        # Target point actor as cell marker
        actor = unreal.EditorLevelLibrary.spawn_actor_from_class(
            unreal.TargetPoint.static_class(), loc
        )
        if actor:
            actor.set_actor_label(f"SMW_Cell_{cell['id']}")
        # Thin plane for pad tile (optional visual)
        try:
            plane = unreal.EditorLevelLibrary.spawn_actor_from_class(
                unreal.StaticMeshActor.static_class(),
                unreal.Vector(cx, cy, cz + 1.0),
            )
            if plane:
                plane.set_actor_label(f"SMW_Pad_{cell['id']}")
                plane.set_actor_scale3d(unreal.Vector(TILE_CM / 100.0, TILE_CM / 100.0, 0.02))
                sm = plane.static_mesh_component
                # Engine plane mesh if available
                mesh = unreal.EditorAssetLibrary.load_asset("/Engine/BasicShapes/Plane")
                if sm and mesh:
                    sm.set_static_mesh(mesh)
        except Exception as e:
            _log(f"pad spawn skip {cell['id']}: {e}")


def spawn_craft_targets(manifest: dict) -> int:
    """Spawn TargetPoints at craft object UE locations (mesh import best-effort)."""
    n = 0
    for pl in manifest.get("placements") or []:
        if pl.get("kind") != "craft":
            continue
        loc_cm = pl.get("location_cm") or [0, 0, 0]
        rot = pl.get("rotation_deg") or [0, 0, 0]
        loc = unreal.Vector(float(loc_cm[0]), float(loc_cm[1]), float(loc_cm[2]))
        # UE rotator: Pitch, Yaw, Roll — save is [pitch, yaw, roll]-like
        rotator = unreal.Rotator(float(rot[0]), float(rot[1]), float(rot[2]))
        actor = unreal.EditorLevelLibrary.spawn_actor_from_class(
            unreal.TargetPoint.static_class(), loc, rotator
        )
        if not actor:
            continue
        label = pl.get("name") or pl.get("id") or "craft"
        handle = pl.get("handle")
        actor.set_actor_label(f"SMW_Craft_{label}_{handle}")
        n += 1
        # Best-effort glTF: Interchange / GLTF importer varies by engine build.
        glb = pl.get("glb")
        if glb:
            try:
                _try_import_glb(glb, loc, rotator, f"SMW_Mesh_{label}_{handle}")
            except Exception as e:
                _log(f"glb import skip {label}: {e}")
    return n


def _try_import_glb(glb_path: str, loc, rotator, label: str) -> None:
    """Attempt automated glTF import; safe no-op if API missing."""
    # UE 5.4 Interchange
    if not hasattr(unreal, "AssetImportTask"):
        return
    task = unreal.AssetImportTask()
    task.filename = glb_path
    task.destination_path = "/Game/SMW_Imported"
    task.replace_existing = True
    task.automated = True
    task.save = True
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    # Spawning imported mesh into level is project-specific; TargetPoint marks pose.


def main() -> None:
    grid = load_json("grid.json")
    manifest = load_json("import_manifest.json")
    _log(f"survey dir {survey_dir()}")
    _log(f"grid {grid['cols']}x{grid['rows']} tiles, {len(grid['cells'])} cells")
    spawn_grid_labels(grid)
    n = spawn_craft_targets(manifest)
    _log(f"spawned {n} craft targets + grid labels")
    _log("Save the level as /Game/Maps/BaseCampSurvey when ready.")


if __name__ == "__main__":
    main()
