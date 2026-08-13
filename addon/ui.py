"""Sidebar panel for the Vibe Toolkit scaffold."""

import bpy


class VIBE_PT_main_panel(bpy.types.Panel):
    bl_label = "Vibe Toolkit"
    bl_idname = "VIBE_PT_main_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Vibe Toolkit"

    def draw(self, context):
        layout = self.layout
        layout.operator("vibe.grid_array")


_CLASSES = (VIBE_PT_main_panel,)


def register():
    for cls in _CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(_CLASSES):
        bpy.utils.unregister_class(cls)
