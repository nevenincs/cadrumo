#Requires -Version 5.1
<#
.SYNOPSIS
  Run native Tauri backend checks without building the frontend or package.
.DESCRIPTION
  BuildDirectory must already contain the standalone CMake build-path manifest
  and generated native contract. Unit runs mock-IPC, policy and subprocess tests.
  Package adds real PTY/projection probes against an existing assembled package;
  use Filter to select a capability. Neither mode starts the GUI or rebuilds the
  supplied package. Clippy checks native targets. Cargo compiles test artifacts
  incrementally; CARGO_TARGET_DIR may select an existing compiler cache.
.EXAMPLE
  ./native/desktop/tests/run-backend.ps1 -BuildDirectory build/windows-x86-64/e2e-desktop -Filter shell::sign_in
.EXAMPLE
  ./native/desktop/tests/run-backend.ps1 -BuildDirectory build/windows-x86-64/e2e-desktop -Mode Package -PackageRoot <existing-app> -Filter python_kind_is_a_repl
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$BuildDirectory,
    [ValidateSet('Unit','Package','Clippy')][string]$Mode = 'Unit',
    [string]$PackageRoot,
    [string]$Filter,
    [string]$RustBin,
    [string]$DevPython
)
$ErrorActionPreference = 'Stop'
$repository = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..\..')).ProviderPath
$buildRoot = (Resolve-Path -LiteralPath $BuildDirectory).ProviderPath
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
if (-not $DevPython) { $DevPython = Join-Path $repository '.venv\Scripts\python.exe' }
$DevPython = (Resolve-Path -LiteralPath $DevPython).ProviderPath
$saved = @{}
function Set-TestEnvironment([string]$Name, [string]$Value) {
    if (-not $saved.ContainsKey($Name)) { $saved[$Name] = [Environment]::GetEnvironmentVariable($Name, 'Process') }
    [Environment]::SetEnvironmentVariable($Name, $Value, 'Process')
}
Push-Location -LiteralPath $repository
try {
    $rootVariable = & $DevPython -B -c 'from cadrumo.core.storage_environment import STORAGE_ROOT; print(STORAGE_ROOT.variable)'
    if ($LASTEXITCODE -ne 0 -or -not $rootVariable) { throw 'Cannot resolve the canonical storage-root variable.' }
    $contract = Get-Content -LiteralPath (Join-Path $generated 'contract.json') -Raw | ConvertFrom-Json
    foreach ($name in $contract.storage_environment_allowlist) { Set-TestEnvironment $name $null }
    $storage = Join-Path $testing ('backend-runs\' + [Guid]::NewGuid().ToString('N') + '\storage')
    New-Item -ItemType Directory -Path $storage -Force | Out-Null
    Set-TestEnvironment $rootVariable.Trim() $storage
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
