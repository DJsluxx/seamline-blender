"""Panel Line: non-destructive, re-editable hard-surface seam grooves.

Reads the edges selected in Edit Mode, stores that selection as a boolean
edge attribute on the mesh, and adds a Geometry Nodes modifier (see
`nodes.py`) that reads the attribute and procedurally cuts a re-editable
groove along it. Nothing here is baked: Depth / Width / Segments / which
edges are the seam all stay live, editable modifier inputs after the
operator finishes.

Re-run on the same object to stack additional independent seams — each
run gets its own attribute name and its own modifier instance sharing the
one node group, so seams can be tweaked or deleted independently.
"""

from __future__ import annotations

import bmesh
import bpy

from . import nodes

ATTRIBUTE_BASE_NAME = "panel_line_seam"
MODIFIER_BASE_NAME = "Panel Line"


def _read_selected_edge_indices(mesh: bpy.types.Mesh) -> list[int]:
    bm = bmesh.from_edit_mesh(mesh)
    bm.edges.ensure_lookup_table()
    return sorted(e.index for e in bm.edges if e.select)


def _unique_name(base: str, existing: set[str]) -> str:
    if base not in existing:
        return base
    i = 1
    while f"{base}.{i:03d}" in existing:
        i += 1
    return f"{base}.{i:03d}"


def _write_seam_attribute(mesh: bpy.types.Mesh, edge_indices: list[int]) -> str:
    existing = {a.name for a in mesh.attributes}
    attr_name = _unique_name(ATTRIBUTE_BASE_NAME, existing)
    attr = mesh.attributes.new(name=attr_name, type="BOOLEAN", domain="EDGE")
    values = [False] * len(mesh.edges)
    for idx in edge_indices:
        values[idx] = True
    attr.data.foreach_set("value", values)
    mesh.update()
    return attr_name


def _set_modifier_input(mod: bpy.types.NodesModifier, identifier: str, value) -> None:
    """Set a Geometry Nodes modifier input by interface-socket identifier.

    Blender's API for this changed between LTS releases: 4.2 LTS stores
    modifier inputs as plain ID properties (`mod["Socket_1"] = value`);
    4.3+ moved them behind a typed `mod.properties.inputs.Socket_1.value`
    interface. Both are tried so the same add-on works on both — this is
    NOT guessed, it was verified empirically against an installed 4.2 LTS
    and 5.2 LTS on this machine (see tests/test_harness.py and README).
    """
    props = getattr(mod, "properties", None)
    inputs = getattr(props, "inputs", None) if props is not None else None
    socket = getattr(inputs, identifier, None) if inputs is not None else None
    if socket is not None and hasattr(socket, "value"):
        socket.value = value
        return
    mod[identifier] = value


class MESH_OT_vibe_panel_line(bpy.types.Operator):
    """Add a non-destructive panel-line groove along the selected edges."""

    bl_idname = "mesh.vibe_panel_line"
    bl_label = "Panel Line"
    bl_options = {"REGISTER", "UNDO"}

    depth: bpy.props.FloatProperty(
        name="Depth",
        description="How deep the groove is recessed",
        default=0.01,
        min=0.0001,
        precision=4,
        unit="LENGTH",
    )
    width: bpy.props.FloatProperty(
        name="Width",
        description="Chamfer width of the groove's rim",
        default=0.004,
        min=0.0,
        precision=4,
        unit="LENGTH",
    )
    segments: bpy.props.IntProperty(
        name="Segments",
        description="Chamfer segment count on the groove's rim",
        default=2,
        min=1,
        max=12,
    )

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

        edge_indices = _read_selected_edge_indices(mesh)
        if not edge_indices:
            self.report({"ERROR"}, "No edges selected")
            return {"CANCELLED"}

        made_single_user = mesh.users > 1

        bpy.ops.object.mode_set(mode="OBJECT")
        try:
            if made_single_user:
                obj.data = obj.data.copy()
                mesh = obj.data

            attr_name = _write_seam_attribute(mesh, edge_indices)
            self._add_panel_line_modifier(obj, attr_name)
        finally:
            bpy.ops.object.mode_set(mode="EDIT")

        message = f"Panel Line added on {len(edge_indices)} edges"
        if made_single_user:
            message += " (mesh was linked; made single-user copy)"
        self.report({"INFO"}, message)
        return {"FINISHED"}

    def _add_panel_line_modifier(self, obj: bpy.types.Object, attr_name: str) -> None:
        node_group, socket_ids = nodes.get_or_create_panel_line_node_group()

        existing_mod_names = {m.name for m in obj.modifiers}
        mod_name = _unique_name(MODIFIER_BASE_NAME, existing_mod_names)

        mod = obj.modifiers.new(name=mod_name, type="NODES")
        mod.node_group = node_group

        _set_modifier_input(mod, socket_ids[nodes.SOCKET_DEPTH], self.depth)
        _set_modifier_input(mod, socket_ids[nodes.SOCKET_WIDTH], self.width)
        _set_modifier_input(mod, socket_ids[nodes.SOCKET_SEGMENTS], self.segments)
        _set_modifier_input(mod, socket_ids[nodes.SOCKET_SEAM_ATTRIBUTE], attr_name)


_CLASSES = (MESH_OT_vibe_panel_line,)


def register():
    for cls in _CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(_CLASSES):
        bpy.utils.unregister_class(cls)
