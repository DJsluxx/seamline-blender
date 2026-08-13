# Runs the full Seamline test suite (headless harness + windowed undo test)
# against every Blender install passed in, each in its own throwaway
# profile. Exits non-zero if ANY run on ANY version fails.
#
# Usage:
#   powershell -File scripts\run_all_tests.ps1
#   powershell -File scripts\run_all_tests.ps1 -BlenderExes @("C:\...\blender.exe", "C:\...\blender.exe")

param(
    [string[]]$BlenderExes = @(
        "C:\Program Files\Blender Foundation\Blender 4.2\blender.exe",
        "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe"
    )
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$overallExit = 0

foreach ($exe in $BlenderExes) {
    if (-not (Test-Path $exe)) {
        Write-Output "SKIP (not installed): $exe"
        continue
    }

    Write-Output "=== HEADLESS HARNESS: $exe ==="
    & powershell -File "$RepoRoot\scripts\run_tests.ps1" -BlenderExe $exe
    if ($LASTEXITCODE -ne 0) { $overallExit = 1 }
    Write-Output "exit=$LASTEXITCODE"

    Write-Output "=== UNDO TEST (windowed): $exe ==="
    $tempResources = Join-Path $env:TEMP ("seamline_undo_" + [guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Force -Path $tempResources | Out-Null
    try {
        $env:BLENDER_USER_RESOURCES = $tempResources
        & $exe --factory-startup --python "$RepoRoot\tests\test_undo.py"
        $undoExit = $LASTEXITCODE
    }
    finally {
        Remove-Item Env:\BLENDER_USER_RESOURCES -ErrorAction SilentlyContinue
        Remove-Item -Recurse -Force -Path $tempResources -ErrorAction SilentlyContinue
    }
    if ($undoExit -ne 0) { $overallExit = 1 }
    Write-Output "exit=$undoExit"
}

exit $overallExit
