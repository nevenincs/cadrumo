#Requires -Version 5.1
<#
.SYNOPSIS
  Runs the packaged desktop end-to-end test from an interactive desktop session.

.DESCRIPTION
  Builds the test host with the webview2-remote-debugging feature in the
  configured repository build, then runs the packaged end-to-end test that the
  desktop-packaged-test target runs, against an assembled package with
  documentation. Each run uses a fresh storage root. Results go to
  <BuildDirectory>\desktop\test-results\packaged\<timestamp>\. BuildDirectory
  defaults to build\<preset>, the binary directory of the repository's Windows
  x64 configure preset; the desktop has no build directory of its own, and this
  script never configures one. Configure the repository build first.

  The package defaults to the build's own stage\<Configuration>\app. Give
  -PackageRoot, another assembled package that carries
  docs\user\manifest.json, or -Kit, a directory holding app\ (a package) and
  docs-staged\user\ (staged documentation). A kit is copied, never modified,
  into <BuildDirectory>\desktop\testing\packaged\package\ with the
  documentation under docs\user\, and the copy is reused while the kit's
  manifests are unchanged.

  During the run the test types into the window's terminals, sends real key
  presses and clicks only while the test window is in the foreground, replaces
  the text clipboard and restores it at the end. Do not use the keyboard or
  mouse until it finishes.

.PARAMETER PrepareOnly
  Assemble the package, configure and build the test host, and stop before
  the run. It needs no desktop session.

.PARAMETER AllowBrowser
  Let the external-link check reach the host, which opens the system browser.
  Without it the shell's open_external request is recorded and answered
  before it reaches the host.
#>
[CmdletBinding(DefaultParameterSetName = 'Package')]
param(
    [Parameter(ParameterSetName = 'Package')][string]$PackageRoot,
    [Parameter(ParameterSetName = 'Kit', Mandatory = $true)][string]$Kit,
    [string]$BuildDirectory,
    [ValidateSet('Release', 'Debug', 'RelWithDebInfo', 'MinSizeRel')][string]$Configuration = 'Release',
    [string]$RustBin,
    [string]$DevPython,
    [switch]$AllowBrowser,
    [switch]$PrepareOnly,
    [switch]$Yes
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0

$Repository = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..\..')).ProviderPath
$Desktop = Join-Path $Repository 'native\desktop'

# The repository build is the desktop's only build: its binary directory is
# build\<name> of the configure preset that targets Windows x64.
function Get-HostBuildDirectory([string]$Repository) {
    $presets = (Get-Content -LiteralPath (Join-Path $Repository 'CMakePresets.json') -Raw | ConvertFrom-Json).configurePresets
    $selected = @($presets | Where-Object {
        $_.PSObject.Properties['cacheVariables'] -and $_.cacheVariables.PSObject.Properties['CADRUMO_TARGET'] -and
        $_.cacheVariables.CADRUMO_TARGET -eq 'windows-x86-64'
    })
    if ($selected.Count -ne 1) { throw 'The repository presets do not name exactly one Windows x64 configure preset.' }
    return [IO.Path]::GetFullPath((Join-Path (Join-Path $Repository 'build') $selected[0].name))
}

if (-not $BuildDirectory) { $BuildDirectory = Get-HostBuildDirectory $Repository }
$BuildDirectory = [IO.Path]::GetFullPath($BuildDirectory)
if (-not $DevPython) { $DevPython = Join-Path $Repository '.venv\Scripts\python.exe' }
if (-not (Test-Path -LiteralPath $DevPython)) { throw "Development interpreter not found: $DevPython (pass -DevPython)" }
$DevPython = (Resolve-Path -LiteralPath $DevPython).ProviderPath

$session = [Diagnostics.Process]::GetCurrentProcess().SessionId
if ($session -eq 0 -and -not $PrepareOnly) {
    throw 'This is Session 0, which has no interactive desktop. Run this script from a signed-in desktop session.'
}

function Get-Sha256([string]$Path) {
    $sha = [Security.Cryptography.SHA256]::Create()
    $stream = [IO.File]::OpenRead($Path)
    try { return -join ($sha.ComputeHash($stream) | ForEach-Object { $_.ToString('x2') }) }
    finally { $stream.Dispose(); $sha.Dispose() }
}

function Invoke-Checked([string]$File, [string[]]$Arguments) {
    & $File @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$File exited with $LASTEXITCODE" }
}

function Assert-UnlinkedBuildMember([string]$Path) {
    $root = [IO.Path]::GetFullPath($BuildDirectory).TrimEnd([char[]]@('\','/'))
    $candidate = [IO.Path]::GetFullPath($Path)
    $prefix = $root + [IO.Path]::DirectorySeparatorChar
    if (-not $candidate.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Output path is outside the selected build directory: $candidate"
    }
    $current = $root
    $relative = $candidate.Substring($prefix.Length)
    $separators = [char[]]@([IO.Path]::DirectorySeparatorChar, [IO.Path]::AltDirectorySeparatorChar)
    foreach ($part in $relative.Split($separators)) {
        if (-not $part) { continue }
        $current = Join-Path $current $part
        if (Test-Path -LiteralPath $current) {
            $item = Get-Item -LiteralPath $current -Force
            if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
                throw "Output path contains a symlink or junction: $current"
            }
        }
    }
}

# The package ------------------------------------------------------------------
$source = $null
if ($PSCmdlet.ParameterSetName -eq 'Kit') {
    $Kit = (Resolve-Path -LiteralPath $Kit).ProviderPath.TrimEnd('\')
    $kitApp = Join-Path $Kit 'app'
    $kitDocs = Join-Path $Kit 'docs-staged\user'
    foreach ($required in @((Join-Path $kitApp 'python.exe'), (Join-Path $kitApp 'data\package-manifest.json'), (Join-Path $kitDocs 'manifest.json'))) {
        if (-not (Test-Path -LiteralPath $required)) { throw "Kit file missing: $required" }
    }
    $PackageRoot = Join-Path $BuildDirectory 'desktop\testing\packaged\package'
    $wanted = [ordered]@{
        kit                  = $Kit
        packageManifestSha256 = Get-Sha256 (Join-Path $kitApp 'data\package-manifest.json')
        docsManifestSha256   = Get-Sha256 (Join-Path $kitDocs 'manifest.json')
    }
    $source = "a copy of the smoke kit $Kit (not a package built from HEAD)"
} else {
    if (-not $PackageRoot) { $PackageRoot = Join-Path $BuildDirectory "stage\$Configuration\app" }
    $PackageRoot = (Resolve-Path -LiteralPath $PackageRoot).ProviderPath.TrimEnd('\')
    $source = "the assembled package $PackageRoot"
}
Write-Host ''
Write-Host 'CADRUMO packaged desktop test'
Write-Host "  package: $source"
Write-Host "  build:   $BuildDirectory ($Configuration)"
Write-Host "  session: $session"
Write-Host ''
if (-not $PrepareOnly) {
    Write-Host 'The run takes several minutes. Do not use the keyboard or mouse until it ends.'
    Write-Host 'It replaces your text clipboard during the run and restores it at the end.'
    if ($AllowBrowser) { Write-Host 'The external-link check will open https://example.com/cadrumo-s10 in your browser.' }
    $others = @(Get-Process -Name 'cadrumo' -ErrorAction SilentlyContinue)
    if ($others.Count -gt 0) {
        Write-Warning ('A CADRUMO desktop process is running (' + (($others | ForEach-Object { $_.Id }) -join ', ') + '). Close it first: one window runs per user, so the test window would not open.')
    }
    if (-not $Yes) { [void](Read-Host 'Press Enter to start') }
}

# Build and run -------------------------------------------------------------------
# The configured repository build is admitted, with its physical preset
# directory and output manifest, before the kit is copied anywhere inside it.
Push-Location $Repository
try {
    $admittedBuild = & $DevPython -B -c 'import sys; from dev.packaging.native.build_directory import require_enrolled_build; print(require_enrolled_build(sys.argv[1]))' $BuildDirectory
    if ($LASTEXITCODE -ne 0 -or -not $admittedBuild) {
        throw 'The selected directory is not a configured repository build preset.'
    }
} finally {
    Pop-Location
}
$BuildDirectory = [IO.Path]::GetFullPath([string]$admittedBuild)

if ($PSCmdlet.ParameterSetName -eq 'Kit') {
    $marker = Join-Path $PackageRoot 'kit-source.json'
    $kitDocsDestination = Join-Path $PackageRoot 'docs\user'
    Assert-UnlinkedBuildMember $PackageRoot
    Assert-UnlinkedBuildMember $kitDocsDestination
    Assert-UnlinkedBuildMember $marker
    $current = $null
    if (Test-Path -LiteralPath $marker) { $current = Get-Content -LiteralPath $marker -Raw | ConvertFrom-Json }
    $same = $current -and $current.kit -eq $wanted.kit -and
        $current.packageManifestSha256 -eq $wanted.packageManifestSha256 -and
        $current.docsManifestSha256 -eq $wanted.docsManifestSha256
    if (-not $same) {
        if (Test-Path -LiteralPath $PackageRoot) {
            if (-not (Test-Path -LiteralPath $marker)) {
                throw "Refusing to replace ${PackageRoot}: it is not a kit copy this script made."
            }
            Remove-Item -LiteralPath $PackageRoot -Recurse -Force
        }
        Write-Host "Copying the kit package and staged documentation into $PackageRoot"
        & robocopy.exe $kitApp $PackageRoot /E /MT:16 /NFL /NDL /NJH /NJS /NP /XF cadrumo.exe cadrumo-production.exe | Out-Null
        if ($LASTEXITCODE -ge 8) { throw "robocopy of the package failed with $LASTEXITCODE" }
        Assert-UnlinkedBuildMember $kitDocsDestination
        & robocopy.exe $kitDocs $kitDocsDestination /E /MT:16 /NFL /NDL /NJH /NJS /NP | Out-Null
        if ($LASTEXITCODE -ge 8) { throw "robocopy of the documentation failed with $LASTEXITCODE" }
        Assert-UnlinkedBuildMember $marker
        $wanted | ConvertTo-Json | Set-Content -LiteralPath $marker -Encoding UTF8
    }
}
foreach ($required in @('python.exe', 'data\package-manifest.json', 'docs\user\manifest.json')) {
    if (-not (Test-Path -LiteralPath (Join-Path $PackageRoot $required))) { throw "The package has no $required" }
}

if ($RustBin) { $env:CADRUMO_DESKTOP_RUST_BIN = $RustBin }
# desktop-packaged-host depends on the native contract and the frontend bundle of this build.
Invoke-Checked 'cmake' @('--build', $BuildDirectory, '--config', $Configuration, '--target', 'desktop-packaged-host')
if ($PrepareOnly) {
    Write-Host "Prepared. Run again without -PrepareOnly from a desktop session; package $PackageRoot"
    exit 0
}

# The environment desktop-packaged-test gives the test, with this run's package:
# the shared build's configured package root is not rewritten for one run.
$paths = (Get-Content -LiteralPath (Join-Path $BuildDirectory 'build-paths.json') -Raw | ConvertFrom-Json).paths
$temporary = Join-Path (Join-Path $BuildDirectory $paths.desktop_testing) 'temporary'
Assert-UnlinkedBuildMember $temporary
New-Item -ItemType Directory -Path $temporary -Force | Out-Null
Push-Location $Repository
try {
    $rootVariable = & $DevPython -B -c 'from cadrumo.core.storage_environment import STORAGE_ROOT; print(STORAGE_ROOT.variable)'
    if ($LASTEXITCODE -ne 0 -or -not $rootVariable) { throw 'Cannot resolve the canonical storage-root variable.' }
} finally {
    Pop-Location
}
$results = Join-Path $BuildDirectory ('desktop\test-results\packaged\' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
$runEnvironment = [ordered]@{
    CADRUMO_CMAKE_BINARY_DIR       = $BuildDirectory
    TEMP                           = $temporary
    TMP                            = $temporary
    TMPDIR                         = $temporary
    CADRUMO_BUILD_CONFIG           = $Configuration
    CADRUMO_NATIVE_CONTRACT        = Join-Path (Join-Path $BuildDirectory $paths.generated) 'contract.json'
    CADRUMO_DESKTOP_PACKAGE_ROOT   = $PackageRoot
    CADRUMO_STORAGE_ROOT_VARIABLE  = $rootVariable.Trim()
    CADRUMO_PACKAGED_RESULTS       = $results
    CADRUMO_PACKAGED_ALLOW_BROWSER = $(if ($AllowBrowser) { '1' } else { '0' })
}
$saved = @{}
foreach ($name in $runEnvironment.Keys) {
    $saved[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
    [Environment]::SetEnvironmentVariable($name, [string]$runEnvironment[$name], 'Process')
}
Push-Location $BuildDirectory
try {
    & node --test (Join-Path $Desktop 'tests\packaged.test.mjs')
    $exitCode = $LASTEXITCODE
} finally {
    Pop-Location
    foreach ($name in $saved.Keys) { [Environment]::SetEnvironmentVariable($name, $saved[$name], 'Process') }
}

Write-Host ''
$summary = Join-Path $results 'summary.txt'
if (Test-Path -LiteralPath $summary) {
    Get-Content -LiteralPath $summary | Write-Host
    Write-Host ''
    Write-Host "Results: $results"
} else {
    Write-Warning "No summary was written; see the build output above. Expected results in $results"
}
exit $exitCode
