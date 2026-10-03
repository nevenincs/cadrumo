<#
Shared PowerShell mirror of cadrumo.core.storage_environment.

Callers pass their own repository anchor because the release smoke copies this
script set into a disposable harness. Relative category values resolve below
the configured local/shared storage root; absolute values remain independent
overrides.
#>

function Get-CadrumoStorageRoot {
    param([Parameter(Mandatory = $true)][string]$RepositoryRoot)
    $anchor = $RepositoryRoot
    if (-not (Test-Path -LiteralPath (Join-Path $anchor "pyproject.toml") -PathType Leaf)) {
        $workingDirectory = (Get-Location).Path
        if (Test-Path -LiteralPath (Join-Path $workingDirectory "pyproject.toml") -PathType Leaf) {
            $anchor = $workingDirectory
        }
    }
    $configuredRoot = ([string]$env:CADRUMO_LOCAL_STORAGE_ROOT).Trim()
    if (-not $configuredRoot) {
        $configuredRoot = ([string]$env:CADRUMO_STORAGE_ROOT).Trim()
    }
    if (-not $configuredRoot) { $configuredRoot = "var/storage" }
    if ([System.IO.Path]::IsPathRooted($configuredRoot)) {
        return [System.IO.Path]::GetFullPath($configuredRoot)
    }
    return [System.IO.Path]::GetFullPath((Join-Path $anchor $configuredRoot))
}

function Resolve-CadrumoStoragePath {
    param(
        [Parameter(Mandatory = $true)][string]$Value,
        [Parameter(Mandatory = $true)][string]$RepositoryRoot
    )
    if ([System.IO.Path]::IsPathRooted($Value)) {
        return [System.IO.Path]::GetFullPath($Value)
    }
    return [System.IO.Path]::GetFullPath(
        (Join-Path (Get-CadrumoStorageRoot -RepositoryRoot $RepositoryRoot) $Value)
    )
}

function Get-CadrumoStorageDirectory {
    param(
        [Parameter(Mandatory = $true)][string]$EnvironmentVariable,
        [Parameter(Mandatory = $true)][string]$Default,
        [Parameter(Mandatory = $true)][string]$RepositoryRoot
    )
    $configuredPath = ([string][Environment]::GetEnvironmentVariable($EnvironmentVariable)).Trim()
    if (-not $configuredPath) { $configuredPath = $Default }
    return Resolve-CadrumoStoragePath -Value $configuredPath -RepositoryRoot $RepositoryRoot
}

function Initialize-CadrumoScoopStorageEnvironment {
    param([Parameter(Mandatory = $true)][string]$RepositoryRoot)
    $cacheArguments = @{
        EnvironmentVariable = "CADRUMO_SCOOP_CACHE_DIR"
        Default = "development/cache/scoop"
        RepositoryRoot = $RepositoryRoot
    }
    $configArguments = @{
        EnvironmentVariable = "CADRUMO_TOOL_CONFIG_DIR"
        Default = "development/config/tools"
        RepositoryRoot = $RepositoryRoot
    }
    $scoopCache = Get-CadrumoStorageDirectory @cacheArguments
    $toolConfig = Get-CadrumoStorageDirectory @configArguments
    New-Item -ItemType Directory -Force -Path $scoopCache | Out-Null
    New-Item -ItemType Directory -Force -Path $toolConfig | Out-Null
    $env:SCOOP_CACHE = $scoopCache
    $env:XDG_CONFIG_HOME = $toolConfig
}
