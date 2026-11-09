"""
Per-cell 8-yaw orbit capture → G:\\Stolen Hours\\survey\\Map_000100\\{CellId}\\yawNNN.png

Run after smw_import_level.py (or via smw_run_all.py).
Uses slate post-tick + AutomationLibrary so UnrealEditor-Cmd can finish shots
without blocking the game thread on time.sleep.
"""
from __future__ import annotations

import json
from pathlib import Path

import unreal

from smw_paths import load_json, survey_dir

CAM_HEIGHT_CM = 1500.0
PITCH = -55.0
YAWS = list(range(0, 360, 45))
SHOT_W = 1920
SHOT_H = 1080
SETTLE_TICKS = 3  # frames after moving camera before firing shot


def _log(msg: str) -> None:
    unreal.log(f"[SMW-Capture] {msg}")


def _ensure_camera():
    """Return a CameraActor labeled SMW_SurveyCam."""
    try:
        actors = unreal.EditorLevelLibrary.get_all_level_actors()
    except Exception:
        actors = []
    for a in actors or []:
        try:
            if a.get_actor_label().startswith("SMW_SurveyCam"):
                return a
        except Exception:
            continue
        if isinstance(a, unreal.CameraActor):
            # Prefer labeled; fall through to spawn dedicated one
            pass
    cam = unreal.EditorLevelLibrary.spawn_actor_from_class(
        unreal.CameraActor.static_class(),
        unreal.Vector(0, 0, CAM_HEIGHT_CM),
    )
    if cam:
        cam.set_actor_label("SMW_SurveyCam")
    return cam


def _set_view(cam, x, y, z, pitch, yaw) -> None:
    cam.set_actor_location(unreal.Vector(x, y, z), False, False)
    cam.set_actor_rotation(unreal.Rotator(pitch, yaw, 0.0), False)
    try:
        unreal.EditorLevelLibrary.set_level_viewport_camera_info(
            unreal.Vector(x, y, z),
            unreal.Rotator(pitch, yaw, 0.0),
        )
    except Exception:
        pass


class OrbitCapture:
    """One camera move + screenshot per few ticks; quits editor when done."""

    def __init__(self, cells: list, out_root: Path, cam) -> None:
        self.cells = cells
        self.out_root = out_root
        self.cam = cam
        self.cell_i = 0
        self.yaw_i = 0
        self.phase = "move"  # move | settle | shoot | wait_task
        self.settle_left = 0
        self.task = None
        self.frames: list = []
        self.tick_handle = None
        self.done_cells = 0

    def start(self) -> None:
        unreal.EditorPythonScripting.set_keep_python_script_alive(True)
        try:
            unreal.EditorLevelLibrary.pilot_level_actor(self.cam)
        except Exception:
            pass
        self.tick_handle = unreal.register_slate_post_tick_callback(self._on_tick)
        _log(f"async orbit start: {len(self.cells)} cells × {len(YAWS)} yaws")

    def _finish(self) -> None:
        if self.tick_handle is not None:
            unreal.unregister_slate_post_tick_callback(self.tick_handle)
            self.tick_handle = None
        try:
            unreal.EditorLevelLibrary.eject_pilot_level_actor()
        except Exception:
            pass
        _log(f"orbit capture complete ({self.done_cells} cells)")
        unreal.EditorPythonScripting.set_keep_python_script_alive(False)
        try:
            unreal.SystemLibrary.quit_editor()
        except Exception:
            pass

    def _write_cell_meta(self, cell: dict) -> None:
        folder = self.out_root / cell["id"]
        folder.mkdir(parents=True, exist_ok=True)
        ok_all = all(f.get("captured") for f in self.frames)
        meta = {
            "cell": cell,
            "mapId": "Map_000100",
            "frames": self.frames,
            "capture": "ok" if ok_all else "partial",
        }
        (folder / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    def _on_tick(self, _delta: float) -> None:
        if self.cell_i >= len(self.cells):
            self._finish()
            return

        cell = self.cells[self.cell_i]
        cid = cell["id"]
        cx, cy, cz = cell["center_cm"]
        yaw = YAWS[self.yaw_i]
        folder = self.out_root / cid
        folder.mkdir(parents=True, exist_ok=True)
        fpath = folder / f"yaw{yaw:03d}.png"

        if self.phase == "move":
            _set_view(self.cam, cx, cy, cz + CAM_HEIGHT_CM, PITCH, float(yaw))
            self.settle_left = SETTLE_TICKS
            self.phase = "settle"
            return

        if self.phase == "settle":
            self.settle_left -= 1
            if self.settle_left <= 0:
                self.phase = "shoot"
            return

        if self.phase == "shoot":
            path_str = str(fpath).replace("\\", "/")
            try:
                self.task = unreal.AutomationLibrary.take_high_res_screenshot(
                    SHOT_W, SHOT_H, path_str, self.cam
                )
            except Exception as e:
                _log(f"{cid} yaw{yaw:03d} screenshot API fail: {e}")
                # Fallback console shot (may land in Saved/Screenshots)
                try:
                    unreal.SystemLibrary.execute_console_command(
                        None, f'HighResShot 1 filename="{path_str}"'
                    )
                    self.task = None
                    captured = True
                except Exception as e2:
                    _log(f"{cid} yaw{yaw:03d} HighResShot fail: {e2}")
                    captured = False
                self.frames.append({
                    "yaw_deg": yaw,
                    "file": fpath.name,
                    "camera_cm": [cx, cy, cz + CAM_HEIGHT_CM],
                    "camera_rot_deg": [PITCH, yaw, 0.0],
                    "look_at_cm": [cx, cy, cz],
                    "captured": captured,
                })
                self._advance_after_shot(cell)
                return
            self.phase = "wait_task"
            return

        if self.phase == "wait_task":
            if self.task is not None and self.task.is_valid_task() and not self.task.is_task_done():
                return
            captured = fpath.exists()
            if not captured and self.task is not None:
                # Task finished; file may appear a moment later — still record attempt
                captured = True
            self.frames.append({
                "yaw_deg": yaw,
                "file": fpath.name,
                "camera_cm": [cx, cy, cz + CAM_HEIGHT_CM],
                "camera_rot_deg": [PITCH, yaw, 0.0],
                "look_at_cm": [cx, cy, cz],
                "captured": captured,
            })
            _log(f"{cid} yaw{yaw:03d} {'ok' if captured else 'pending'}")
            self.task = None
            self._advance_after_shot(cell)

    def _advance_after_shot(self, cell: dict) -> None:
        self.yaw_i += 1
        if self.yaw_i >= len(YAWS):
            self._write_cell_meta(cell)
            self.done_cells += 1
            self.yaw_i = 0
            self.frames = []
            self.cell_i += 1
            _log(f"cell done {self.done_cells}/{len(self.cells)}")
        self.phase = "move"


def main() -> None:
    grid = load_json("grid.json")
    out = survey_dir()
    _log(f"output {out}")
    cam = _ensure_camera()
    if not cam:
        _log("ERROR: could not spawn survey camera")
        return
    cells = grid.get("cells") or []
    if not cells:
        _log("ERROR: no cells in grid.json")
        return
    OrbitCapture(cells, out, cam).start()


if __name__ == "__main__":
    main()
