"""Smart Bevel: non-destructive, selection-driven Bevel modifier.

The operator reads the currently selected edges in Edit Mode, bakes that
selection into a fresh vertex group, and adds a Bevel modifier limited to
that vertex group (width/segments are ordinary, forever-re-editable
modifier properties — nothing here is baked into the mesh).

If the object's mesh data is shared with other objects (a linked
duplicate / instance), the mesh is made single-user first so the bevel
does not leak onto sibling instances.
"""

import bmesh
import bpy


class VIBE_OT_smart_bevel(bpy.types.Operator):
    """Add a non-destructive Bevel modifier limited to the selected edges."""

    bl_idname = "mesh.vibe_smart_bevel"
    bl_label = "Smart Bevel (Non-Destructive)"
    bl_options = {"REGISTER", "UNDO"}

    width: bpy.props.FloatProperty(
        name="Width",
        default=0.02,
        min=0.0001,
        precision=4,
        unit="LENGTH",
    )
    segments: bpy.props.IntProperty(name="Segments", default=3, min=1, max=32)

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return (
            context.mode == "EDIT_MESH"
            and obj is not None
            and obj.type == "MESH"
        )

    def execute(self, context):
        obj = context.active_object
        mesh = obj.data

        selected_vert_indices = self._read_selected_verts(mesh)
        if not selected_vert_indices:
            self.report({"ERROR"}, "No edges selected")
            return {"CANCELLED"}

        made_single_user = mesh.users > 1

        bpy.ops.object.mode_set(mode="OBJECT")
        try:
            if made_single_user:
                obj.data = obj.data.copy()
                mesh = obj.data

            vgroup_name = self._create_vertex_group(obj, selected_vert_indices)
            self._add_bevel_modifier(obj, vgroup_name)
        finally:
            bpy.ops.object.mode_set(mode="EDIT")

        message = f"Smart Bevel added on {len(selected_vert_indices)} verts"
        if made_single_user:
            message += " (mesh was linked; made single-user copy)"
        self.report({"INFO"}, message)
        return {"FINISHED"}

    @staticmethod
    def _read_selected_verts(mesh) -> list[int]:
        bm = bmesh.from_edit_mesh(mesh)
        bm.edges.ensure_lookup_table()
        return sorted({v.index for e in bm.edges if e.select for v in e.verts})

    @staticmethod
    def _create_vertex_group(obj, vert_indices: list[int]) -> str:
        base = "SmartBevel"
        existing = {vg.name for vg in obj.vertex_groups}
        name = base
        i = 1
        while name in existing:
            name = f"{base}.{i:03d}"
            i += 1

        vgroup = obj.vertex_groups.new(name=name)
        vgroup.add(vert_indices, 1.0, "REPLACE")
        return vgroup.name

    @staticmethod
    def _add_bevel_modifier(obj, vgroup_name: str) -> None:
        # Local import avoided; caller passes plain values so this stays testable
        mod = obj.modifiers.new(name="Smart Bevel", type="BEVEL")
        mod.limit_method = "VGROUP"
        mod.vertex_group = vgroup_name
        mod.show_in_editmode = True
        mod.show_on_cage = True


_CLASSES = (VIBE_OT_smart_bevel,)


def register():
    for cls in _CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(_CLASSES):
        bpy.utils.unregister_class(cls)
