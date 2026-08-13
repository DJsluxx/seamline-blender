"""Headless install/enable/run/assert test harness.

This is the money-path test: it proves the artifact a buyer would actually
download (the built zip in dist/) installs cleanly into a FRESH Blender
config, enables without errors, its operator runs and produces the exact
scene state expected, and unregister leaves no leaked classes.

Must be invoked FROM INSIDE BLENDER, e.g.:

    "<blender.exe>" --background --factory-startup --python tests/test_harness.py

It exits 0 on success and 1 (via bpy's own process exit through sys.exit)
on any assertion failure or exception. It never mutates the developer's
real Blender config: BLENDER_USER_RESOURCES is expected to be pointed at a
throwaway temp dir by the calling wrapper script (run_tests.ps1 / .sh) so
addon_install() writes into an isolated scripts/addons folder.
"""

from __future__ import annotations

import sys
import traceback

import bpy

# As of Blender 4.2+/5.x, locally-installed extensions are namespaced under
# bl_ext.<repo_module>.<extension_id> — verified empirically against this
# machine's Blender 5.2.0 LTS (addon_utils.paths() no longer scans the
# legacy scripts/addons folder at all, so a bl_info-only zip silently does
# nothing; extensions.package_install_files() is the only working path).
REPO_MODULE = "user_default"
EXTENSION_ID = "vibe_toolkit"
MODULE_NAME = f"bl_ext.{REPO_MODULE}.{EXTENSION_ID}"
ZIP_GLOB_HINT = "dist/vibe_toolkit-*.zip"


def _find_zip() -> str:
    import glob
    import pathlib

    root = pathlib.Path(__file__).resolve().parent.parent
    matches = sorted((root / "dist").glob("vibe_toolkit-*.zip"))
    if not matches:
        raise FileNotFoundError(
            f"No built zip found matching {ZIP_GLOB_HINT}. Run scripts/build_zip.py first."
        )
    return str(matches[-1])


def _fresh_scene():
    # Deliberately NOT bpy.ops.wm.read_factory_settings(): that resets
    # preferences too and silently disables/unregisters any extension
    # enabled this session. We only need an empty object list, so remove
    # objects directly and leave the enabled-add-on state alone.
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)


def _install_and_enable(zip_path: str) -> None:
    result = bpy.ops.extensions.package_install_files(
        filepath=zip_path,
        repo=REPO_MODULE,
        enable_on_install=True,
        overwrite=True,
    )
    if result != {"FINISHED"}:
        raise RuntimeError(f"package_install_files did not finish cleanly: {result}")

    import addon_utils

    is_enabled, is_loaded = addon_utils.check(MODULE_NAME)
    if not (is_enabled and is_loaded):
        raise RuntimeError(
            f"addon not reported enabled+loaded after install: "
            f"enabled={is_enabled} loaded={is_loaded} (module={MODULE_NAME})"
        )


def _run_operator_and_assert() -> None:
    _fresh_scene()

    before_count = len(bpy.data.objects)
    if before_count != 0:
        raise AssertionError(f"expected empty scene, found {before_count} objects")

    result = bpy.ops.vibe.grid_array(count_x=3, count_y=2, spacing=2.0)
    if result != {"FINISHED"}:
        raise AssertionError(f"operator did not finish: {result}")

    objs = [o for o in bpy.data.objects if o.name.startswith("VibeGridCube_")]
    expected = 3 * 2
    if len(objs) != expected:
        raise AssertionError(f"expected {expected} grid cubes, found {len(objs)}")

    for obj in objs:
        if obj.type != "MESH":
            raise AssertionError(f"{obj.name} is not a MESH object: {obj.type}")
        mesh = obj.data
        if len(mesh.vertices) != 8:
            raise AssertionError(
                f"{obj.name} expected 8 verts (a cube), found {len(mesh.vertices)}"
            )
        if len(mesh.polygons) != 6:
            raise AssertionError(
                f"{obj.name} expected 6 faces (a cube), found {len(mesh.polygons)}"
            )

    xs = sorted({round(o.location.x, 4) for o in objs})
    if xs != [0.0, 2.0, 4.0]:
        raise AssertionError(f"unexpected X spacing layout: {xs}")


def _unregister_leaves_no_classes() -> None:
    bpy.ops.preferences.addon_disable(module=MODULE_NAME)

    leaked = [
        cls_name
        for cls_name in ("VIBE_OT_grid_array", "VIBE_PT_main_panel")
        if hasattr(bpy.types, cls_name)
    ]
    if leaked:
        raise AssertionError(f"classes still registered after disable: {leaked}")


def main() -> int:
    zip_path = _find_zip()
    print(f"HARNESS: using zip {zip_path}")

    _install_and_enable(zip_path)
    print("HARNESS: install+enable OK")

    _run_operator_and_assert()
    print("HARNESS: operator run + scene assertions OK")

    _unregister_leaves_no_classes()
    print("HARNESS: disable leaves no leaked classes OK")

    print("HARNESS_RESULT PASS")
    return 0


if __name__ == "__main__":
    try:
        code = main()
    except Exception:  # noqa: BLE001 - top-level harness boundary, must not raise
        print("HARNESS_RESULT FAIL")
        traceback.print_exc()
        code = 1
    sys.exit(code)
