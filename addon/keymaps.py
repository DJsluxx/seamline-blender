"""Keymap entry for the Panel Line operator.

Bound to Ctrl+Shift+Alt+P in the Mesh (Edit Mode) keymap — deliberately a
4-modifier chord to avoid colliding with any of Blender's default Edit
Mesh bindings (P alone is Separate, Shift+P/Alt+P/Ctrl+P are unbound by
default in that keymap as of 4.2/5.2).
"""

import bpy

_addon_keymaps: list[tuple] = []


def register() -> None:
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    if kc is None:
        # Headless / background Blender (e.g. the test harness) has no
        # addon keyconfig; keymap registration is a no-op there, which is
        # expected and not an error.
        return

    km = kc.keymaps.new(name="Mesh", space_type="EMPTY")
    kmi = km.keymap_items.new(
        "mesh.vibe_panel_line",
        type="P",
        value="PRESS",
        ctrl=True,
        shift=True,
        alt=True,
    )
    _addon_keymaps.append((km, kmi))


def unregister() -> None:
    for km, kmi in _addon_keymaps:
        km.keymap_items.remove(kmi)
    _addon_keymaps.clear()
