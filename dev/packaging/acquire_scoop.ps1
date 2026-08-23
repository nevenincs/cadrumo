<#
.SYNOPSIS
    Reacquire Cadrumo through the PUBLIC Scoop bucket and repeat installed work.

.DESCRIPTION
    Post-publication reacquisition for post-release-distribution plan row P03.S16.
    Adds the published Scoop bucket, installs the app from it, verifies every
    installed cohort artifact digest against the promoted cohort, and repeats the
    grounded installed CLI tax-work oracle. Reuses the disposable
    Windows-container orchestration pattern of smoke_scoop.ps1 (-Mode Container
    launches a throwaway ltsc2022 container that bootstraps Scoop and runs the
    Host implementation). Refuses instructively when the public bucket does not
    yet carry the app (never a silent skip).

.NOTES
    Unlike smoke_scoop.ps1, this script installs from a PUBLIC bucket source
    (-BucketSource) rather than staging a local bucket; the cohort directory is
    used only to verify the installed digests, never to serve the artifacts.
#>
[CmdletBinding()]
param(
    [ValidateSet("Container", "Host")]
    [string]$Mode = "Container",

    [Parameter(Mandatory = $true)]
    [string]$CohortDir,

    [Parameter(Mandatory = $true)]
    [ValidatePattern("^[A-Za-z0-9][A-Za-z0-9._/:@+-]*$")]
    [string]$BucketSource,

    [Parameter(Mandatory = $true)]
    [string]$EvidenceDir,

    [ValidatePattern("^[A-Za-z0-9][A-Za-z0-9._-]*$")]
    [string]$AppName = "cadrumo",

    [ValidatePattern("^[A-Za-z0-9][A-Za-z0-9._-]*$")]
    [string]$BucketName = "cadrumo",

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
    throw "the Windows container child must execute the Host reacquisition implementation"
}

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path

function Invoke-Native {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $true)][string[]]$ArgumentList,
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

function Get-ScoopRoot {
    if ($env:SCOOP) { return [System.IO.Path]::GetFullPath($env:SCOOP) }
    return Join-Path ([Environment]::GetFolderPath("UserProfile")) "scoop"
}

function Install-ScoopIfRequested {
    param(
        [Parameter(Mandatory = $true)][bool]$Requested,
        [Parameter(Mandatory = $true)][string]$InstallerDir,
        [Parameter(Mandatory = $true)][bool]$Elevated
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
        if ($Elevated) { & $installer -RunAsAdmin } else { & $installer }
        if (-not $?) { throw "Scoop bootstrap failed" }
    }
    $scoopShims = Join-Path (Get-ScoopRoot) "shims"
    if (($env:PATH -split [System.IO.Path]::PathSeparator) -notcontains $scoopShims) {
        $env:PATH = "$scoopShims$([System.IO.Path]::PathSeparator)$env:PATH"
    }
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
        Invoke-Native -FilePath "scoop" -ArgumentList @("install", "git", "--no-update-scoop")
    }
}

function Get-ScoopCommandPath {
    param(
        [Parameter(Mandatory = $true)][string]$CommandName,
        [Parameter(Mandatory = $true)][string]$ScoopRoot
    )
    $resolved = @(& scoop which $CommandName)
    if ($LASTEXITCODE -ne 0 -or $resolved.Count -ne 1) {
        throw "scoop did not resolve exactly one installed target for ${CommandName}: $resolved"
    }
    $shim = (Resolve-Path (Join-Path $ScoopRoot "shims\${CommandName}.cmd")).Path
    return $shim
}

function Get-ExecutionIdentity {
    param(
        [Parameter(Mandatory = $true)][bool]$ContainerChild,
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

function Assert-InstalledCohortDigests {
    <#
        Prove every promoted cohort artifact present under the installed app
        directory matches the cohort's declared bytes. The manifest is read from
        python-cohort.json in the supplied cohort directory; a public bucket that
        serves drifted bytes fails here.
    #>
    param(
        [Parameter(Mandatory = $true)][string]$Prefix,
        [Parameter(Mandatory = $true)][string]$SourceCohort
    )
    $manifestPath = Join-Path $SourceCohort "python-cohort.json"
    $manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
    $expected = @{}
    foreach ($name in $manifest.sha256.PSObject.Properties.Name) {
        $filename = [string]$manifest.artifacts.$name
        $expected[$filename] = ([string]$manifest.sha256.$name).ToLowerInvariant()
    }
    $verified = 0
    foreach ($installed in Get-ChildItem -LiteralPath $Prefix -Recurse -File) {
        if ($expected.ContainsKey($installed.Name)) {
            $observed = (Get-FileHash -LiteralPath $installed.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
            if ($observed -ne $expected[$installed.Name]) {
                throw (
                    "public reacquisition digest mismatch: installed $($installed.Name) sha256 $observed " +
                    "does not match the promoted cohort $($expected[$installed.Name]); refusing"
                )
            }
            $verified += 1
        }
    }
    if ($verified -le 0) {
        throw (
            "public reacquisition verified no cohort artifacts under $Prefix against the promoted " +
            "cohort ($manifestPath); the installed app carries none of the expected wheels; refusing"
        )
    }
    return $verified
}

function Invoke-InstalledOracle {
    param(
        [Parameter(Mandatory = $true)][string]$SourceCohort,
        [Parameter(Mandatory = $true)][string]$Prefix,
        [Parameter(Mandatory = $true)][string]$AeatCommand,
        [Parameter(Mandatory = $true)][string]$OutputDir
    )
    $python = (Resolve-Path (Join-Path $Prefix "venv\Scripts\python.exe")).Path
    $taxEvidence = Join-Path $OutputDir "tax-evidence.json"
    $cohortManifest = (Resolve-Path (Join-Path $SourceCohort "python-cohort.json")).Path
    $cohort = Get-Content -LiteralPath $cohortManifest -Raw | ConvertFrom-Json
    $cohortManifestSha256 = (Get-FileHash -LiteralPath $cohortManifest -Algorithm SHA256).Hash.ToLowerInvariant()
    Push-Location $RepoRoot
    try {
        Invoke-Native -FilePath $python -ArgumentList @(
            "-m", "dev.packaging.installed_tax_oracle",
            "--cli", $AeatCommand,
            "--storage-root", (Join-Path $OutputDir "tax-state"),
            "--work-dir", (Join-Path $OutputDir "tax-work"),
            "--cohort-source-commit", $cohort.source_commit,
            "--cohort-manifest-sha256", $cohortManifestSha256,
            "--cohort-root-wheel-sha256", $cohort.sha256.cadrumo,
            "--output", $taxEvidence
        ) -OutputPath (Join-Path $OutputDir "tax-oracle.log")
    }
    finally {
        Pop-Location
    }
    $tax = Get-Content -LiteralPath $taxEvidence -Raw | ConvertFrom-Json
    if ($tax.target_value -ne "23000.00") {
        throw "installed Scoop oracle returned an unexpected tax value: cli=$($tax.target_value)"
    }
    return @{ tax_evidence = $taxEvidence }
}

function Invoke-HostAcquisition {
    param(
        [Parameter(Mandatory = $true)][string]$SourceCohort,
        [Parameter(Mandatory = $true)][string]$Source,
        [Parameter(Mandatory = $true)][string]$Bucket,
        [Parameter(Mandatory = $true)][string]$Package,
        [Parameter(Mandatory = $true)][string]$OutputDir,
        [Parameter(Mandatory = $true)][hashtable]$ExecutionIdentity
    )
    $resolvedCohort = (Resolve-Path $SourceCohort).Path
    Invoke-Native -FilePath "uv" -ArgumentList @(
        "run", "python", "-m", "dev.packaging.python_cohort", "verify", "--cohort-dir", $resolvedCohort
    )
    New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
    $resolvedEvidence = (Resolve-Path $OutputDir).Path
    $runId = [DateTimeOffset]::UtcNow.ToString("yyyyMMddTHHmmssfffZ")
    $runEvidence = Join-Path $resolvedEvidence "run-$runId"
    New-Item -ItemType Directory -Force -Path $runEvidence | Out-Null
    $scoopRoot = Get-ScoopRoot

    try {
        Invoke-Native -FilePath "scoop" -ArgumentList @("bucket", "add", $Bucket, $Source)
    }
    catch {
        throw (
            "public reacquisition unavailable: scoop bucket $Source does not serve $Package. " +
            "Next step: publish the public Scoop bucket and rerun. Detail: $($_.Exception.Message)"
        )
    }
    try {
        Invoke-Native -FilePath "scoop" -ArgumentList @(
            "install", "${Bucket}/${Package}", "--no-cache", "--no-update-scoop"
        )
    }
    catch {
        throw (
            "public reacquisition unavailable: scoop bucket ${Bucket} does not yet carry ${Package}. " +
            "Next step: publish the app manifest to the public bucket and rerun. Detail: $($_.Exception.Message)"
        )
    }

    $prefixOutput = @(& scoop prefix $Package)
    if ($LASTEXITCODE -ne 0 -or $prefixOutput.Count -ne 1) {
        throw "scoop did not return one installed prefix for $Package"
    }
    $prefix = (Resolve-Path ([string]$prefixOutput[0])).Path
    $aeat = Get-ScoopCommandPath -CommandName "aeat" -ScoopRoot $scoopRoot
    Invoke-Native -FilePath $aeat -ArgumentList @("--version")
    $verifiedDigests = Assert-InstalledCohortDigests -Prefix $prefix -SourceCohort $resolvedCohort
    $oracle = Invoke-InstalledOracle -SourceCohort $SourceCohort -Prefix $prefix -AeatCommand $aeat -OutputDir $runEvidence
    $manifest = Get-Content -LiteralPath (Join-Path $resolvedCohort "python-cohort.json") -Raw | ConvertFrom-Json
    $evidence = [ordered]@{
        schema = "cadrumo.packaging.acquire-scoop.v1"
        status = "passed"
        completed_at = [DateTimeOffset]::UtcNow.ToString("o")
        bucket = "${Bucket}/${Package}"
        platform = [System.Runtime.InteropServices.RuntimeInformation]::OSDescription
        cohort = @{
            source_commit = [string]$manifest.source_commit
            version = [string]$manifest.version
        }
        verified_artifact_digests = $verifiedDigests
        installed_prefix = $prefix
        installed_tax_oracle = (Get-Content -LiteralPath $oracle.tax_evidence -Raw | ConvertFrom-Json)
    }
    $evidence | ConvertTo-Json -Depth 20 |
        Set-Content -LiteralPath (Join-Path $resolvedEvidence "acquire-scoop-evidence.json") -Encoding UTF8
}

function Assert-WindowsContainerRuntime {
    $docker = Get-Command docker -ErrorAction SilentlyContinue
    if (-not $docker) {
        throw "Windows container runtime required: 'docker' was not found on PATH. Run on a Windows-container host."
    }
    $serverOs = @(& $docker.Source version --format "{{.Server.Os}}" 2>&1)
    if ($LASTEXITCODE -ne 0) {
        throw "Windows container runtime required: the Docker daemon did not answer ($($serverOs -join ' '))."
    }
    $observedOs = ([string]($serverOs | Select-Object -Last 1)).Trim()
    if ($observedOs -ne "windows") {
        throw "Windows container runtime required: the Docker daemon is in '$observedOs'-container mode."
    }
    return $docker.Source
}

function Invoke-ContainerAcquisition {
    param(
        [Parameter(Mandatory = $true)][string]$DockerPath,
        [Parameter(Mandatory = $true)][string]$Image,
        [Parameter(Mandatory = $true)][string]$SourceCohort,
        [Parameter(Mandatory = $true)][string]$Source,
        [Parameter(Mandatory = $true)][string]$Bucket,
        [Parameter(Mandatory = $true)][string]$Package,
        [Parameter(Mandatory = $true)][string]$OutputDir,
        [Parameter(Mandatory = $true)][int]$MaximumMinutes
    )
    $resolvedCohort = (Resolve-Path $SourceCohort).Path
    Invoke-Native -FilePath "uv" -ArgumentList @(
        "run", "python", "-m", "dev.packaging.python_cohort", "verify", "--cohort-dir", $resolvedCohort
    )
    New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
    $resolvedEvidence = (Resolve-Path $OutputDir).Path
    $nonce = [Guid]::NewGuid().ToString("N")
    $containerName = "cadrumo-acquire-scoop-$nonce"
    $dockerArguments = @(
        "run", "--rm", "--name", $containerName, "--isolation=process",
        "-v", "${RepoRoot}:C:\repo:ro",
        "-v", "${resolvedCohort}:C:\cohort:ro",
        "-v", "${resolvedEvidence}:C:\evidence",
        "--workdir", "C:\repo",
        $Image,
        "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
        "-File", "C:\repo\dev\packaging\acquire_scoop.ps1",
        "-Mode", "Host", "-InsideContainer", "-BootstrapScoop",
        "-CohortDir", "C:\cohort",
        "-BucketSource", $Source,
        "-BucketName", $Bucket,
        "-EvidenceDir", "C:\evidence",
        "-AppName", $Package,
        "-OrchestrationNonce", $nonce
    )
    $process = Start-Process -FilePath $DockerPath -ArgumentList $dockerArguments -PassThru -NoNewWindow
    if (-not $process.WaitForExit($MaximumMinutes * 60 * 1000)) {
        & $DockerPath rm -f $containerName | Out-Null
        try { $process.Kill() } catch { }
        throw "Windows container Scoop reacquisition exceeded $MaximumMinutes minutes"
    }
    if ($process.ExitCode -ne 0) {
        throw "Windows container exited with code $($process.ExitCode) without Scoop reacquisition evidence"
    }
    $evidencePath = Join-Path $resolvedEvidence "acquire-scoop-evidence.json"
    if (-not (Test-Path -LiteralPath $evidencePath -PathType Leaf)) {
        throw "Windows container exited without Scoop reacquisition evidence"
    }
    $evidence = Get-Content -LiteralPath $evidencePath -Raw | ConvertFrom-Json
    if (
        $evidence.status -ne "passed" -or
        $evidence.mode -ne "Container" -or
        $evidence.orchestration_nonce -ne $nonce -or
        $evidence.container_identity_verified -ne $true -or
        -not ([string]$evidence.runtime_identity).EndsWith(
            "\ContainerAdministrator",
            [System.StringComparison]::OrdinalIgnoreCase
        )
    ) {
        throw "Windows container reacquisition evidence identity or nonce binding is invalid"
    }
}

New-Item -ItemType Directory -Force -Path $EvidenceDir | Out-Null
$resolvedTopLevelEvidence = (Resolve-Path $EvidenceDir).Path
foreach ($resultName in ("acquire-scoop-evidence.json", "acquire-scoop-failure.json")) {
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
        Invoke-ContainerAcquisition `
            -DockerPath $dockerPath `
            -Image $ContainerImage `
            -SourceCohort $CohortDir `
            -Source $BucketSource `
            -Bucket $BucketName `
            -Package $AppName `
            -OutputDir $EvidenceDir `
            -MaximumMinutes $TimeoutMinutes
    }
    else {
        Install-ScoopIfRequested `
            -Requested ([bool]$BootstrapScoop) `
            -InstallerDir $EvidenceDir `
            -Elevated ([bool]$InsideContainer)
        Invoke-HostAcquisition `
            -SourceCohort $CohortDir `
            -Source $BucketSource `
            -Bucket $BucketName `
            -Package $AppName `
            -OutputDir $EvidenceDir `
            -ExecutionIdentity $executionIdentity
    }
}
catch {
    $failure = [ordered]@{
        schema       = "cadrumo.packaging.acquire-scoop.v1"
        status       = "failed"
        mode         = if ($InsideContainer) { "Container" } else { $Mode }
        completed_at = [DateTimeOffset]::UtcNow.ToString("O")
        error        = $_.Exception.Message
    }
    $failure | ConvertTo-Json -Depth 10 |
        Set-Content -LiteralPath (Join-Path $EvidenceDir "acquire-scoop-failure.json") -Encoding UTF8
    throw
}
