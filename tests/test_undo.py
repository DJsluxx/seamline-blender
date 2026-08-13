"""Clean-undo test for Seamline (acceptance criterion 3).

Split out from test_harness.py because Blender's `ed.undo` operator polls
false in `--background` mode ("context is incorrect" — no window exists
there; verified empirically on this machine's 5.2.0). This script must be
run WITHOUT --background so a real (briefly-visible) window exists:

    "<blender.exe>" --factory-startup --python tests/test_undo.py

It installs the built zip into an isolated extensions repo (same as
test_harness.py), runs the Panel Line operator once, and asserts that
exactly ONE bpy.ops.ed.undo() call fully reverts it: modifier gone, seam
attribute gone, topology unchanged, no leftover datablocks. Exits 0/1.
"""

from __future__ import annotations

import sys
import traceback

import bpy

REPO_MODULE = "user_default"
EXTENSION_ID = "seamline"
MODULE_NAME = f"bl_ext.{REPO_MODULE}.{EXTENSION_ID}"


def _find_zip() -> str:
    import pathlib

    root = pathlib.Path(__file__).resolve().parent.parent
    matches = sorted((root / "dist").glob("seamline-*.zip"))
    if not matches:
        raise FileNotFoundError("No built zip found in dist/. Run scripts/build_zip.py first.")
    return str(matches[-1])


def _install_and_enable(zip_path: str) -> None:
    result = bpy.ops.extensions.package_install_files(
        filepath=zip_path, repo=REPO_MODULE, enable_on_install=True, overwrite=True,
    )
    if result != {"FINISHED"}:
        raise RuntimeError(f"package_install_files did not finish cleanly: {result}")
    import addon_utils

    is_enabled, is_loaded = addon_utils.check(MODULE_NAME)
    if not (is_enabled and is_loaded):
        raise RuntimeError(f"addon not enabled+loaded after install (module={MODULE_NAME})")


def main() -> int:
    zip_path = _find_zip()
    print(f"UNDO_TEST: using zip {zip_path}")
    _install_and_enable(zip_path)
    print("UNDO_TEST: install+enable OK")

    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)

    bpy.ops.ed.undo_push(message="seamline undo-test baseline")

    bpy.ops.mesh.primitive_cube_add(size=2.0)
    obj = bpy.context.active_object
    obj_name = obj.name  # plain str: `obj` itself goes stale across undo's memfile reload
    verts_before = len(obj.data.vertices)
    modifiers_before = len(obj.modifiers)
    attrs_before = {a.name for a in obj.data.attributes}
    mesh_users_before = obj.data.users

    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")

    result = bpy.ops.mesh.vibe_panel_line(depth=0.05, width=0.01, segments=2)
    if result != {"FINISHED"}:
        raise AssertionError(f"operator did not finish: {result}")

    modifiers_after = len(obj.modifiers)
    attrs_after = {a.name for a in obj.data.attributes}
    if modifiers_after == modifiers_before:
        raise AssertionError("operator did not add a modifier; nothing to test undo against")
    if attrs_after == attrs_before:
        raise AssertionError("operator did not add a seam attribute; nothing to test undo against")
    print(f"UNDO_TEST: operator applied ({modifiers_before}->{modifiers_after} modifiers)")

    objects_before_undo = len(bpy.data.objects)
    meshes_before_undo = len(bpy.data.meshes)

    undo_result = bpy.ops.ed.undo()
    if undo_result != {"FINISHED"}:
        raise AssertionError(f"bpy.ops.ed.undo() did not finish: {undo_result}")

    obj_after_undo = bpy.data.objects.get(obj_name)
    if obj_after_undo is None:
        raise AssertionError(
            f"object {obj_name!r} no longer exists after a single undo step "
            "(undo reverted further than the one operator call)"
        )
    if bpy.context.active_object is None or bpy.context.active_object.name != obj_name:
        raise AssertionError("active object identity changed/lost across a single undo step")

    modifiers_final = len(obj_after_undo.modifiers)
    attrs_final = {a.name for a in obj_after_undo.data.attributes}
    verts_final = len(obj_after_undo.data.vertices)

    if modifiers_final != modifiers_before:
        raise AssertionError(
            f"one undo did not remove the modifier: before={modifiers_before} after_undo={modifiers_final}"
        )
    if attrs_final != attrs_before:
        raise AssertionError(
            f"one undo did not remove the seam attribute: before={attrs_before} after_undo={attrs_final}"
        )
    if verts_final != verts_before:
        raise AssertionError(
            f"one undo left the base mesh topology altered: before={verts_before} after_undo={verts_final}"
        )
    if len(bpy.data.objects) != objects_before_undo:
        raise AssertionError("one undo changed the object count — orphaned/leaked object")
    if len(bpy.data.meshes) > meshes_before_undo:
        raise AssertionError("one undo left a leaked mesh datablock behind")

    print("UNDO_TEST: single Ctrl+Z fully reverted modifier + attribute + topology OK")
    print("UNDO_TEST_RESULT PASS")
    return 0


if __name__ == "__main__":
    try:
        code = main()
    except Exception:  # noqa: BLE001
        print("UNDO_TEST_RESULT FAIL")
        traceback.print_exc()
        code = 1
    sys.exit(code)
