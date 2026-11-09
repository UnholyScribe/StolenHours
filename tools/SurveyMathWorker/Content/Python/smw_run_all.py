"""Import grid + craft targets, then run orbit capture. Invoked via -ExecutePythonScript."""
from __future__ import annotations

import unreal

unreal.log("[SMW] run_all: import")
import smw_import_level
smw_import_level.main()

unreal.log("[SMW] run_all: capture")
import smw_capture_orbit
smw_capture_orbit.main()

unreal.log("[SMW] run_all: capture scheduled (async ticks)")
