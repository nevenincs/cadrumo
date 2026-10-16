#Requires -Version 5.1
<#
.SYNOPSIS
  Windows convenience wrapper for native Tauri backend checks.
.DESCRIPTION
  Portable entry points are the desktop-host-unit-test and desktop-host-unit-clippy
  CMake targets. This wrapper assumes a Windows preset and virtual environment.
  BuildDirectory defaults to the binary directory of the Windows x64 configure
  preset in native\desktop\CMakePresets.json. It must already contain the
  standalone CMake build-path manifest and generated native contract. Unit runs
  mock-IPC, policy and subprocess tests.
  Package adds real PTY/projection probes against an existing assembled package;
  use Filter to select a capability. Neither mode starts the GUI or rebuilds the
  supplied package. Clippy checks native targets. Cargo compiles test artifacts
  incrementally in the selected preset's declared desktop_cargo output.
.EXAMPLE
  ./native/desktop/tests/run-backend.ps1 -Filter shell::sign_in
.EXAMPLE
  ./native/desktop/tests/run-backend.ps1 -Mode Package -PackageRoot <existing-app> -Filter python_kind_is_a_repl
#>
[CmdletBinding()]
param(
    [string]$BuildDirectory,
    [ValidateSet('Unit','Package','Clippy')][string]$Mode = 'Unit',
    [string]$PackageRoot,
    [string]$Filter,
    [string]$RustBin,
    [string]$DevPython
)
$ErrorActionPreference = 'Stop'
$repository = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..\..')).ProviderPath
# The standalone desktop project's presets own the default build directory:
# the preset that configures the Windows x64 target names it.
function Get-DesktopPreset([string]$Source) {
    $presets = (Get-Content -LiteralPath (Join-Path $Source 'CMakePresets.json') -Raw | ConvertFrom-Json).configurePresets
    $selected = @($presets | Where-Object { $_.cacheVariables.CADRUMO_TARGET -eq 'windows-x86-64' })
    if ($selected.Count -ne 1) { throw 'The desktop presets do not name exactly one Windows x64 configure preset.' }
    $binary = $selected[0].binaryDir.Replace('${sourceDir}', $Source).Replace('${presetName}', $selected[0].name)
    return [pscustomobject]@{ Name = $selected[0].name; BinaryDirectory = [IO.Path]::GetFullPath($binary) }
}
if (-not $BuildDirectory) { $BuildDirectory = (Get-DesktopPreset (Join-Path $repository 'native\desktop')).BinaryDirectory }
if (-not $DevPython) { $DevPython = Join-Path $repository '.venv\Scripts\python.exe' }
if (-not (Test-Path -LiteralPath $DevPython)) { throw "Development interpreter not found: $DevPython (pass -DevPython)" }
$DevPython = (Resolve-Path -LiteralPath $DevPython).ProviderPath
Push-Location -LiteralPath $repository
try {
    $admittedBuild = & $DevPython -B -c 'import sys; from dev.packaging.native.build_directory import require_enrolled_build; print(require_enrolled_build(sys.argv[1]))' $BuildDirectory
    if ($LASTEXITCODE -ne 0 -or -not $admittedBuild) {
        throw 'The selected desktop directory is not a configured enrolled build preset.'
    }
} finally {
    Pop-Location
}
$buildRoot = [IO.Path]::GetFullPath([string]$admittedBuild)
$cacheLine = Select-String -LiteralPath (Join-Path $buildRoot 'CMakeCache.txt') -Pattern '^CMAKE_HOME_DIRECTORY:[^=]*=(.*)$'
if (-not $cacheLine) { throw "The selected build has no CMake source directory: $buildRoot" }
$cacheSource = [IO.Path]::GetFullPath($cacheLine.Matches[0].Groups[1].Value)
$desktopSource = [IO.Path]::GetFullPath((Join-Path $repository 'native\desktop'))
if (-not $cacheSource.Equals($desktopSource, [StringComparison]::OrdinalIgnoreCase)) {
    throw "The selected preset does not configure the standalone desktop project: $buildRoot"
}
$paths = (Get-Content -LiteralPath (Join-Path $buildRoot 'build-paths.json') -Raw | ConvertFrom-Json).paths
function Resolve-BuildMember([string]$Member) {
    $candidate = [IO.Path]::GetFullPath((Join-Path $buildRoot $Member))
    if (-not $candidate.StartsWith($buildRoot.TrimEnd('\') + '\', [StringComparison]::OrdinalIgnoreCase)) {
        throw "Build member escapes the selected build directory: $Member"
    }
    return $candidate
}
$generated = Resolve-BuildMember $paths.generated
$testing = Resolve-BuildMember $paths.desktop_testing
foreach ($name in @('contract.json','contract.rs','identity.json')) {
    if (-not (Test-Path -LiteralPath (Join-Path $generated $name))) { throw "Missing generated $name; configure/generate native metadata first." }
}
if ($Mode -eq 'Clippy' -and $Filter) { throw 'Clippy does not accept a test filter.' }
if ($Mode -eq 'Package' -and -not $PackageRoot) { throw 'Package mode requires an existing assembled PackageRoot.' }
if ($PackageRoot) { $PackageRoot = (Resolve-Path -LiteralPath $PackageRoot).ProviderPath }
$saved = @{}
function Set-TestEnvironment([string]$Name, [string]$Value) {
    if (-not $saved.ContainsKey($Name)) { $saved[$Name] = [Environment]::GetEnvironmentVariable($Name, 'Process') }
    [Environment]::SetEnvironmentVariable($Name, $Value, 'Process')
}
Push-Location -LiteralPath $repository
try {
    $rootVariable = & $DevPython -B -c 'from cadrumo.core.storage_environment import STORAGE_ROOT; print(STORAGE_ROOT.variable)'
    if ($LASTEXITCODE -ne 0 -or -not $rootVariable) { throw 'Cannot resolve the canonical storage-root variable.' }
    $allowlist = & $DevPython -B -c 'import json, sys; print("\n".join(json.load(open(sys.argv[1], encoding="utf-8"))["application_environment"]["location_names"]))' (Join-Path $generated 'contract.json')
    if ($LASTEXITCODE -ne 0) { throw 'Cannot read the generated storage environment allow-list.' }
    foreach ($name in $allowlist) { Set-TestEnvironment $name $null }
    $runRoot = Join-Path $testing ('backend-runs\' + [Guid]::NewGuid().ToString('N'))
    $storage = Join-Path $runRoot 'storage'
    $temporary = Join-Path $runRoot 'temporary'
    & $DevPython -B -c 'import sys; from dev.packaging.native.build_directory import require_enrolled_output; [require_enrolled_output(path) for path in sys.argv[1:]]' $storage $temporary
    if ($LASTEXITCODE -ne 0) { throw 'The backend storage and temporary directories are not enrolled build outputs.' }
    New-Item -ItemType Directory -Path $storage -Force | Out-Null
    New-Item -ItemType Directory -Path $temporary -Force | Out-Null
    Set-TestEnvironment $rootVariable.Trim() $storage
    Set-TestEnvironment 'CADRUMO_STORAGE_ROOT' $storage
    Set-TestEnvironment 'CADRUMO_LOCAL_STORAGE_ROOT' $storage
    Set-TestEnvironment 'TEMP' $temporary
    Set-TestEnvironment 'TMP' $temporary
    Set-TestEnvironment 'TMPDIR' $temporary
    Set-TestEnvironment 'CADRUMO_CMAKE_BINARY_DIR' $buildRoot
    Set-TestEnvironment 'CADRUMO_BUILD_CONFIG' 'Debug'
    Set-TestEnvironment 'CADRUMO_NATIVE_CONTRACT' (Join-Path $generated 'contract.json')
    Set-TestEnvironment 'CADRUMO_DESKTOP_PACKAGE_ROOT' $PackageRoot
    if ($RustBin) { Set-TestEnvironment 'CADRUMO_DESKTOP_RUST_BIN' $RustBin }
    & $DevPython -B (Join-Path $repository 'native\desktop\src-tauri\src\shell\sign_in\cli_contract_fixtures.py') --check
    if ($LASTEXITCODE -ne 0) { throw 'CLI contract fixtures differ from the current canonical producers.' }
    $action = @{ Unit='test-unit'; Package='test-package'; Clippy='clippy-backend' }[$Mode]
    $arguments = @((Join-Path $repository 'native\desktop\scripts\tauri.mjs'), $action)
    if ($Filter) { $arguments += $Filter }
    Write-Host "Native backend $Mode checks; isolated storage: $storage"
    & node @arguments
    $testExit = $LASTEXITCODE
} finally {
    foreach ($name in $saved.Keys) { [Environment]::SetEnvironmentVariable($name, $saved[$name], 'Process') }
    Pop-Location
}
exit $testExit
