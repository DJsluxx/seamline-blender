# Vibe Toolkit (Blender add-on) — scaffold

STATUS: scaffold. This repo currently ships a placeholder demo feature
(a grid-array cube generator) that exists ONLY to prove the full
build → package → install → run → test pipeline works on the exact
Blender version this machine has installed. The real product feature set
is pending the product brief and will replace `addon/operators.py` /
`addon/ui.py` without touching the packaging or test infrastructure.

## For buyers (once this is a real product)

1. Download `vibe_toolkit-<version>.zip` from your purchase.
2. Open Blender (**4.2 or newer** — this add-on uses the Extensions
   system, not the legacy `bl_info` add-on format).
3. `Edit > Preferences > Get Extensions` (or `Add-ons`) tab.
4. Click the dropdown in the top-right corner → **Install from Disk...**
5. Select the downloaded `.zip`. It installs and enables automatically.
6. Open the 3D Viewport sidebar (press `N`) → **Vibe Toolkit** tab.

**Compatibility:** built and tested against Blender 5.2.0 LTS. Minimum
supported version is declared in `addon/blender_manifest.toml`
(`blender_version_min`).

**Support:** contact info goes here once the product is real (support
email / Gumroad message).

## For developers

### Layout

- `addon/` — the installable Python package (`__init__.py`,
  `operators.py`, `ui.py`, `blender_manifest.toml`). This is exactly
  what ships to the buyer, zipped.
- `scripts/build_zip.py` — packages `addon/` into
  `dist/<id>-<version>.zip` in the Blender Extensions zip layout
  (manifest + `.py` files at the zip ROOT, no wrapping folder).
- `scripts/run_tests.ps1` — runs the test harness inside a throwaway
  Blender config so it never touches your real profile.
- `tests/test_harness.py` — the money-path test. Installs the BUILT
  zip (not source files) into a clean Blender, enables it via the
  Extensions API, runs the operator(s) against a known empty scene,
  and asserts on the resulting object/mesh state. Exits non-zero on
  any failure or exception.

### Build + test loop

```powershell
python scripts\build_zip.py
powershell -File scripts\run_tests.ps1
```

`run_tests.ps1` exits with Blender's exit code — 0 pass, 1 fail — so it
is safe to wire into CI.

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
to actually work, exactly like our first attempt did.
