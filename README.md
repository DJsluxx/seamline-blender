# Seamline — Non-Destructive Panel Lines for Blender

Seamline adds one operator: select an edge loop on a hard-surface mesh,
run **Panel Line**, and get a re-editable, non-destructive groove along
it — a "Panel Line" **Geometry Nodes** modifier with Depth / Width /
Segments inputs you can go back and change at any time. Nothing is
baked into the mesh.

Search phrase this is aimed at: **"panel lines blender"** / "panel line
generator blender addon" / "non destructive panel lines blender" — this
is what a hard-surface modeller building greebles/mech/vehicle detail
would type looking for exactly this.

## For buyers

1. Download `seamline-<version>.zip`.
2. Open Blender **4.2 LTS or newer**.
3. `Edit > Preferences > Get Extensions` (or `Add-ons`) tab.
4. Click the dropdown in the top-right corner → **Install from Disk...**
5. Select the downloaded `.zip`. It installs and enables automatically.
6. In the 3D Viewport, select some edges in Edit Mode, open the sidebar
   (`N`) → **Seamline** tab → **Panel Line**. Or press `Ctrl Shift Alt P`.
7. Depth / Width / Segments and which edges are the seam stay editable
   afterward on the **Panel Line** modifier in the Modifier Properties
   tab — this is the point of the tool, not an afterthought.

**Compatibility — only what was actually run, nothing assumed:** the
full test suite (headless install/enable/operator/n-gon/instanced-mesh/
100k-poly harness + a separate windowed clean-undo test) passes on both
**Blender 4.2.16 LTS** and **Blender 5.2.0 LTS** on this machine. Those
are the only two versions installed and tested; `blender_version_min` in
`addon/blender_manifest.toml` is set to `4.2.0` on that basis, not a
guess. On 4.2 the groove is sharp-edged (no rim chamfer) because
`GeometryNodeMeshBevel` does not exist there — verified empirically, see
`addon/nodes.py`. On 5.2+ the groove gets a chamfered rim using
Width/Segments.

**Licence:** GPL-3.0-or-later (`addon/LICENSE.txt`, full text, ships in
the zip). You may redistribute this add-on freely; there is no licence
key, no telemetry, no phone-home, no obfuscation.

**Support:** open an issue at
<https://github.com/DJsluxx/seamline-blender/issues>.

## For developers

### Layout

- `addon/` — the installable Python package. This is exactly what ships
  to the buyer, zipped.
  - `__init__.py` — registration entry point (Extensions manifest-driven,
    no `bl_info`).
  - `operators.py` — `MESH_OT_vibe_panel_line`: reads the Edit-Mode edge
    selection, writes it as a boolean edge attribute, makes the mesh
    single-user if it was a linked duplicate, and adds a Geometry Nodes
    modifier.
  - `nodes.py` — builds the "Panel Line" Geometry Nodes group at
    runtime (Extrude Mesh + optional Mesh Bevel; see the module
    docstring for the exact graph and the 4.2/5.2 version gate).
  - `ui.py` — the `N`-panel.
  - `keymaps.py` — `Ctrl Shift Alt P` in the Mesh (Edit Mode) keymap.
  - `blender_manifest.toml` / `LICENSE.txt` — Extensions metadata and
    the full GPL-3.0 text, both shipped in the zip.
- `scripts/build_zip.py` — packages `addon/` into
  `dist/<id>-<version>.zip` in the Blender Extensions zip layout
  (manifest + `.py` files + `LICENSE.txt` at the zip ROOT).
- `scripts/run_tests.ps1` — runs the headless harness against ONE
  Blender install, inside a throwaway config.
- `scripts/run_all_tests.ps1` — runs the headless harness AND the
  windowed undo test against every installed Blender you pass it
  (defaults to the 4.2 + 5.2 installs on this machine). Non-zero exit if
  anything fails anywhere — this is the command that actually backs the
  compatibility claim above.
- `tests/test_harness.py` — the money-path test. Installs the BUILT zip
  (not source files) into a clean Blender, enables it via the Extensions
  API, and asserts: N-panel + keymap registered; the operator runs and
  produces a genuinely non-destructive, re-editable result (changing a
  modifier input after the fact changes the shape, disabling the
  modifier restores the original topology exactly); it survives an
  n-gon; it isolates instanced/linked-duplicate mesh data (no leakage
  onto sibling objects); it handles a 100k+-poly mesh. Exits non-zero on
  any failure.
- `tests/test_undo.py` — the clean-undo test (acceptance criterion:
  "one Ctrl+Z restores prior state"). Split out from test_harness.py
  because `bpy.ops.ed.undo()` polls false in `--background` mode (no
  window exists there — verified empirically), so this one runs Blender
  with a real, briefly-visible window. Asserts one undo removes the
  modifier and seam attribute, leaves topology and mesh-datablock count
  unchanged, leaves no stray objects, and that `bpy.data.orphans_purge()`
  finds nothing new to purge relative to the factory-startup baseline.

  **Read this before changing that test — two of its assertions were once
  measuring the wrong thing, and the fixes are deliberate:**

  1. *Scripted undo has different granularity than user undo.* Blender
     pushes undo steps around user interaction; a run of `bpy.ops` calls
     from a script does not produce one restorable step per call, so a
     single `ed.undo()` collapses the whole script and lands back on the
     **factory-startup snapshot**. Measured here: objects went
     `1 ['Cube']` → `3 ['Camera','Cube','Light']` across one undo. An
     assertion of the form `len(bpy.data.objects) == before` therefore
     fails for reasons that have nothing to do with this add-on. The test
     now compares against a factory baseline captured up front.
  2. *Blender's startup file ships its own orphans.* On 5.2 the
     grease-pencil material `Dots Stroke` has `users == 0` out of the box,
     so an unconditional `orphans_purge() == 0` assertion fails on a stock
     datablock. The test now asserts *no NEW orphan appears* relative to
     that baseline.
  3. *Post-undo leak checks are vacuous — this was proven, not assumed.*
     A copy of the add-on was deliberately sabotaged to leak a stray
     helper object plus a fake-user mesh, and **every post-undo assertion
     still passed**, because the undo wipes the leak along with everything
     else. The leak check therefore runs **immediately after the operator
     and before the undo**, where a leak is actually observable. With that
     check in place the sabotaged build fails with
     `operator created stray object(s) ... ['SeamlineHelper']` while the
     real build passes — which is what makes this suite non-vacuous rather
     than decorative.

### Build + test loop

```powershell
python scripts\build_zip.py
powershell -File scripts\run_all_tests.ps1
```

### Two Blender modifier-input APIs, handled explicitly

Blender 4.2 LTS stores Geometry Nodes modifier inputs as plain ID
properties (`mod["Socket_1"] = value`); 4.3+/5.x moved them behind a
typed `mod.properties.inputs.Socket_1.value` interface. Both add-on code
(`operators.py: _set_modifier_input`) and the test harness handle both,
verified empirically against both installed LTS releases rather than
assumed from release notes.

### Why the Extensions API, not `bl_info`

Verified empirically on this machine's Blender 5.2.0 LTS: `addon_utils.
paths()` no longer scans the user `scripts/addons` folder at all — a
legacy `bl_info`-only zip installs (file copy succeeds) but is silently
invisible to Blender, so `bpy.ops.preferences.addon_enable()` reports
success while the operator never actually registers. The working path
on 4.2+ is `bpy.ops.extensions.package_install_files(filepath=...,
repo="user_default", enable_on_install=True)`, and the resulting module
is namespaced `bl_ext.user_default.<extension_id>`. `tests/
test_harness.py` uses this path; do not "simplify" it back to
`addon_install`/`bl_info` without re-running the harness against a
fresh Blender profile — it will silently pass install and silently fail
to actually work.

### A note on the operator class name

Blender registers an operator under a name derived from `bl_idname`
(`mesh.vibe_panel_line` → `MESH_OT_vibe_panel_line`), **not** from the
Python class name you happen to choose. An earlier iteration of this
add-on named the class `VIBE_OT_panel_line`, which imports and runs
fine but is registered under a different `bpy.types` name than its own
class name suggests — the test harness caught this by asserting
`hasattr(bpy.types, "MESH_OT_vibe_panel_line")` rather than assuming the
Python name. Keep operator class names matching their `bl_idname`.
