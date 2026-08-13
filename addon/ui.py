"""Sidebar (N-panel) UI for Seamline."""

import bpy


class VIBE_PT_main_panel(bpy.types.Panel):
    bl_label = "Seamline"
    bl_idname = "VIBE_PT_main_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Seamline"

    @classmethod
    def poll(cls, context):
        return context.mode in {"EDIT_MESH", "OBJECT"}

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)

        if context.mode != "EDIT_MESH":
            col.label(text="Enter Edit Mode and select", icon="INFO")
            col.label(text="edges to add a panel line.")
            return

        col.operator("mesh.vibe_panel_line", icon="MOD_BEVEL")
        col.separator()
        col.label(text="Keymap: Ctrl Shift Alt P")
        col.separator()
        box = layout.box()
        box.label(text="Depth / Width / Segments and", icon="MODIFIER")
        box.label(text="which edges are the seam stay")
        box.label(text="editable on the 'Panel Line'")
        box.label(text="modifier afterward.")


_CLASSES = (VIBE_PT_main_panel,)


def register():
    for cls in _CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(_CLASSES):
        bpy.utils.unregister_class(cls)
