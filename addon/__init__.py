"""Add-on entry point.

SCAFFOLD NOTICE: This is a placeholder product skeleton built before the
ATLAS product brief landed. The operator and panel below are a minimal,
provably-working demo (grid array generator) that exercises the exact
registration/packaging/test path the real product will use. Swap
`operators.py` / `ui.py` for the real feature set once the brief arrives;
do not change the register/unregister contract without re-running
tests/test_harness.py.

NOTE: as of Blender 5.2 LTS, add-on metadata (name/version/min-blender-
version/etc.) lives in blender_manifest.toml, not a bl_info dict — the
legacy addon_utils.paths() scan does not even look at the user scripts/
addons directory anymore. This file intentionally has no bl_info; the
manifest is the single source of truth for metadata.
"""

from . import operators
from . import ui

_MODULES = (operators, ui)


def register():
    for module in _MODULES:
        module.register()


def unregister():
    for module in reversed(_MODULES):
        module.unregister()
