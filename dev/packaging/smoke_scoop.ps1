[CmdletBinding()]
param(
    [ValidateSet("Sandbox", "Host")]
    [string]$Mode = "Sandbox",

    [Parameter(Mandatory = $true)]
    [string]$CohortDir,

    [Parameter(Mandatory = $true)]
    [string]$ManifestPath,

    [Parameter(Mandatory = $true)]
    [string]$EvidenceDir,

    [ValidatePattern("^[A-Za-z0-9][A-Za-z0-9._-]*$")]
    [string]$AppName = "cadrumo-s19-stage",

    [ValidateRange(1, 240)]
    [int]$TimeoutMinutes = 60,

    [switch]$BootstrapScoop,

    [switch]$InsideSandbox,

    [string]$OrchestrationNonce,

    [switch]$ShutdownWhenDone
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if ($BootstrapScoop -and -not $InsideSandbox) {
    throw "Scoop bootstrap is restricted to the disposable Windows Sandbox child"
}
if ($ShutdownWhenDone -and -not $InsideSandbox) {
    throw "automatic shutdown is restricted to the disposable Windows Sandbox child"
}
if ($InsideSandbox -and $Mode -ne "Host") {
    throw "the Windows Sandbox child must execute the Host smoke implementation"
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

    if ($OutputPath) {
        $output = @(& $FilePath @ArgumentList 2>&1)
        $exitCode = $LASTEXITCODE
        $output | Set-Content -LiteralPath $OutputPath -Encoding UTF8
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
        [string]$InstallerDir
    )

    if (-not $Requested) {
        if (-not (Get-Command scoop -ErrorAction SilentlyContinue)) {
            throw "scoop is not installed; use -BootstrapScoop only in a disposable Windows environment"
        }
        return
    }

    if (-not (Get-Command scoop -ErrorAction SilentlyContinue)) {
        Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser -Force
        $installer = Join-Path $InstallerDir "install-scoop.ps1"
        Invoke-WebRequest -Uri "https://get.scoop.sh" -OutFile $installer -UseBasicParsing
        & $installer
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
        [bool]$SandboxChild,

        [string]$Nonce
    )

    $runtimeIdentity = [Security.Principal.WindowsIdentity]::GetCurrent().Name
    $observedSandbox = $runtimeIdentity.EndsWith(
        "\WDAGUtilityAccount",
        [System.StringComparison]::OrdinalIgnoreCase
    )
    if ($SandboxChild) {
        if (-not $Nonce) {
            throw "sandbox child execution requires an orchestration nonce"
        }
        if (-not $observedSandbox) {
            throw "sandbox child identity was not observed: $runtimeIdentity"
        }
    }
    elseif ($Nonce) {
        throw "host execution must not accept a sandbox orchestration nonce"
    }
    return @{
        mode = if ($SandboxChild) { "Sandbox" } else { "Host" }
        orchestration_nonce = if ($SandboxChild) { $Nonce } else { $null }
        runtime_identity = $runtimeIdentity
        sandbox_identity_verified = $observedSandbox
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
        [string]$McpCommand,

        [Parameter(Mandatory = $true)]
        [string]$OutputDir
    )

    $python = (Resolve-Path (Join-Path $Prefix "venv\Scripts\python.exe")).Path
    $taxEvidence = Join-Path $OutputDir "tax-evidence.json"
    $mcpEvidence = Join-Path $OutputDir "mcp-evidence.json"
    $taxState = Join-Path $OutputDir "tax-state"
    $taxWork = Join-Path $OutputDir "tax-work"
    $mcpState = Join-Path $OutputDir "mcp-state"
    $mcpWork = Join-Path $OutputDir "mcp-work"

    Push-Location $RepoRoot
    try {
        Invoke-Native -FilePath $python -ArgumentList @(
            "-m", "dev.packaging.installed_tax_oracle",
            "--cli", $AeatCommand,
            "--storage-root", $taxState,
            "--work-dir", $taxWork,
            "--output", $taxEvidence
        ) -OutputPath (Join-Path $OutputDir "tax-oracle.log")
        Invoke-Native -FilePath $python -ArgumentList @(
            "-m", "dev.packaging.installed_mcp_oracle",
            "--server", $McpCommand,
            "--storage-root", $mcpState,
            "--work-dir", $mcpWork,
            "--output", $mcpEvidence
        ) -OutputPath (Join-Path $OutputDir "mcp-oracle.log")
    }
    finally {
        Pop-Location
    }

    return @{
        tax_evidence = (Resolve-Path $taxEvidence).Path
        mcp_evidence = (Resolve-Path $mcpEvidence).Path
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
        Get-ChildItem -LiteralPath $persistEntriesRoot -Directory |
            ForEach-Object { $_.Name }
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
        $mcp = Get-ScoopCommandPath -CommandName "cadrumo-mcp" -ScoopRoot $scoopRoot

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
        $mcp = Get-ScoopCommandPath -CommandName "cadrumo-mcp" -ScoopRoot $scoopRoot
        $oracleEvidence = Invoke-InstalledOracle `
            -Prefix $prefix `
            -AeatCommand $aeat `
            -McpCommand $mcp `
            -OutputDir $runEvidence

        $evidence = [ordered]@{
            schema = "cadrumo.packaging.scoop-smoke.v1"
            status = "passed"
            mode = $ExecutionIdentity.mode
            orchestration_nonce = $ExecutionIdentity.orchestration_nonce
            runtime_identity = $ExecutionIdentity.runtime_identity
            sandbox_identity_verified = $ExecutionIdentity.sandbox_identity_verified
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
            mcp_command = $mcp
            persisted_marker = $marker
            persisted_marker_sha256 = $reinstalledMarkerHash
            update_preserved_persistence = $true
            uninstall_preserved_persistence = $true
            reinstall_preserved_persistence = $true
            tax_evidence = $oracleEvidence.tax_evidence
            mcp_evidence = $oracleEvidence.mcp_evidence
        }
    }
    finally {
        $cleanupErrors = [System.Collections.Generic.List[string]]::new()
        $newScoopApps = @()
        if ($installed -or (Test-Path -LiteralPath $appRoot)) {
            & scoop uninstall $PackageName --purge
            if ($LASTEXITCODE -ne 0) {
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
            & scoop uninstall $newScoopApp --purge
            if ($LASTEXITCODE -ne 0) {
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
            Get-ChildItem -LiteralPath $persistEntriesRoot -Directory |
                Where-Object {
                    $preexistingScoopPersistEntries -notcontains $_.Name
                } |
                ForEach-Object { $_.Name }
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

function Invoke-SandboxSmoke {
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
        [int]$MaximumMinutes
    )

    $feature = Get-WindowsOptionalFeature `
        -Online `
        -FeatureName Containers-DisposableClientVM
    if ($feature.State -ne "Enabled") {
        throw "Windows Sandbox feature Containers-DisposableClientVM is not enabled"
    }
    $sandbox = Get-Command WindowsSandbox.exe -ErrorAction SilentlyContinue
    if (-not $sandbox) {
        throw "WindowsSandbox.exe is unavailable"
    }

    $resolvedCohort = (Resolve-Path $SourceCohort).Path
    $resolvedManifest = (Resolve-Path $SourceManifest).Path
    New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
    $resolvedEvidence = (Resolve-Path $OutputDir).Path
    $sandboxManifest = Join-Path $resolvedEvidence "source-manifest.json"
    Copy-Item -LiteralPath $resolvedManifest -Destination $sandboxManifest -Force

    $escapedRepo = [Security.SecurityElement]::Escape($RepoRoot)
    $escapedCohort = [Security.SecurityElement]::Escape($resolvedCohort)
    $escapedEvidence = [Security.SecurityElement]::Escape($resolvedEvidence)
    $nonce = [Guid]::NewGuid().ToString("N")
    $command = (
        "powershell.exe -NoProfile -ExecutionPolicy Bypass " +
        "-File C:\repo\dev\packaging\smoke_scoop.ps1 " +
        "-Mode Host -CohortDir C:\cohort " +
        "-ManifestPath C:\evidence\source-manifest.json " +
        "-EvidenceDir C:\evidence -AppName $PackageName " +
        "-BootstrapScoop -InsideSandbox -OrchestrationNonce $nonce -ShutdownWhenDone"
    )
    $escapedCommand = [Security.SecurityElement]::Escape($command)
    $configuration = @"
<Configuration>
  <MappedFolders>
    <MappedFolder>
      <HostFolder>$escapedRepo</HostFolder>
      <SandboxFolder>C:\repo</SandboxFolder>
      <ReadOnly>true</ReadOnly>
    </MappedFolder>
    <MappedFolder>
      <HostFolder>$escapedCohort</HostFolder>
      <SandboxFolder>C:\cohort</SandboxFolder>
      <ReadOnly>true</ReadOnly>
    </MappedFolder>
    <MappedFolder>
      <HostFolder>$escapedEvidence</HostFolder>
      <SandboxFolder>C:\evidence</SandboxFolder>
      <ReadOnly>false</ReadOnly>
    </MappedFolder>
  </MappedFolders>
  <LogonCommand>
    <Command>$escapedCommand</Command>
  </LogonCommand>
</Configuration>
"@
    $configurationPath = Join-Path $resolvedEvidence "cadrumo-scoop-smoke.wsb"
    $configuration | Set-Content -LiteralPath $configurationPath -Encoding UTF8

    $process = Start-Process `
        -FilePath $sandbox.Source `
        -ArgumentList $configurationPath `
        -PassThru `
        -WindowStyle Hidden
    if (-not $process.WaitForExit($MaximumMinutes * 60 * 1000)) {
        $process.Kill()
        throw "Windows Sandbox Scoop smoke exceeded $MaximumMinutes minutes"
    }
    $evidencePath = Join-Path $resolvedEvidence "scoop-evidence.json"
    if (-not (Test-Path -LiteralPath $evidencePath -PathType Leaf)) {
        $failurePath = Join-Path $resolvedEvidence "scoop-failure.json"
        if (Test-Path -LiteralPath $failurePath -PathType Leaf) {
            throw (Get-Content -LiteralPath $failurePath -Raw)
        }
        throw "Windows Sandbox exited without Scoop evidence"
    }
    $evidence = Get-Content -LiteralPath $evidencePath -Raw | ConvertFrom-Json
    $expectedManifestHash = (
        Get-FileHash -LiteralPath $resolvedManifest -Algorithm SHA256
    ).Hash.ToLowerInvariant()
    if (
        $evidence.status -ne "passed" -or
        $evidence.mode -ne "Sandbox" -or
        $evidence.orchestration_nonce -ne $nonce -or
        $evidence.source_manifest_sha256 -ne $expectedManifestHash -or
        $evidence.sandbox_identity_verified -ne $true -or
        -not ([string]$evidence.runtime_identity).EndsWith(
            "\WDAGUtilityAccount",
            [System.StringComparison]::OrdinalIgnoreCase
        )
    ) {
        throw "Windows Sandbox evidence identity or source binding is invalid"
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
        -SandboxChild ([bool]$InsideSandbox) `
        -Nonce $OrchestrationNonce
    if ($Mode -eq "Sandbox") {
        Invoke-SandboxSmoke `
            -SourceCohort $CohortDir `
            -SourceManifest $ManifestPath `
            -OutputDir $EvidenceDir `
            -PackageName $AppName `
            -MaximumMinutes $TimeoutMinutes
    }
    else {
        Install-ScoopIfRequested `
            -Requested ([bool]$BootstrapScoop) `
            -InstallerDir $EvidenceDir
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
        schema = "cadrumo.packaging.scoop-smoke.v1"
        status = "failed"
        mode = if ($InsideSandbox) { "Sandbox" } else { $Mode }
        completed_at = [DateTimeOffset]::UtcNow.ToString("O")
        error = $_.Exception.Message
        detail = $_ | Out-String
    }
    $failure |
        ConvertTo-Json -Depth 10 |
        Set-Content -LiteralPath (Join-Path $EvidenceDir "scoop-failure.json") -Encoding UTF8
    throw
}
finally {
    if ($ShutdownWhenDone) {
        shutdown.exe /s /t 0
    }
}
