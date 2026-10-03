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
    $installArguments = @{
        EnvironmentVariable = "CADRUMO_SCOOP_INSTALL_ROOT"
        Default = "development/packages/scoop"
        RepositoryRoot = $RepositoryRoot
    }
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
    $installRoot = Get-CadrumoStorageDirectory @installArguments
    $scoopCache = Get-CadrumoStorageDirectory @cacheArguments
    $toolConfig = Get-CadrumoStorageDirectory @configArguments
    New-Item -ItemType Directory -Force -Path $scoopCache | Out-Null
    New-Item -ItemType Directory -Force -Path $toolConfig | Out-Null
    $env:SCOOP = $installRoot
    $env:SCOOP_CACHE = $scoopCache
    $env:XDG_CONFIG_HOME = $toolConfig
}

function Set-CadrumoScoopShimsFirst {
    param([Parameter(Mandatory = $true)][string]$ScoopRoot)
    $scoopShims = Join-Path $ScoopRoot "shims"
    $normalizedShims = [System.IO.Path]::GetFullPath($scoopShims).TrimEnd('\', '/')
    $remaining = @(
        foreach ($entry in ($env:PATH -split [System.IO.Path]::PathSeparator)) {
            if (-not $entry) { continue }
            $normalizedEntry = [System.IO.Path]::GetFullPath($entry).TrimEnd('\', '/')
            if (-not $normalizedEntry.Equals($normalizedShims, [System.StringComparison]::OrdinalIgnoreCase)) {
                $entry
            }
        }
    )
    $env:PATH = (@($scoopShims) + $remaining) -join [System.IO.Path]::PathSeparator
}

function Test-CadrumoScoopCommandRoot {
    param([Parameter(Mandatory = $true)][string]$ScoopRoot)
    # Do not filter by command type here. PowerShell gives aliases and
    # functions precedence over external commands; filtering would skip a
    # shadowing command and report a shim that `scoop` will never execute.
    $command = Get-Command scoop -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $command) { return $false }
    if ([string]$command.CommandType -notin @("Application", "ExternalScript")) { return $false }
    $commandPath = [string]$command.Path
    if (-not $commandPath) { $commandPath = [string]$command.Source }
    if (-not $commandPath) { return $false }
    $root = [System.IO.Path]::GetFullPath($ScoopRoot).TrimEnd('\', '/')
    $separator = [System.IO.Path]::DirectorySeparatorChar
    $rootPrefix = "$root$separator"
    $resolvedCommand = [System.IO.Path]::GetFullPath($commandPath)
    return $resolvedCommand.StartsWith($rootPrefix, [System.StringComparison]::OrdinalIgnoreCase)
}

function Assert-CadrumoScoopCommandRoot {
    param([Parameter(Mandatory = $true)][string]$ScoopRoot)
    $expectedRoot = [System.IO.Path]::GetFullPath($ScoopRoot)
    $nativeRoot = ([string]$env:SCOOP).Trim()
    if (
        -not $nativeRoot -or
        -not [System.IO.Path]::GetFullPath($nativeRoot).Equals(
            $expectedRoot,
            [System.StringComparison]::OrdinalIgnoreCase
        )
    ) {
        throw "SCOOP does not match the selected CADRUMO_SCOOP_INSTALL_ROOT '$expectedRoot'"
    }
    if (Test-CadrumoScoopCommandRoot -ScoopRoot $expectedRoot) { return }
    $command = Get-Command scoop -ErrorAction SilentlyContinue | Select-Object -First 1
    $commandType = if ($command) { [string]$command.CommandType } else { "not found" }
    $commandPath = ""
    if ($command) {
        $pathProperty = $command.PSObject.Properties["Path"]
        if ($pathProperty) { $commandPath = [string]$pathProperty.Value }
        if (-not $commandPath) {
            $sourceProperty = $command.PSObject.Properties["Source"]
            if ($sourceProperty) { $commandPath = [string]$sourceProperty.Value }
        }
        if (-not $commandPath) { $commandPath = [string]$command.Name }
    }
    if (-not $commandPath) { $commandPath = "(not found)" }
    throw (
        "resolved Scoop command '$commandPath' (type $commandType) is not an external command under " +
        "selected install root '$expectedRoot'. " +
        "Set CADRUMO_SCOOP_INSTALL_ROOT to an existing Scoop install root; this control does not relocate " +
        "an existing Scoop installation. Use -BootstrapScoop only for a disposable container install."
    )
}
