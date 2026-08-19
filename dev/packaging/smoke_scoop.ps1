[CmdletBinding()]
param(
    [ValidateSet("Container", "Host")]
    [string]$Mode = "Container",

    [Parameter(Mandatory = $true)]
    [string]$CohortDir,

    [Parameter(Mandatory = $true)]
    [string]$ManifestPath,

    [Parameter(Mandatory = $true)]
    [string]$EvidenceDir,

    [ValidatePattern("^[A-Za-z0-9][A-Za-z0-9._-]*$")]
    [string]$AppName = "cadrumo-s19-stage",

    [ValidatePattern("^[A-Za-z0-9][A-Za-z0-9._/:-]*$")]
    [string]$ContainerImage = "mcr.microsoft.com/windows/servercore:ltsc2022",

    [ValidateRange(1, 240)]
    [int]$TimeoutMinutes = 60,

    [switch]$BootstrapScoop,

    [switch]$InsideContainer,

    [string]$OrchestrationNonce
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if ($BootstrapScoop -and -not $InsideContainer) {
    throw "Scoop bootstrap is restricted to the disposable Windows container child"
}
if ($InsideContainer -and $Mode -ne "Host") {
    throw "the Windows container child must execute the Host smoke implementation"
}

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path

function Invoke-Native {
    param(
        [Parameter(Mandatory = $true)]
        [string]$FilePath,

        [Parameter(Mandatory = $true)]
        [string[]]$ArgumentList,

        [string]$OutputPath
    )

    # Native stderr is DATA here: uv (invoked by the Scoop manifest's
    # installer) writes informational lines like "Using CPython ...
    # interpreter at" to stderr while exiting 0. Under the script-wide
    # $ErrorActionPreference = "Stop", Windows PowerShell 5.1 turns the FIRST
    # merged (2>&1) stderr line into a terminating NativeCommandError even
    # though the command succeeded. Scope Continue around the invocation and
    # gate success on the exit code alone; the merged output — stderr
    # included — stays captured for the failure detail, never silenced.
    $previousPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        if ($OutputPath) {
            $output = @(& $FilePath @ArgumentList 2>&1)
            $exitCode = $LASTEXITCODE
            $output | ForEach-Object { [string]$_ } |
                Set-Content -LiteralPath $OutputPath -Encoding UTF8
            if ($exitCode -ne 0) {
                $output | Select-Object -Last 200 | ForEach-Object {
                    [Console]::Error.WriteLine([string]$_)
                }
                throw "command failed with exit code ${exitCode}: $FilePath $($ArgumentList -join ' ')"
            }
            return
        }

        & $FilePath @ArgumentList 2>&1 | ForEach-Object {
            [Console]::Out.WriteLine([string]$_)
        }
        if ($LASTEXITCODE -ne 0) {
            throw "command failed with exit code ${LASTEXITCODE}: $FilePath $($ArgumentList -join ' ')"
        }
    }
    finally {
        $ErrorActionPreference = $previousPreference
    }
}

function Stop-ProcessesUnderPath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Root
    )

    # A child of the exercised venv (a lingering python/MCP subprocess, or a
    # scanner holding an open handle through it) can outlive the oracle and
    # block `scoop uninstall` with "it may be in use". Reap every process
    # whose image path is rooted under the staged app before uninstalling.
    # Separator-anchored prefix: a bare StartsWith would also match a SIBLING
    # directory sharing the name prefix (scoop\apps\python vs python-foo) and
    # reap an unrelated process on the shared runner.
    $normalizedRoot = [System.IO.Path]::GetFullPath($Root).TrimEnd(
        [System.IO.Path]::DirectorySeparatorChar,
        [System.IO.Path]::AltDirectorySeparatorChar
    ) + [System.IO.Path]::DirectorySeparatorChar
    $reaped = @()
    foreach ($process in @(Get-Process -ErrorAction SilentlyContinue)) {
        $imagePath = $null
        try { $imagePath = $process.Path } catch { continue }
        if (-not $imagePath) { continue }
        $normalizedImage = [System.IO.Path]::GetFullPath($imagePath)
        if ($normalizedImage.StartsWith($normalizedRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
            $reaped += "$($process.Id):$($process.ProcessName)"
            try { Stop-Process -Id $process.Id -Force -ErrorAction Stop } catch { }
        }
    }
    if ($reaped.Count -gt 0) {
        # Console, not the output stream: these helpers return values through
        # the pipeline, and a pipelined progress line would corrupt them.
        [Console]::Out.WriteLine("reaped processes still rooted under ${Root}: $($reaped -join ', ')")
        Start-Sleep -Seconds 2
    }
}

function Invoke-ScoopUninstallWithRetry {
    param(
        [Parameter(Mandatory = $true)]
        [string]$PackageName,

        [Parameter(Mandatory = $true)]
        [string]$AppRoot,

        [string[]]$ExtraArguments = @(),

        [int]$SettleSeconds = 4
    )

    # Windows may hold handles on the exercised venv briefly after the oracle;
    # a failed `scoop uninstall` then AUTO-REPAIRS (relinks `current` and
    # recreates the shims), so every retry must RE-RUN uninstall, never merely
    # re-check. The bounded loop only buys Windows time to release handles —
    # the caller's retained-app assertions stay fail-loud.
    for ($attempt = 1; $attempt -le 3; $attempt++) {
        Stop-ProcessesUnderPath -Root $AppRoot
        & scoop uninstall $PackageName @ExtraArguments
        if ($LASTEXITCODE -eq 0 -and -not (Test-Path -LiteralPath $AppRoot)) {
            return $true
        }
        if ($attempt -lt 3) {
            [Console]::Out.WriteLine(
                "scoop uninstall attempt $attempt left $PackageName present " +
                "(exit $LASTEXITCODE); retrying after handle settle"
            )
            Start-Sleep -Seconds $SettleSeconds
        }
    }
    return (-not (Test-Path -LiteralPath $AppRoot))
}

function Get-ScoopRoot {
    if ($env:SCOOP) {
        return [System.IO.Path]::GetFullPath($env:SCOOP)
    }
    return Join-Path ([Environment]::GetFolderPath("UserProfile")) "scoop"
}

function Install-ScoopIfRequested {
    param(
        [Parameter(Mandatory = $true)]
        [bool]$Requested,

        [Parameter(Mandatory = $true)]
        [string]$InstallerDir,

        [Parameter(Mandatory = $true)]
        [bool]$Elevated
    )

    if (-not $Requested) {
        if (-not (Get-Command scoop -ErrorAction SilentlyContinue)) {
            throw "scoop is not installed; use -BootstrapScoop only in a disposable Windows container"
        }
        return
    }

    if (-not (Get-Command scoop -ErrorAction SilentlyContinue)) {
        # The container child already launches with -ExecutionPolicy Bypass, so
        # only widen at Process scope; a CurrentUser/machine scope write is
        # rejected by the Windows container's more-specific pinned policy and
        # terminates under ErrorActionPreference Stop ("Security error.").
        try {
            Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process -Force
        }
        catch {
            # The effective policy is already Bypass from the launch flag; a
            # policy-override refusal here is non-fatal, so continue bootstrap.
        }
        [Net.ServicePointManager]::SecurityProtocol = (
            [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
        )
        $installer = Join-Path $InstallerDir "install-scoop.ps1"
        Invoke-WebRequest -Uri "https://get.scoop.sh" -OutFile $installer -UseBasicParsing
        # The Windows container runs its child elevated (ContainerAdministrator), so
        # the installer's default administrator guard must be released explicitly.
        if ($Elevated) {
            & $installer -RunAsAdmin
        }
        else {
            & $installer
        }
        if (-not $?) {
            throw "Scoop bootstrap failed"
        }
    }
    $scoopShims = Join-Path (Get-ScoopRoot) "shims"
    if (($env:PATH -split [System.IO.Path]::PathSeparator) -notcontains $scoopShims) {
        $env:PATH = "$scoopShims$([System.IO.Path]::PathSeparator)$env:PATH"
    }
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
        Invoke-Native -FilePath "scoop" -ArgumentList @("install", "git", "--no-update-scoop")
    }
}

function Get-ExecutionIdentity {
    param(
        [Parameter(Mandatory = $true)]
        [bool]$ContainerChild,

        [string]$Nonce
    )

    $runtimeIdentity = [Security.Principal.WindowsIdentity]::GetCurrent().Name
    $observedContainer = $runtimeIdentity.EndsWith(
        "\ContainerAdministrator",
        [System.StringComparison]::OrdinalIgnoreCase
    )
    if ($ContainerChild) {
        if (-not $Nonce) {
            throw "container child execution requires an orchestration nonce"
        }
        if (-not $observedContainer) {
            throw "container child identity was not observed: $runtimeIdentity"
        }
    }
    elseif ($Nonce) {
        throw "host execution must not accept a container orchestration nonce"
    }
    return @{
        mode = if ($ContainerChild) { "Container" } else { "Host" }
        orchestration_nonce = if ($ContainerChild) { $Nonce } else { $null }
        runtime_identity = $runtimeIdentity
        container_identity_verified = $observedContainer
    }
}

function Write-LocalScoopManifest {
    param(
        [Parameter(Mandatory = $true)]
        [string]$SourceManifest,

        [Parameter(Mandatory = $true)]
        [string]$SourceCohort,

        [Parameter(Mandatory = $true)]
        [string]$Destination
    )

    $manifest = Get-Content -LiteralPath $SourceManifest -Raw | ConvertFrom-Json
    $architecture = $manifest.architecture."64bit"
    $urls = @($architecture.url)
    $hashes = @($architecture.hash)
    if ($urls.Count -ne 3 -or $hashes.Count -ne 3) {
        throw "expected three Scoop cohort URLs and hashes"
    }

    for ($index = 0; $index -lt $urls.Count; $index += 1) {
        $sourceUri = [Uri]$urls[$index]
        $filename = [Uri]::UnescapeDataString(
            [System.IO.Path]::GetFileName($sourceUri.AbsolutePath)
        )
        $artifact = (Resolve-Path (Join-Path $SourceCohort $filename)).Path
        $observedHash = (Get-FileHash -LiteralPath $artifact -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($observedHash -ne ([string]$hashes[$index]).ToLowerInvariant()) {
            throw "cohort hash mismatch for ${filename}: expected $($hashes[$index]), got $observedHash"
        }
        $architecture.url[$index] = ([Uri]$artifact).AbsoluteUri
    }

    New-Item -ItemType Directory -Force -Path (Split-Path $Destination -Parent) | Out-Null
    $manifest | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $Destination -Encoding UTF8
}

function Get-ScoopCommandPath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$CommandName,

        [Parameter(Mandatory = $true)]
        [string]$ScoopRoot
    )

    $resolved = @(& scoop which $CommandName)
    if ($LASTEXITCODE -ne 0 -or $resolved.Count -ne 1) {
        throw "scoop did not resolve exactly one installed target for ${CommandName}: $resolved"
    }
    $target = (Resolve-Path ([string]$resolved[0]).Trim()).Path
    $expectedRoot = (Resolve-Path (Join-Path $ScoopRoot "apps")).Path
    if (-not $target.StartsWith(
        "$expectedRoot$([System.IO.Path]::DirectorySeparatorChar)",
        [System.StringComparison]::OrdinalIgnoreCase
    )) {
        throw "scoop resolved ${CommandName} outside its installed apps root: $target"
    }
    $shim = (Resolve-Path (Join-Path $ScoopRoot "shims\${CommandName}.cmd")).Path
    $expectedShimRoot = (Resolve-Path (Join-Path $ScoopRoot "shims")).Path
    if (-not $shim.StartsWith(
        "$expectedShimRoot$([System.IO.Path]::DirectorySeparatorChar)",
        [System.StringComparison]::OrdinalIgnoreCase
    )) {
        throw "scoop resolved ${CommandName} shim outside its shims root: $shim"
    }
    return $shim
}

function Invoke-InstalledOracle {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Prefix,

        [Parameter(Mandatory = $true)]
        [string]$AeatCommand,

        [Parameter(Mandatory = $true)]
        [string]$OutputDir
    )

    $python = (Resolve-Path (Join-Path $Prefix "venv\Scripts\python.exe")).Path
    $taxEvidence = Join-Path $OutputDir "tax-evidence.json"
    $taxState = Join-Path $OutputDir "tax-state"
    $taxWork = Join-Path $OutputDir "tax-work"

    # The Scoop manifest's pre_install pinned the transitive closure through
    # `uv pip install --constraint constraints.txt`; assert the venv it produced
    # actually landed on those pins before the tax oracle mints evidence on it.
    # The constraints file was written into the app dir beside the venv.
    $constraints = (Resolve-Path (Join-Path $Prefix "constraints.txt")).Path

    Push-Location $RepoRoot
    try {
        Invoke-Native -FilePath $python -ArgumentList @(
            "-m", "dev.packaging.constraint_effect",
            "--python", $python,
            "--constraints", $constraints
        ) -OutputPath (Join-Path $OutputDir "constraint-effect.log")
        Invoke-Native -FilePath $python -ArgumentList @(
            "-m", "dev.packaging.installed_tax_oracle",
            "--cli", $AeatCommand,
            "--storage-root", $taxState,
            "--work-dir", $taxWork,
            "--output", $taxEvidence
        ) -OutputPath (Join-Path $OutputDir "tax-oracle.log")
    }
    finally {
        Pop-Location
    }

    return @{
        tax_evidence = (Resolve-Path $taxEvidence).Path
    }
}

function Invoke-HostSmoke {
    param(
        [Parameter(Mandatory = $true)]
        [string]$SourceCohort,

        [Parameter(Mandatory = $true)]
        [string]$SourceManifest,

        [Parameter(Mandatory = $true)]
        [string]$OutputDir,

        [Parameter(Mandatory = $true)]
        [string]$PackageName,

        [Parameter(Mandatory = $true)]
        [hashtable]$ExecutionIdentity
    )

    $resolvedCohort = (Resolve-Path $SourceCohort).Path
    $resolvedManifest = (Resolve-Path $SourceManifest).Path
    New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
    $resolvedEvidence = (Resolve-Path $OutputDir).Path
    $failurePath = Join-Path $resolvedEvidence "scoop-failure.json"
    if (Test-Path -LiteralPath $failurePath -PathType Leaf) {
        Remove-Item -LiteralPath $failurePath -Force
    }
    $runId = [DateTimeOffset]::UtcNow.ToString("yyyyMMddTHHmmssfffZ")
    $runEvidence = Join-Path $resolvedEvidence "run-$runId"
    New-Item -ItemType Directory -Force -Path $runEvidence | Out-Null
    $bucketName = "cadrumo-s19-$($runId.ToLowerInvariant())"
    $bucketRoot = Join-Path $runEvidence "bucket"
    $bucketManifestDir = Join-Path $bucketRoot "bucket"
    New-Item -ItemType Directory -Force -Path $bucketManifestDir | Out-Null
    $candidateManifest = Join-Path $bucketManifestDir "${PackageName}.json"
    $scoopRoot = Get-ScoopRoot
    $appsRoot = Join-Path $scoopRoot "apps"
    $appRoot = Join-Path $appsRoot $PackageName
    $bucketRegistrationRoot = Join-Path $scoopRoot "buckets\$bucketName"
    $persistEntriesRoot = Join-Path $scoopRoot "persist"
    $persistRoot = Join-Path $scoopRoot "persist\$PackageName"
    $uvRoot = Join-Path $appsRoot "uv"
    $pythonRoot = Join-Path $appsRoot "python"
    $preexistingScoopApps = @(
        Get-ChildItem -LiteralPath $appsRoot -Directory | ForEach-Object { $_.Name }
    )
    $preexistingScoopPersistEntries = @(
        if (Test-Path -LiteralPath $persistEntriesRoot -PathType Container) {
            Get-ChildItem -LiteralPath $persistEntriesRoot -Directory |
                ForEach-Object { $_.Name }
        }
    )
    $uvWasInstalled = Test-Path -LiteralPath (Join-Path $uvRoot "current")
    $pythonWasInstalled = Test-Path -LiteralPath (Join-Path $pythonRoot "current")
    $appWasInstalled = Test-Path -LiteralPath $appRoot
    if ($appWasInstalled) {
        throw "refusing to replace existing Scoop app $PackageName"
    }
    if (Test-Path -LiteralPath $persistRoot) {
        throw "refusing to replace existing persisted state for Scoop app $PackageName"
    }

    Write-LocalScoopManifest `
        -SourceManifest $resolvedManifest `
        -SourceCohort $resolvedCohort `
        -Destination $candidateManifest
    Invoke-Native -FilePath "git" -ArgumentList @("-C", $bucketRoot, "init", "--quiet")
    Invoke-Native -FilePath "git" -ArgumentList @(
        "-C", $bucketRoot, "-c", "user.name=Cadrumo packaging smoke",
        "-c", "user.email=packaging-smoke@invalid.example",
        "add", "bucket/${PackageName}.json"
    )
    Invoke-Native -FilePath "git" -ArgumentList @(
        "-C", $bucketRoot, "-c", "user.name=Cadrumo packaging smoke",
        "-c", "user.email=packaging-smoke@invalid.example",
        "commit", "--quiet", "-m", "stage immutable Cadrumo cohort"
    )

    $startedAt = [DateTimeOffset]::UtcNow
    $installed = $false
    $bucketRegistered = $false
    $evidence = $null
    try {
        $bucketUrl = ([Uri]$bucketRoot).AbsoluteUri
        Invoke-Native -FilePath "scoop" -ArgumentList @(
            "bucket", "add", $bucketName, $bucketUrl
        )
        $bucketRegistered = $true
        Invoke-Native -FilePath "scoop" -ArgumentList @(
            "install", "${bucketName}/${PackageName}", "--no-cache", "--no-update-scoop"
        )
        $installed = $true

        $prefixOutput = @(& scoop prefix $PackageName)
        if ($LASTEXITCODE -ne 0 -or $prefixOutput.Count -ne 1) {
            throw "scoop did not return one installed prefix for $PackageName"
        }
        $prefix = (Resolve-Path ([string]$prefixOutput[0])).Path
        $aeat = Get-ScoopCommandPath -CommandName "aeat" -ScoopRoot $scoopRoot

        Invoke-Native -FilePath $aeat -ArgumentList @("--version")

        $persistState = Join-Path $scoopRoot "persist\$PackageName\state"
        if (-not (Test-Path -LiteralPath $persistState -PathType Container)) {
            throw "Scoop persistence directory was not created: $persistState"
        }
        $marker = Join-Path $persistState "scoop-update-persistence.txt"
        [DateTimeOffset]::UtcNow.ToString("O") |
            Set-Content -LiteralPath $marker -Encoding UTF8
        $markerHash = (Get-FileHash -LiteralPath $marker -Algorithm SHA256).Hash.ToLowerInvariant()
        $transientMarker = Join-Path $prefix "scoop-update-transient.txt"
        "Scoop must replace this non-persisted file during update." |
            Set-Content -LiteralPath $transientMarker -Encoding UTF8

        Invoke-Native -FilePath "scoop" -ArgumentList @(
            "update", $PackageName, "--force", "--no-cache"
        )
        if (Test-Path -LiteralPath $transientMarker -PathType Leaf) {
            throw "Scoop update did not replace the installed application directory"
        }
        if (-not (Test-Path -LiteralPath $marker -PathType Leaf)) {
            throw "Scoop update removed persisted state marker"
        }
        $updatedMarkerHash = (
            Get-FileHash -LiteralPath $marker -Algorithm SHA256
        ).Hash.ToLowerInvariant()
        if ($updatedMarkerHash -ne $markerHash) {
            throw "Scoop update changed persisted state marker"
        }

        Invoke-Native -FilePath "scoop" -ArgumentList @("uninstall", $PackageName)
        if (Test-Path -LiteralPath (Join-Path $scoopRoot "apps\$PackageName\current")) {
            throw "Scoop uninstall retained the active app link for $PackageName"
        }
        $installed = $false
        if (-not (Test-Path -LiteralPath $marker -PathType Leaf)) {
            throw "Scoop uninstall removed persisted state marker"
        }
        $uninstalledMarkerHash = (
            Get-FileHash -LiteralPath $marker -Algorithm SHA256
        ).Hash.ToLowerInvariant()
        if ($uninstalledMarkerHash -ne $markerHash) {
            throw "Scoop uninstall changed persisted state marker"
        }

        Invoke-Native -FilePath "scoop" -ArgumentList @(
            "install", "${bucketName}/${PackageName}", "--no-cache", "--no-update-scoop"
        )
        $installed = $true
        if (-not (Test-Path -LiteralPath $marker -PathType Leaf)) {
            throw "Scoop reinstall did not restore persisted state marker"
        }
        $reinstalledMarkerHash = (
            Get-FileHash -LiteralPath $marker -Algorithm SHA256
        ).Hash.ToLowerInvariant()
        if ($reinstalledMarkerHash -ne $markerHash) {
            throw "Scoop reinstall changed persisted state marker"
        }

        $prefixOutput = @(& scoop prefix $PackageName)
        if ($LASTEXITCODE -ne 0 -or $prefixOutput.Count -ne 1) {
            throw "scoop did not return the reinstalled prefix for $PackageName"
        }
        $prefix = (Resolve-Path ([string]$prefixOutput[0])).Path
        $aeat = Get-ScoopCommandPath -CommandName "aeat" -ScoopRoot $scoopRoot
        $oracleEvidence = Invoke-InstalledOracle `
            -Prefix $prefix `
            -AeatCommand $aeat `
            -OutputDir $runEvidence

        $evidence = [ordered]@{
            schema = "cadrumo.packaging.scoop-smoke.v2"
            status = "passed"
            mode = $ExecutionIdentity.mode
            orchestration_nonce = $ExecutionIdentity.orchestration_nonce
            runtime_identity = $ExecutionIdentity.runtime_identity
            container_identity_verified = $ExecutionIdentity.container_identity_verified
            app_name = $PackageName
            started_at = $startedAt.ToString("O")
            os = (Get-CimInstance Win32_OperatingSystem).Caption
            architecture = $env:PROCESSOR_ARCHITECTURE
            scoop_version = (@(& scoop --version) -join "`n").Trim()
            source_manifest = $resolvedManifest
            source_manifest_sha256 = (
                Get-FileHash -LiteralPath $resolvedManifest -Algorithm SHA256
            ).Hash.ToLowerInvariant()
            bucket_name = $bucketName
            bucket_url = $bucketUrl
            bucket_root = $bucketRoot
            candidate_manifest = $candidateManifest
            run_evidence = $runEvidence
            preexisting_scoop_apps = $preexistingScoopApps
            preexisting_scoop_persist_entries = $preexistingScoopPersistEntries
            uv_preexisting = $uvWasInstalled
            python_preexisting = $pythonWasInstalled
            installed_prefix = $prefix
            aeat_command = $aeat
            persisted_marker = $marker
            persisted_marker_sha256 = $reinstalledMarkerHash
            update_preserved_persistence = $true
            uninstall_preserved_persistence = $true
            reinstall_preserved_persistence = $true
            tax_evidence = $oracleEvidence.tax_evidence
            # The manifest is CLI-only; cadrumo-mcp ships in the sibling
            # cadrumo-harness distribution, which Scoop does not install.
            mcp_evidence = $null
        }
    }
    finally {
        $cleanupErrors = [System.Collections.Generic.List[string]]::new()
        $newScoopApps = @()
        if ($installed -or (Test-Path -LiteralPath $appRoot)) {
            if (-not (Invoke-ScoopUninstallWithRetry `
                        -PackageName $PackageName `
                        -AppRoot $appRoot `
                        -ExtraArguments @("--purge"))) {
                $cleanupErrors.Add("failed to remove staged Scoop app $PackageName")
            }
        }
        if (Test-Path -LiteralPath $persistRoot) {
            Remove-Item -LiteralPath $persistRoot -Recurse -Force
        }
        if ($bucketRegistered -or (Test-Path -LiteralPath $bucketRegistrationRoot)) {
            & scoop bucket rm $bucketName
            if ($LASTEXITCODE -ne 0) {
                $cleanupErrors.Add("failed to remove staged Scoop bucket $bucketName")
            }
        }
        $newScoopApps = @(
            Get-ChildItem -LiteralPath $appsRoot -Directory |
                Where-Object { $preexistingScoopApps -notcontains $_.Name } |
                ForEach-Object { $_.Name }
        )
        foreach ($newScoopApp in $newScoopApps) {
            if (-not (Invoke-ScoopUninstallWithRetry `
                        -PackageName $newScoopApp `
                        -AppRoot (Join-Path $appsRoot $newScoopApp) `
                        -ExtraArguments @("--purge"))) {
                $cleanupErrors.Add(
                    "failed to remove Scoop app installed by the smoke run: $newScoopApp"
                )
            }
        }
        if ($cleanupErrors.Count -gt 0) {
            throw ($cleanupErrors -join "; ")
        }
        if (Test-Path -LiteralPath $appRoot) {
            throw "cleanup retained the staged Scoop app $PackageName"
        }
        if (Test-Path -LiteralPath $persistRoot) {
            throw "cleanup retained persisted state for staged Scoop app $PackageName"
        }
        if (Test-Path -LiteralPath $bucketRegistrationRoot) {
            throw "cleanup retained the staged Scoop bucket $bucketName"
        }
        $retainedNewApps = @(
            Get-ChildItem -LiteralPath $appsRoot -Directory |
                Where-Object { $preexistingScoopApps -notcontains $_.Name } |
                ForEach-Object { $_.Name }
        )
        if ($retainedNewApps.Count -gt 0) {
            throw "cleanup retained Scoop apps installed by the smoke run: $($retainedNewApps -join ', ')"
        }
        $retainedNewPersistEntries = @(
            if (Test-Path -LiteralPath $persistEntriesRoot -PathType Container) {
                Get-ChildItem -LiteralPath $persistEntriesRoot -Directory |
                    Where-Object {
                        $preexistingScoopPersistEntries -notcontains $_.Name
                    } |
                    ForEach-Object { $_.Name }
            }
        )
        if ($retainedNewPersistEntries.Count -gt 0) {
            throw (
                "cleanup retained persisted state installed by the smoke run: " +
                ($retainedNewPersistEntries -join ", ")
            )
        }
    }
    if ($null -eq $evidence) {
        throw "Scoop smoke completed without pass evidence"
    }
    $evidence["cleanup_status"] = "passed"
    $evidence["cleanup_removed_app"] = $true
    $evidence["cleanup_removed_bucket"] = $true
    $evidence["cleanup_removed_new_apps"] = $newScoopApps
    $evidence["cleanup_verified_new_app_persistence_absent"] = $newScoopApps
    $evidence["cleanup_removed_new_uv"] = $newScoopApps -contains "uv"
    $evidence["cleanup_removed_new_python"] = $newScoopApps -contains "python"
    $evidence["completed_at"] = [DateTimeOffset]::UtcNow.ToString("O")
    $evidence |
        ConvertTo-Json -Depth 20 |
        Set-Content -LiteralPath (Join-Path $resolvedEvidence "scoop-evidence.json") -Encoding UTF8
}

function Assert-WindowsContainerRuntime {
    $docker = Get-Command docker -ErrorAction SilentlyContinue
    if (-not $docker) {
        throw (
            "Windows container runtime required: 'docker' was not found on PATH. " +
            "Run this lane on a host with Docker in Windows-container mode " +
            "(GitHub-hosted windows-2022, or a local Docker Desktop switched to Windows containers)."
        )
    }
    $serverOs = @(& $docker.Source version --format "{{.Server.Os}}" 2>&1)
    if ($LASTEXITCODE -ne 0) {
        throw (
            "Windows container runtime required: the Docker daemon did not answer " +
            "($($serverOs -join ' ')). Start Docker in Windows-container mode."
        )
    }
    $observedOs = ([string]($serverOs | Select-Object -Last 1)).Trim()
    if ($observedOs -ne "windows") {
        throw (
            "Windows container runtime required: the Docker daemon is in " +
            "'$observedOs'-container mode. Switch to Windows containers " +
            "(Docker Desktop: 'Switch to Windows containers'; " +
            "GitHub-hosted windows-2022 defaults to Windows containers)."
        )
    }
    return $docker.Source
}

function Invoke-ContainerSmoke {
    param(
        [Parameter(Mandatory = $true)]
        [string]$DockerPath,

        [Parameter(Mandatory = $true)]
        [string]$Image,

        [Parameter(Mandatory = $true)]
        [string]$SourceCohort,

        [Parameter(Mandatory = $true)]
        [string]$SourceManifest,

        [Parameter(Mandatory = $true)]
        [string]$OutputDir,

        [Parameter(Mandatory = $true)]
        [string]$PackageName,

        [Parameter(Mandatory = $true)]
        [int]$MaximumMinutes
    )

    $resolvedCohort = (Resolve-Path $SourceCohort).Path
    $resolvedManifest = (Resolve-Path $SourceManifest).Path
    New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
    $resolvedEvidence = (Resolve-Path $OutputDir).Path
    $containerManifest = Join-Path $resolvedEvidence "source-manifest.json"
    Copy-Item -LiteralPath $resolvedManifest -Destination $containerManifest -Force

    $nonce = [Guid]::NewGuid().ToString("N")
    $containerName = "cadrumo-scoop-$nonce"
    # ltsc2022 process isolation matches the Windows Server 2022 host kernel, so no
    # Hyper-V isolation (unavailable on GitHub-hosted runners) is needed. The repo and
    # cohort mounts are read-only sources; only the evidence mount is writable.
    $dockerArguments = @(
        "run", "--rm", "--name", $containerName, "--isolation=process",
        "-v", "${RepoRoot}:C:\repo:ro",
        "-v", "${resolvedCohort}:C:\cohort:ro",
        "-v", "${resolvedEvidence}:C:\evidence",
        "--workdir", "C:\repo",
        $Image,
        "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
        "-File", "C:\repo\dev\packaging\smoke_scoop.ps1",
        "-Mode", "Host", "-InsideContainer", "-BootstrapScoop",
        "-CohortDir", "C:\cohort",
        "-ManifestPath", "C:\evidence\source-manifest.json",
        "-EvidenceDir", "C:\evidence",
        "-AppName", $PackageName,
        "-OrchestrationNonce", $nonce
    )

    $process = Start-Process `
        -FilePath $DockerPath `
        -ArgumentList $dockerArguments `
        -PassThru `
        -NoNewWindow
    if (-not $process.WaitForExit($MaximumMinutes * 60 * 1000)) {
        & $DockerPath rm -f $containerName | Out-Null
        try { $process.Kill() } catch { }
        throw "Windows container Scoop smoke exceeded $MaximumMinutes minutes"
    }
    if ($process.ExitCode -ne 0) {
        $failurePath = Join-Path $resolvedEvidence "scoop-failure.json"
        if (Test-Path -LiteralPath $failurePath -PathType Leaf) {
            throw (Get-Content -LiteralPath $failurePath -Raw)
        }
        throw "Windows container exited with code $($process.ExitCode) without Scoop evidence"
    }

    $evidencePath = Join-Path $resolvedEvidence "scoop-evidence.json"
    if (-not (Test-Path -LiteralPath $evidencePath -PathType Leaf)) {
        $failurePath = Join-Path $resolvedEvidence "scoop-failure.json"
        if (Test-Path -LiteralPath $failurePath -PathType Leaf) {
            throw (Get-Content -LiteralPath $failurePath -Raw)
        }
        throw "Windows container exited without Scoop evidence"
    }
    $evidence = Get-Content -LiteralPath $evidencePath -Raw | ConvertFrom-Json
    $expectedManifestHash = (
        Get-FileHash -LiteralPath $resolvedManifest -Algorithm SHA256
    ).Hash.ToLowerInvariant()
    if (
        $evidence.status -ne "passed" -or
        $evidence.mode -ne "Container" -or
        $evidence.orchestration_nonce -ne $nonce -or
        $evidence.source_manifest_sha256 -ne $expectedManifestHash -or
        $evidence.container_identity_verified -ne $true -or
        -not ([string]$evidence.runtime_identity).EndsWith(
            "\ContainerAdministrator",
            [System.StringComparison]::OrdinalIgnoreCase
        )
    ) {
        throw "Windows container evidence identity or source binding is invalid"
    }
}

New-Item -ItemType Directory -Force -Path $EvidenceDir | Out-Null
$resolvedTopLevelEvidence = (Resolve-Path $EvidenceDir).Path
foreach ($resultName in ("scoop-evidence.json", "scoop-failure.json")) {
    $resultPath = Join-Path $resolvedTopLevelEvidence $resultName
    if (Test-Path -LiteralPath $resultPath -PathType Leaf) {
        Remove-Item -LiteralPath $resultPath -Force
    }
}
try {
    $executionIdentity = Get-ExecutionIdentity `
        -ContainerChild ([bool]$InsideContainer) `
        -Nonce $OrchestrationNonce
    if ($Mode -eq "Container") {
        $dockerPath = Assert-WindowsContainerRuntime
        Invoke-ContainerSmoke `
            -DockerPath $dockerPath `
            -Image $ContainerImage `
            -SourceCohort $CohortDir `
            -SourceManifest $ManifestPath `
            -OutputDir $EvidenceDir `
            -PackageName $AppName `
            -MaximumMinutes $TimeoutMinutes
    }
    else {
        Install-ScoopIfRequested `
            -Requested ([bool]$BootstrapScoop) `
            -InstallerDir $EvidenceDir `
            -Elevated ([bool]$InsideContainer)
        Invoke-HostSmoke `
            -SourceCohort $CohortDir `
            -SourceManifest $ManifestPath `
            -OutputDir $EvidenceDir `
            -PackageName $AppName `
            -ExecutionIdentity $executionIdentity
    }
}
catch {
    $failure = [ordered]@{
        schema = "cadrumo.packaging.scoop-smoke.v2"
        status = "failed"
        mode = if ($InsideContainer) { "Container" } else { $Mode }
        completed_at = [DateTimeOffset]::UtcNow.ToString("O")
        error = $_.Exception.Message
        detail = $_ | Out-String
    }
    $failure |
        ConvertTo-Json -Depth 10 |
        Set-Content -LiteralPath (Join-Path $EvidenceDir "scoop-failure.json") -Encoding UTF8
    throw
}
