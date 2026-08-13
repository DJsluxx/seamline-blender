"""Add-on entry point.

Seamline adds one operator: a non-destructive, re-editable panel-line
groove for hard-surface meshes, built entirely on a Geometry Nodes
modifier (see `nodes.py` for the node graph and why it was chosen).

NOTE: as of Blender 4.2+/5.x, add-on metadata (name/version/min-blender-
version/etc.) lives in blender_manifest.toml, not a bl_info dict — the
legacy addon_utils.paths() scan does not look at the user scripts/addons
directory anymore. This file intentionally has no bl_info; the manifest
is the single source of truth for metadata.
"""

from . import keymaps, operators, ui

_MODULES = (operators, ui, keymaps)


def register():
    for module in _MODULES:
        module.register()


def unregister():
    for module in reversed(_MODULES):
        module.unregister()
