# Runs the headless test harness against a FRESH, throwaway Blender config
# so it never touches the real developer profile. Exits with Blender's exit
# code (0 = pass, non-zero = fail), so it is CI-safe.
#
# Usage:
#   powershell -File scripts\run_tests.ps1
#   powershell -File scripts\run_tests.ps1 -BlenderExe "C:\path\to\blender.exe"

param(
    [string]$BlenderExe = "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe"
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$TempResources = Join-Path $env:TEMP ("vibe_toolkit_test_" + [guid]::NewGuid().ToString("N"))

New-Item -ItemType Directory -Force -Path $TempResources | Out-Null

try {
    $env:BLENDER_USER_RESOURCES = $TempResources

    & $BlenderExe --background --factory-startup --python "$RepoRoot\tests\test_harness.py"
    $exitCode = $LASTEXITCODE
}
finally {
    Remove-Item Env:\BLENDER_USER_RESOURCES -ErrorAction SilentlyContinue
    Remove-Item -Recurse -Force -Path $TempResources -ErrorAction SilentlyContinue
}

exit $exitCode
