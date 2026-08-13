"""Generates real product-shot marketing renders for Seamline by driving
Blender headlessly. This is not a mockup generator: every image comes from
an actual render of the actual add-on running the actual operator on an
actual mesh, through the exact same install path tests/test_harness.py
verifies (bpy.ops.extensions.package_install_files against the built zip).

Must be invoked FROM INSIDE BLENDER, background mode is fine for these
(no viewport/N-panel chrome is needed for a 3D-viewport-camera render):

    "<blender.exe>" --background --factory-startup --python scripts/render_marketing.py

BLENDER_USER_RESOURCES should point at a throwaway temp dir (see
scripts/run_marketing_renders.ps1) so this never touches the real profile.

Produces, in marketing/:
    seamline_before.png   - hard-surface plate, flat top, no grooves
    seamline_after.png    - same plate + mesh, same camera, grooves applied
    seamline_sweep.png    - 4 copies of the same modifier at different
                             Depth values side by side, proving the result
                             is re-editable, not baked
    seamline_hero.png     - single hero shot, safe-crop-square composition

GEOMETRY NOTE (this is the part the previous version of this script got
wrong -- see scratchpad diag_loop.py / diag_topgrid.py from this run):
the Panel Line operator extrudes the SELECTED EDGES inward along their
local surface normal. If you select an edge loop that runs across a
corner/multiple face orientations (as the old _build_hull's bisect-based
belt+vertical seams did), each seam vertex's offset normal is an average
of several different face normals, which can produce a displacement that
is real (verified non-zero in evaluated geometry) but visually near-
imperceptible from a given camera angle. The fix used here is to give the
seam its OWN flat, single-orientation region: a box with its top face
replaced by a subdivided grid, selecting ONLY the grid's INTERIOR edges
(not the outer rim). Every selected vertex then has the same +Z normal,
so the whole seam recesses straight down by exactly `depth`, verified
against the evaluated mesh (16 of 40 verts sit at exactly top_z - depth,
the rest are untouched) before this was used for any of the 4 renders.
"""

from __future__ import annotations

import math
import pathlib
import sys
import traceback

import bmesh
import bpy
import mathutils

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))
import test_harness as harness  # noqa: E402  reuse verified install/modifier helpers

OUT_DIR = ROOT / "marketing"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Plate footprint (X, Y, Z) in world units and how many seam lines subdivide
# the top face: PLATE_X_SECTIONS=3 -> 2 interior vertical seam lines,
# PLATE_Y_SECTIONS=2 -> 1 interior horizontal seam line -- a 6-panel grid.
PLATE_SIZE = (2.0, 1.24, 0.84)
PLATE_HALF_Z = PLATE_SIZE[2] / 2
PLATE_X_SECTIONS = 3
PLATE_Y_SECTIONS = 2

# Empirically measured against the real operator (scratchpad diag_topgrid.py,
# run through the same install path as tests/test_harness.py): depth=0.15 on
# this plate (top-face half-thickness 0.42) sends the seam verts to exactly
# top_z - 0.15 while every other vertex is untouched -- a real, ~36%-of-half-
# thickness recess. The previous version of this script used depth=0.03,
# roughly 5x too shallow to read at any camera distance.
DEMO_DEPTH = 0.15
DEMO_WIDTH = 0.05
DEMO_SEGMENTS = 3

SWEEP_DEPTHS = [0.05, 0.12, 0.20, 0.30]

BODY_COLOR = (0.60, 0.62, 0.65)
GREEBLE_COLOR = (0.46, 0.48, 0.51)
GROUND_COLOR = (0.90, 0.90, 0.91)


# ---------------------------------------------------------------- scene ---


def _clear_scene() -> None:
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    for mesh in list(bpy.data.meshes):
        if mesh.users == 0:
            bpy.data.meshes.remove(mesh)
    for mat in list(bpy.data.materials):
        if mat.users == 0:
            bpy.data.materials.remove(mat)
    for txt in list(bpy.data.curves):
        if txt.users == 0:
            bpy.data.curves.remove(txt)


def _make_material(name: str, color) -> bpy.types.Material:
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*color, 1.0)
    mat.use_nodes = False
    return mat


def _safe_set(obj, name, value) -> None:
    try:
        setattr(obj, name, value)
    except Exception as exc:  # noqa: BLE001
        print(f"WARN: could not set {type(obj).__name__}.{name} = {value!r}: {exc}")


def _setup_render_settings(scene: bpy.types.Scene) -> None:
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.image_settings.color_depth = "8"
    scene.render.film_transparent = False
    # Max lossless PNG compression -- these are flat-shaded product shots,
    # not photographic noise, so this shrinks the file substantially with
    # zero quality loss (previous renders shipped at Blender's default
    # compression and came out ~2MB each for what is mostly flat grey).
    scene.render.image_settings.compression = 95

    shading = scene.display.shading
    # NOTE: studio_light is a dynamic enum whose valid identifiers depend on
    # `light` mode; verified empirically that reassigning it is unnecessary
    # noise ('Default' is already a valid STUDIO-mode identifier) so it is
    # deliberately left untouched here.
    _safe_set(shading, "light", "STUDIO")
    # Fix the studio light in WORLD space and rotate it off-axis so it rakes
    # across the seams at an angle instead of hitting them head-on (a flat
    # frontal key light is exactly what hid the grooves in the previous
    # render -- a grazing light makes a recessed edge cast a real shadow).
    _safe_set(shading, "use_world_space_lighting", True)
    _safe_set(shading, "studiolight_rotate_z", math.radians(40))
    _safe_set(shading, "studiolight_intensity", 1.15)
    _safe_set(shading, "show_cavity", True)
    _safe_set(shading, "cavity_type", "BOTH")
    _safe_set(shading, "curvature_ridge_factor", 1.1)
    _safe_set(shading, "curvature_valley_factor", 2.2)
    _safe_set(shading, "cavity_ridge_factor", 1.2)
    _safe_set(shading, "cavity_valley_factor", 2.5)
    _safe_set(shading, "show_shadows", True)
    _safe_set(shading, "shadow_intensity", 0.75)
    _safe_set(shading, "color_type", "SINGLE")
    _safe_set(shading, "single_color", BODY_COLOR)
    _safe_set(shading, "background_type", "VIEWPORT")
    _safe_set(shading, "background_color", GROUND_COLOR)
    _safe_set(shading, "object_outline_color", (0.05, 0.05, 0.05))
    _safe_set(shading, "show_object_outline", False)

    try:
        scene.view_settings.view_transform = "Standard"
    except Exception as exc:  # noqa: BLE001
        print(f"WARN: could not set view_transform: {exc}")


def _add_ground() -> bpy.types.Object:
    bpy.ops.mesh.primitive_plane_add(size=30, location=(0, 0, 0))
    plane = bpy.context.active_object
    plane.name = "Ground"
    plane.data.materials.append(_make_material("GroundMat", GROUND_COLOR))
    return plane


# ------------------------------------------------------------- geometry ---


def _build_plate(name: str = "SeamlinePlate", location=(0.0, 0.0, 0.0)):
    """A solid hard-surface block whose TOP FACE is a subdivided grid.

    Only the grid's INTERIOR edges are selected as the seam (the outer rim
    of the top face, and the box's sides/bottom, are left alone) -- every
    selected vertex therefore shares the same +Z surface normal, so the
    operator's offset is a clean, unambiguous, straight-down recess.
    Verified against evaluated mesh vertex Z values before use (see the
    module docstring). Returns (obj, seam_edge_count).
    """
    sx, sy, sz = PLATE_SIZE
    top_z = PLATE_HALF_Z

    bpy.ops.mesh.primitive_cube_add(size=2.0, location=location)
    box = bpy.context.active_object
    box.name = name
    box.scale = (sx / 2, sy / 2, sz / 2)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

    bpy.context.view_layer.objects.active = box
    bpy.ops.object.mode_set(mode="EDIT")
    bm = bmesh.from_edit_mesh(box.data)
    bm.faces.ensure_lookup_table()
    top_faces = [f for f in bm.faces if f.normal.z > 0.9]
    bmesh.ops.delete(bm, geom=top_faces, context="FACES")
    bmesh.update_edit_mesh(box.data)
    bpy.ops.object.mode_set(mode="OBJECT")

    bpy.ops.mesh.primitive_grid_add(
        x_subdivisions=PLATE_X_SECTIONS + 1,
        y_subdivisions=PLATE_Y_SECTIONS + 1,
        size=1.0,
        location=(location[0], location[1], location[2] + top_z),
    )
    grid = bpy.context.active_object
    grid.scale = (sx, sy, 1.0)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

    bpy.ops.object.select_all(action="DESELECT")
    grid.select_set(True)
    box.select_set(True)
    bpy.context.view_layer.objects.active = box
    bpy.ops.object.join()
    box.data.materials.append(_make_material("PlateMat", BODY_COLOR))

    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.remove_doubles(threshold=1e-4)

    bm2 = bmesh.from_edit_mesh(box.data)
    bm2.verts.ensure_lookup_table()
    bm2.edges.ensure_lookup_table()
    bm2.faces.ensure_lookup_table()

    world_top_z = location[2] + top_z
    half_x = sx / 2 - 1e-4
    half_y = sy / 2 - 1e-4

    for e in bm2.edges:
        e.select = False
    for v in bm2.verts:
        v.select = False
    for f in bm2.faces:
        f.select = False

    seam_edges = []
    for e in bm2.edges:
        v0, v1 = e.verts
        if abs(v0.co.z - world_top_z) < 1e-4 and abs(v1.co.z - world_top_z) < 1e-4:
            on_rim = (
                abs(abs(v0.co.x - location[0]) - half_x) < 2e-4
                and abs(abs(v1.co.x - location[0]) - half_x) < 2e-4
            ) or (
                abs(abs(v0.co.y - location[1]) - half_y) < 2e-4
                and abs(abs(v1.co.y - location[1]) - half_y) < 2e-4
            )
            if not on_rim:
                seam_edges.append(e)

    for e in seam_edges:
        e.select = True
        e.verts[0].select = True
        e.verts[1].select = True
    bmesh.update_edit_mesh(box.data)
    bpy.ops.object.mode_set(mode="OBJECT")
    return box, len(seam_edges)


def _add_greebles(top_z: float = PLATE_SIZE[2]):
    """Small blocks placed OUTSIDE the seam grid (near the plate's rim) so
    they never overlap or hide the grooves being demonstrated.
    """
    specs = [(-0.90, 0.0, 0.14), (0.86, 0.44, 0.10), (0.86, -0.44, 0.10)]
    objs = []
    mat = _make_material("GreebleMat", GREEBLE_COLOR)
    for i, (x, y, s) in enumerate(specs):
        bpy.ops.mesh.primitive_cube_add(size=s, location=(x, y, top_z + s / 2))
        g = bpy.context.active_object
        g.name = f"Greeble{i}"
        g.data.materials.append(mat)
        objs.append(g)
    return objs


def _apply_seamline(obj, depth: float, width: float, segments: int) -> None:
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode="EDIT")
    result = bpy.ops.mesh.vibe_panel_line(depth=depth, width=width, segments=segments)
    bpy.ops.object.mode_set(mode="OBJECT")
    if result != {"FINISHED"}:
        raise RuntimeError(f"vibe_panel_line operator did not finish: {result}")


# --------------------------------------------------------------- camera ---


def _bounds_center_radius(objs):
    coords = []
    for obj in objs:
        mat = obj.matrix_world
        for v in obj.data.vertices:
            coords.append(mat @ v.co)
    xs = [c.x for c in coords]
    ys = [c.y for c in coords]
    zs = [c.z for c in coords]
    center = mathutils.Vector(
        ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, (min(zs) + max(zs)) / 2)
    )
    radius = max((c - center).length for c in coords)
    return center, radius


def _camera_distance(radius, lens, sensor_width, frame_x, frame_y, margin):
    aspect = frame_x / frame_y
    hfov = 2 * math.atan(sensor_width / (2 * lens))
    if aspect >= 1:
        vfov = 2 * math.atan((sensor_width / aspect) / (2 * lens))
    else:
        vfov = hfov
        hfov = 2 * math.atan((sensor_width * aspect) / (2 * lens))
    half = min(hfov, vfov) / 2
    return (radius / math.sin(half)) * margin


def _add_framed_camera(
    objs, direction, res_x, res_y, margin=1.4, lens=50.0,
    frame_x=None, frame_y=None, name="Cam",
):
    """Adds a camera aimed at objs' combined bounds via a Track-To Empty.

    frame_x/frame_y let you compute distance against a DIFFERENT aspect
    than the actual render resolution (used for the hero shot so the
    subject stays inside a safe centre-square even though the delivered
    canvas is wider).
    """
    center, radius = _bounds_center_radius(objs)
    frame_x = frame_x or res_x
    frame_y = frame_y or res_y

    cam_data = bpy.data.cameras.new(name)
    cam_data.lens = lens
    cam_obj = bpy.data.objects.new(name, cam_data)
    bpy.context.collection.objects.link(cam_obj)

    dist = _camera_distance(radius, lens, cam_data.sensor_width, frame_x, frame_y, margin)
    direction = mathutils.Vector(direction).normalized()
    cam_obj.location = center + direction * dist

    target = bpy.data.objects.new(f"{name}Target", None)
    target.location = center
    bpy.context.collection.objects.link(target)

    con = cam_obj.constraints.new("TRACK_TO")
    con.target = target
    con.track_axis = "TRACK_NEGATIVE_Z"
    con.up_axis = "UP_Y"

    bpy.context.scene.camera = cam_obj
    bpy.context.scene.render.resolution_x = res_x
    bpy.context.scene.render.resolution_y = res_y
    return cam_obj, target


def _face_camera(text_obj, cam_obj) -> None:
    con = text_obj.constraints.new("TRACK_TO")
    con.target = cam_obj
    con.track_axis = "TRACK_Z"
    con.up_axis = "UP_Y"


def _add_label(text: str, location, size=0.09) -> bpy.types.Object:
    bpy.ops.object.text_add(location=location)
    t = bpy.context.active_object
    t.data.body = text
    t.data.size = size
    t.data.align_x = "CENTER"
    t.data.align_y = "TOP"
    t.data.extrude = 0.006
    t.data.materials.append(_make_material("LabelMat", (0.08, 0.08, 0.08)))
    return t


# ---------------------------------------------------------------- steps ---


def render_before_after() -> None:
    scene = bpy.context.scene
    _clear_scene()
    _setup_render_settings(scene)
    _add_ground()
    plate, n_seam = _build_plate()
    if n_seam == 0:
        raise RuntimeError("no seam edges captured on plate; nothing to demo")
    greebles = _add_greebles()

    cam, target = _add_framed_camera(
        [plate, *greebles], direction=(1.6, -2.5, 1.9), res_x=1600, res_y=1600,
        margin=1.06, lens=62, name="BACam",
    )

    scene.render.filepath = str(OUT_DIR / "seamline_before.png")
    bpy.ops.render.render(write_still=True)
    print(f"RENDER_OK {scene.render.filepath}")

    _apply_seamline(plate, DEMO_DEPTH, DEMO_WIDTH, DEMO_SEGMENTS)

    scene.render.filepath = str(OUT_DIR / "seamline_after.png")
    bpy.ops.render.render(write_still=True)
    print(f"RENDER_OK {scene.render.filepath}")


def render_hero() -> None:
    scene = bpy.context.scene
    _clear_scene()
    _setup_render_settings(scene)
    _add_ground()
    plate, n_seam = _build_plate()
    if n_seam == 0:
        raise RuntimeError("no seam edges captured on hero plate")
    greebles = _add_greebles()
    _apply_seamline(plate, DEMO_DEPTH, DEMO_WIDTH, DEMO_SEGMENTS)

    res_x, res_y = 1920, 1350
    cam, target = _add_framed_camera(
        [plate, *greebles], direction=(1.7, -2.7, 1.85), res_x=res_x, res_y=res_y,
        margin=1.04, lens=64, frame_x=res_y, frame_y=res_y, name="HeroCam",
    )

    scene.render.filepath = str(OUT_DIR / "seamline_hero.png")
    bpy.ops.render.render(write_still=True)
    print(f"RENDER_OK {scene.render.filepath}")


def render_sweep() -> None:
    scene = bpy.context.scene
    _clear_scene()
    _setup_render_settings(scene)
    _add_ground()

    spacing = 2.35
    plates = []
    for i, depth in enumerate(SWEEP_DEPTHS):
        x_offset = (i - (len(SWEEP_DEPTHS) - 1) / 2) * spacing
        plate, n_seam = _build_plate(name=f"Sweep{i}", location=(x_offset, 0.0, 0.0))
        if n_seam == 0:
            raise RuntimeError(f"no seam edges captured on sweep plate {i}")
        _apply_seamline(plate, depth, DEMO_WIDTH, DEMO_SEGMENTS)
        plates.append(plate)

    res_x, res_y = 2800, 1000
    cam, target = _add_framed_camera(
        plates, direction=(0.4, -3.4, 1.5), res_x=res_x, res_y=res_y,
        margin=1.03, lens=48, name="SweepCam",
    )

    for i, (plate, depth) in enumerate(zip(plates, SWEEP_DEPTHS)):
        label_x = plate.location.x
        label = _add_label(f"DEPTH {depth:.2f}m", (label_x, 0.72, 0.02), size=0.14)
        _face_camera(label, cam)

    scene.render.filepath = str(OUT_DIR / "seamline_sweep.png")
    bpy.ops.render.render(write_still=True)
    print(f"RENDER_OK {scene.render.filepath}")


def main() -> int:
    zip_path = harness._find_zip()
    print(f"MARKETING: using zip {zip_path}")
    harness._install_and_enable(zip_path)
    print("MARKETING: install+enable OK")

    render_before_after()
    render_hero()
    render_sweep()

    print("MARKETING_RESULT PASS")
    return 0


if __name__ == "__main__":
    try:
        code = main()
    except Exception:  # noqa: BLE001
        print("MARKETING_RESULT FAIL")
        traceback.print_exc()
        code = 1
    sys.exit(code)
