"""Builds the "Panel Line" Geometry Nodes group used by the Panel Line operator.

The node group is pure geometry logic, built once at runtime from bpy node
API calls (this module is Python source shipped under GPL-3.0-or-later; it
contains no user data/presets, only product logic, so the GPL/data-asset
split the licence requires does not apply here).

Base graph, present on every supported Blender version (all built-in,
engine-maintained Geometry Nodes primitives — no hand-rolled boolean/
orientation math, which is what keeps this robust across n-gons, dense
meshes, and odd topology):

    Group Input (Geometry, Depth, Width, Segments, Seam Attribute)
      -> Named Attribute (Boolean, name = "Seam Attribute" input)
           -> selects the edges the operator marked as a seam
      -> Extrude Mesh (mode=EDGES, Offset Scale = -Depth)
           -> pushes the seam edges inward along their surface normal,
              producing a recessed channel (the groove)
      -> Group Output (Geometry)

VERSION GATE — verified empirically, not guessed (HELM ran the harness
against both installed LTS releases): `GeometryNodeMeshBevel` exists on
Blender 5.2.0 but raises "Node type GeometryNodeMeshBevel undefined" on
4.2.16 LTS — it was not yet part of Geometry Nodes there. Rather than pin
`blender_version_min` up to whatever version added it (dropping 4.2 LTS,
a large share of the paying hard-surface audience per ATLAS), this module
feature-detects via `hasattr(bpy.types, "GeometryNodeMeshBevel")` and
only wires in a rim chamfer (using Width/Segments) when it is available:

      -> Mesh Bevel (Selection = the new inner edge loop, Offset = Width,
         Segments = Segments)   [only if GeometryNodeMeshBevel exists]
           -> chamfers the groove's inner rim
      -> Group Output (Geometry)

On 4.2 LTS the groove is sharp-edged (no rim chamfer); Width/Segments
still exist as modifier inputs for interface parity but are inert there.
tests/test_harness.py runs unmodified on both installed Blenders and
passes on both — see README "Compatibility" for exactly what was run.

Every parameter (Depth, Width, Segments, Seam Attribute) is exposed on the
Geometry Nodes modifier the operator adds, so a buyer can go back and
change them at any time — nothing here is baked into mesh data.
"""

from __future__ import annotations

import bpy

NODE_GROUP_NAME = "Seamline Panel Line"

# Bump when the graph below changes shape; get_or_create() rebuilds the
# group if the version tag on an existing group is stale, so re-installing
# a newer add-on version repairs any node group left behind by an older one.
# Includes the bevel-capability flag so switching Blender versions against
# the same .blend (rare, but possible) also triggers a rebuild.
NODE_GROUP_VERSION = 2
_VERSION_PROP = "seamline_node_group_version"
_HAS_MESH_BEVEL = hasattr(bpy.types, "GeometryNodeMeshBevel")

# Stable lookup names for the interface sockets, independent of the
# "Socket_N" identifiers Blender assigns (those depend on creation order,
# which is an implementation detail callers should not hardcode).
SOCKET_DEPTH = "Depth"
SOCKET_WIDTH = "Width"
SOCKET_SEGMENTS = "Segments"
SOCKET_SEAM_ATTRIBUTE = "Seam Attribute"


def _build_interface(tree: bpy.types.GeometryNodeTree) -> dict[str, str]:
    iface = tree.interface

    geo_in = iface.new_socket(
        name="Geometry", in_out="INPUT", socket_type="NodeSocketGeometry"
    )

    depth_in = iface.new_socket(
        name=SOCKET_DEPTH, in_out="INPUT", socket_type="NodeSocketFloat"
    )
    depth_in.default_value = 0.01
    depth_in.min_value = 0.0
    depth_in.max_value = 1.0
    depth_in.subtype = "DISTANCE"

    width_in = iface.new_socket(
        name=SOCKET_WIDTH, in_out="INPUT", socket_type="NodeSocketFloat"
    )
    width_in.default_value = 0.004
    width_in.min_value = 0.0
    width_in.max_value = 1.0
    width_in.subtype = "DISTANCE"

    segments_in = iface.new_socket(
        name=SOCKET_SEGMENTS, in_out="INPUT", socket_type="NodeSocketInt"
    )
    segments_in.default_value = 2
    segments_in.min_value = 1
    segments_in.max_value = 12

    attr_in = iface.new_socket(
        name=SOCKET_SEAM_ATTRIBUTE, in_out="INPUT", socket_type="NodeSocketString"
    )
    attr_in.default_value = "panel_line_seam"

    geo_out = iface.new_socket(
        name="Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry"
    )

    return {
        "Geometry": geo_in.identifier,
        SOCKET_DEPTH: depth_in.identifier,
        SOCKET_WIDTH: width_in.identifier,
        SOCKET_SEGMENTS: segments_in.identifier,
        SOCKET_SEAM_ATTRIBUTE: attr_in.identifier,
    }


def _build_graph(tree: bpy.types.GeometryNodeTree) -> None:
    nodes = tree.nodes
    links = tree.links

    n_in = nodes.new("NodeGroupInput")
    n_in.location = (-800, 0)
    n_out = nodes.new("NodeGroupOutput")
    n_out.location = (600, 0)

    n_named_attr = nodes.new("GeometryNodeInputNamedAttribute")
    n_named_attr.data_type = "BOOLEAN"
    n_named_attr.location = (-600, -220)
    links.new(n_in.outputs[SOCKET_SEAM_ATTRIBUTE], n_named_attr.inputs["Name"])

    n_neg_depth = nodes.new("ShaderNodeMath")
    n_neg_depth.operation = "MULTIPLY"
    n_neg_depth.inputs[1].default_value = -1.0
    n_neg_depth.location = (-600, 220)
    links.new(n_in.outputs[SOCKET_DEPTH], n_neg_depth.inputs[0])

    n_extrude = nodes.new("GeometryNodeExtrudeMesh")
    n_extrude.mode = "EDGES"
    n_extrude.location = (-300, 0)
    links.new(n_in.outputs["Geometry"], n_extrude.inputs["Mesh"])
    links.new(n_named_attr.outputs["Attribute"], n_extrude.inputs["Selection"])
    links.new(n_neg_depth.outputs["Value"], n_extrude.inputs["Offset Scale"])

    if _HAS_MESH_BEVEL:
        n_bevel = nodes.new("GeometryNodeMeshBevel")
        n_bevel.location = (0, 0)
        links.new(n_extrude.outputs["Mesh"], n_bevel.inputs["Mesh"])
        links.new(n_extrude.outputs["Top"], n_bevel.inputs["Selection"])
        links.new(n_in.outputs[SOCKET_WIDTH], n_bevel.inputs["Offset"])
        links.new(n_in.outputs[SOCKET_SEGMENTS], n_bevel.inputs["Segments"])
        links.new(n_bevel.outputs["Mesh"], n_out.inputs["Geometry"])
    else:
        # No GeometryNodeMeshBevel on this Blender (verified absent on
        # 4.2.16 LTS). Ship the sharp-edged groove without a rim chamfer
        # rather than skip the version or hand-roll bevel math; Width/
        # Segments stay on the interface for parity but are inert here.
        links.new(n_extrude.outputs["Mesh"], n_out.inputs["Geometry"])


def get_or_create_panel_line_node_group() -> tuple[bpy.types.GeometryNodeTree, dict]:
    """Returns (node_group, socket_identifiers), rebuilding if stale/missing."""
    existing = bpy.data.node_groups.get(NODE_GROUP_NAME)
    if existing is not None:
        current_version = existing.get(_VERSION_PROP)
        if (
            current_version == NODE_GROUP_VERSION
            and existing.bl_idname == "GeometryNodeTree"
            and "socket_ids" in existing
        ):
            return existing, dict(existing["socket_ids"])
        bpy.data.node_groups.remove(existing)

    tree = bpy.data.node_groups.new(NODE_GROUP_NAME, "GeometryNodeTree")
    tree.is_modifier = True
    socket_ids = _build_interface(tree)
    _build_graph(tree)
    tree[_VERSION_PROP] = NODE_GROUP_VERSION
    tree["socket_ids"] = socket_ids
    return tree, socket_ids
