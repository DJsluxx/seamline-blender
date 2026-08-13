"""Build the installable add-on zip.

Packages `addon/` into `dist/<id>-<version>.zip` in the Blender Extensions
layout: blender_manifest.toml and the Python module files sit at the ROOT
of the zip (no wrapping folder) — that is what
bpy.ops.extensions.package_install_files() expects on Blender 4.2+/5.x.

Usage:
    python scripts/build_zip.py
"""

from __future__ import annotations

import pathlib
import sys
import zipfile

try:
    import tomllib  # Python 3.11+
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore[no-redef]

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "addon"
DIST_DIR = ROOT / "dist"
MANIFEST_PATH = SRC_DIR / "blender_manifest.toml"


def _read_manifest() -> dict:
    if not MANIFEST_PATH.exists():
        raise FileNotFoundError(f"manifest not found: {MANIFEST_PATH}")
    with MANIFEST_PATH.open("rb") as f:
        return tomllib.load(f)


def build() -> pathlib.Path:
    if not SRC_DIR.exists():
        raise FileNotFoundError(f"add-on source dir not found: {SRC_DIR}")

    manifest = _read_manifest()
    ext_id = manifest["id"]
    version = manifest["version"]

    DIST_DIR.mkdir(parents=True, exist_ok=True)
    out_path = DIST_DIR / f"{ext_id}-{version}.zip"
    if out_path.exists():
        out_path.unlink()

    py_files = sorted(SRC_DIR.glob("*.py"))
    if not py_files:
        raise FileNotFoundError(f"no .py files found in {SRC_DIR}")

    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(MANIFEST_PATH, MANIFEST_PATH.name)
        for f in py_files:
            zf.write(f, f.name)

    return out_path


if __name__ == "__main__":
    path = build()
    print(f"BUILD_OK {path}")
    sys.exit(0)
