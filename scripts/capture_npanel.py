"""Attempts to screenshot the real Seamline N-panel inside a live Blender
window (not a mockup). --background mode has no window/UI region at all,
so this MUST run without --background (a real, briefly-visible window,
same pattern as tests/test_undo.py uses for bpy.ops.ed.undo()):

    "<blender.exe>" --factory-startup --python scripts/capture_npanel.py

It installs the built add-on, opens Edit Mode on a cube with edges
selected (so the panel shows its real "ready to run" state, not the
"enter edit mode" placeholder), forces the 3D Viewport sidebar (N-panel)
open on the Seamline tab if the API allows selecting it, waits for the
window to actually draw via bpy.app.timers, screenshots the whole
window, then quits.
"""

from __future__ import annotations

import pathlib
import sys

import bpy

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))
import test_harness as harness  # noqa: E402

OUT_PATH = ROOT / "marketing" / "seamline_npanel.png"


def _setup_scene() -> None:
    try:
        bpy.context.preferences.view.show_splash = False
    except Exception as exc:  # noqa: BLE001
        print(f"CAPTURE: could not disable splash: {exc}")

    zip_path = harness._find_zip()
    harness._install_and_enable(zip_path)

    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)

    bpy.ops.mesh.primitive_cube_add(size=2.0)
    obj = bpy.context.active_object
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")

    win = bpy.context.window_manager.windows[0]
    screen = win.screen
    view3d_area = next(a for a in screen.areas if a.type == "VIEW_3D")
    space = view3d_area.spaces.active
    space.show_region_ui = True
    ui_region = next(r for r in view3d_area.regions if r.type == "UI")
    try:
        with bpy.context.temp_override(window=win, area=view3d_area, region=ui_region):
            bpy.context.region.active_panel_category = "Seamline"
        print("CAPTURE: set active_panel_category via context override ok")
    except Exception as exc:  # noqa: BLE001
        print(f"CAPTURE: could not set active_panel_category: {exc}")
    ui_region.tag_redraw()
    view3d_area.tag_redraw()
    print("CAPTURE: scene + N-panel setup done")


def _click_seamline_tab() -> None:
    """Real OS-level click on the N-panel 'Seamline' tab.

    bpy gives no public setter for Region.active_panel_category (confirmed
    read-only via the RNA API on this Blender build), so the only way to
    actually switch to it, short of a human doing it, is a genuine mouse
    click on the tab, exactly like a user would. Position is derived from
    the known window rect (bpy.context.window) plus the tab strip's
    measured position from an initial screenshot of THIS window (5 tabs:
    Item/Tool/View/Animation/Seamline, Seamline last => bottom tab).
    """
    import ctypes

    user32 = ctypes.windll.user32
    fg = user32.GetForegroundWindow()
    pid = ctypes.c_ulong()
    user32.GetWindowThreadProcessId(fg, ctypes.byref(pid))
    import os

    if pid.value != os.getpid():
        print(
            f"CAPTURE: SKIPPING synthetic click — the foreground window "
            f"(pid={pid.value}) is not this Blender process (pid={os.getpid()}); "
            "clicking blind would risk hitting an unrelated window."
        )
        return

    win = bpy.context.window
    print(f"CAPTURE: window rect x={win.x} y={win.y} w={win.width} h={win.height}")

    # Measured on a 2560x1369 window: tab strip column x~2080, Seamline
    # (5th/last of 5 tabs) label centre y~263. Scale to the actual window.
    ref_w, ref_h = 2560, 1369
    tab_x, tab_y = 2080, 263
    x = win.x + int(tab_x * (win.width / ref_w))
    y = win.y + int(tab_y * (win.height / ref_h))
    print(f"CAPTURE: clicking Seamline tab at screen ({x}, {y})")

    user32.SetCursorPos(x, y)
    MOUSEEVENTF_LEFTDOWN = 0x0002
    MOUSEEVENTF_LEFTUP = 0x0004
    user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)


def _screenshot_and_quit() -> None:
    try:
        win = bpy.context.window_manager.windows[0]
        with bpy.context.temp_override(window=win):
            bpy.ops.wm.redraw_timer(type="DRAW_WIN_SWAP", iterations=5)

        _click_seamline_tab()

        def _final_shot():
            try:
                with bpy.context.temp_override(window=win):
                    bpy.ops.wm.redraw_timer(type="DRAW_WIN_SWAP", iterations=5)
                    result = bpy.ops.screen.screenshot(filepath=str(OUT_PATH))
                print(f"CAPTURE: screenshot op result = {result}")
                if OUT_PATH.exists():
                    print(f"CAPTURE_OK {OUT_PATH} ({OUT_PATH.stat().st_size} bytes)")
                else:
                    print("CAPTURE_FAIL: screenshot operator finished but no file was written")
            except Exception:  # noqa: BLE001
                import traceback

                print("CAPTURE_FAIL: exception during screenshot")
                traceback.print_exc()
            finally:
                bpy.ops.wm.quit_blender()
            return None

        bpy.app.timers.register(_final_shot, first_interval=0.6)
    except Exception:  # noqa: BLE001
        import traceback

        print("CAPTURE_FAIL: exception before final screenshot")
        traceback.print_exc()
        bpy.ops.wm.quit_blender()
    return None


def main() -> None:
    _setup_scene()
    bpy.app.timers.register(_screenshot_and_quit, first_interval=2.0)


main()
