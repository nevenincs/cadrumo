#Requires -Version 5.1
<#
.SYNOPSIS
  Runs the packaged desktop end-to-end test from an interactive desktop session.

.DESCRIPTION
  Configures the standalone desktop build, generates the native contract, builds
  the test host with the webview2-remote-debugging feature and runs the
  desktop-packaged-test target against an assembled package with documentation.
  Each run uses a fresh storage root. Results go to
  <BuildDirectory>\desktop\test-results\packaged\<timestamp>\. BuildDirectory
  defaults to the binary directory of the Windows x64 configure preset in
  native\desktop\CMakePresets.json, and the build is then configured through
  that preset.

  Give either -PackageRoot, an assembled package that carries
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
    [Parameter(ParameterSetName = 'Package', Mandatory = $true)][string]$PackageRoot,
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

# The standalone desktop project's presets own the default build directory:
# the preset that configures the Windows x64 target names it.
function Get-DesktopPreset([string]$Source) {
    $presets = (Get-Content -LiteralPath (Join-Path $Source 'CMakePresets.json') -Raw | ConvertFrom-Json).configurePresets
    $selected = @($presets | Where-Object { $_.cacheVariables.CADRUMO_TARGET -eq 'windows-x86-64' })
    if ($selected.Count -ne 1) { throw 'The desktop presets do not name exactly one Windows x64 configure preset.' }
    $binary = $selected[0].binaryDir.Replace('${sourceDir}', $Source).Replace('${presetName}', $selected[0].name)
    return [pscustomobject]@{ Name = $selected[0].name; BinaryDirectory = [IO.Path]::GetFullPath($binary) }
}

$Preset = $null
if (-not $BuildDirectory) {
    $Preset = Get-DesktopPreset $Desktop
    $BuildDirectory = $Preset.BinaryDirectory
}
$BuildDirectory = [IO.Path]::GetFullPath($BuildDirectory)
if (-not $DevPython) { $DevPython = Join-Path $Repository '.venv\Scripts\python.exe' }
if (-not (Test-Path -LiteralPath $DevPython)) { throw "Development interpreter not found: $DevPython (pass -DevPython)" }

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
    $marker = Join-Path $PackageRoot 'kit-source.json'
    $wanted = [ordered]@{
        kit                  = $Kit
        packageManifestSha256 = Get-Sha256 (Join-Path $kitApp 'data\package-manifest.json')
        docsManifestSha256   = Get-Sha256 (Join-Path $kitDocs 'manifest.json')
    }
    $current = $null
    if (Test-Path -LiteralPath $marker) { $current = Get-Content -LiteralPath $marker -Raw | ConvertFrom-Json }
    $same = $current -and $current.kit -eq $wanted.kit -and
        $current.packageManifestSha256 -eq $wanted.packageManifestSha256 -and
        $current.docsManifestSha256 -eq $wanted.docsManifestSha256
    if (-not $same) {
        if (Test-Path -LiteralPath $PackageRoot) {
            $resolved = (Resolve-Path -LiteralPath $PackageRoot).ProviderPath
            $owned = $resolved.StartsWith((Join-Path $BuildDirectory 'desktop\testing\packaged\'), [StringComparison]::OrdinalIgnoreCase)
            if (-not $owned -or -not (Test-Path -LiteralPath $marker)) {
                throw "Refusing to replace ${resolved}: it is not a kit copy this script made."
            }
            Remove-Item -LiteralPath $resolved -Recurse -Force
        }
        Write-Host "Copying the kit package and staged documentation into $PackageRoot"
        & robocopy.exe $kitApp $PackageRoot /E /MT:16 /NFL /NDL /NJH /NJS /NP /XF cadrumo.exe cadrumo-production.exe | Out-Null
        if ($LASTEXITCODE -ge 8) { throw "robocopy of the package failed with $LASTEXITCODE" }
        & robocopy.exe $kitDocs (Join-Path $PackageRoot 'docs\user') /E /MT:16 /NFL /NDL /NJH /NJS /NP | Out-Null
        if ($LASTEXITCODE -ge 8) { throw "robocopy of the documentation failed with $LASTEXITCODE" }
        $wanted | ConvertTo-Json | Set-Content -LiteralPath $marker -Encoding UTF8
    }
    $source = "a copy of the smoke kit $Kit (not a package built from HEAD)"
} else {
    $PackageRoot = (Resolve-Path -LiteralPath $PackageRoot).ProviderPath.TrimEnd('\')
    $source = "the assembled package $PackageRoot"
}
foreach ($required in @('python.exe', 'data\package-manifest.json', 'docs\user\manifest.json')) {
    if (-not (Test-Path -LiteralPath (Join-Path $PackageRoot $required))) { throw "The package has no $required" }
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
$configure = @('-S', $Desktop)
if ($Preset) {
    # The preset pins the generator and the binary directory.
    $configure += @('--preset', $Preset.Name)
} else {
    if (-not (Test-Path -LiteralPath (Join-Path $BuildDirectory 'CMakeCache.txt')) -and (Get-Command ninja -ErrorAction SilentlyContinue)) {
        $configure = @('-G', 'Ninja') + $configure
    }
    $configure += @('-B', $BuildDirectory, "-DCMAKE_BUILD_TYPE=$Configuration")
}
$configure += @("-DCADRUMO_DESKTOP_PACKAGE_ROOT=$PackageRoot", "-DCADRUMO_DEV_PYTHON=$DevPython")
Invoke-Checked 'cmake' $configure
Push-Location $Repository
try { Invoke-Checked $DevPython @('-B', '-m', 'dev.packaging.native.generate', (Join-Path $BuildDirectory 'generated')) }
finally { Pop-Location }
if (-not (Test-Path -LiteralPath (Join-Path $Repository 'native\desktop\frontend\node_modules'))) {
    Invoke-Checked 'cmake' @('--build', $BuildDirectory, '--config', $Configuration, '--target', 'desktop-frontend-install')
}

if ($RustBin) { $env:CADRUMO_DESKTOP_RUST_BIN = $RustBin }
if ($PrepareOnly) {
    Invoke-Checked 'cmake' @('--build', $BuildDirectory, '--config', $Configuration, '--target', 'desktop-packaged-host')
    Write-Host "Prepared. Run again without -PrepareOnly from a desktop session; package $PackageRoot"
    exit 0
}

$results = Join-Path $BuildDirectory ('desktop\test-results\packaged\' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
$env:CADRUMO_PACKAGED_RESULTS = $results
$env:CADRUMO_PACKAGED_ALLOW_BROWSER = if ($AllowBrowser) { '1' } else { '0' }
& cmake --build $BuildDirectory --config $Configuration --target desktop-packaged-test
$exitCode = $LASTEXITCODE

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
