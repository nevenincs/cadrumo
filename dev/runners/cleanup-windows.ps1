# runner disk-hygiene hook - Windows self-hosted runner.
#
# Wired via ACTIONS_RUNNER_HOOK_JOB_COMPLETED in the runner root .env, so it
# fires after EVERY job (success or failure). It MUST stay fast (<30s typical)
# and MUST always exit 0 - a cleanup failure must never redden a green build.
#
# What it does, in order: purge stale _work/_temp entries; prune per-run lane
# roots (cadrumo-homebrew* / cadrumo-scoop* / cadrumo-claude-* / oracle-emit-work) older than 24h in
# RUNNER_TEMP and the checkout var/ tree (evidence dirs exempt); bound the uv /
# pip / npm speed caches; guarded dangling-only docker hygiene against the host
# daemon (the two Linux runner containers live here); one audit summary line.
#
# It NEVER touches: tracked files in any checkout, the runner's own binaries or
# credentials (.runner / .credentials), the reused checkout's .venv, named
# docker volumes (cadrumo-runner-state*), or real financial data.

$ErrorActionPreference = 'Continue'
$ProgressPreference = 'SilentlyContinue'

# --- constants -------------------------------------------------------------
$LaneGlobs      = @('cadrumo-homebrew*', 'cadrumo-scoop*', 'cadrumo-claude-*', 'oracle-emit-work*')
$LaneMaxAgeHrs  = 24
$EvidenceExempt = 'distribution-install-readiness'   # keep <7d evidence rows
$EvidenceKeepHrs = 24 * 7
# Windows uv cache is shared by operator dev work + the runner, and the do-once
# redesign leans on it staying warm, so it is capped higher than the
# runner-only container/macOS caches (which stay at 5GB).
$UvCapGB        = 15
$PipCapGB       = 3
$NpmCapGB       = 3
$HeavySweepThrottleHrs = 6          # throttle the expensive size-capped sweeps
$LogMaxBytes    = 2MB

# --- path derivation (robust to being called outside a job) ----------------
$WorkRoot = $null
if ($env:RUNNER_TEMP -and (Test-Path $env:RUNNER_TEMP)) {
    $WorkRoot = Split-Path $env:RUNNER_TEMP -Parent          # _work
} elseif ($env:RUNNER_WORKSPACE) {
    $WorkRoot = Split-Path (Split-Path $env:RUNNER_WORKSPACE -Parent) -Parent
}
if (-not $WorkRoot) {
    # script lives at <root>\_work\cadrumo\cadrumo\dev\runners or is copied to
    # <root>; fall back to the conventional Windows runner work root.
    $WorkRoot = 'C:\actions-runner\_work'
}
$LogFile   = Join-Path $WorkRoot 'runner-hygiene.log'
$StateDir  = Join-Path $WorkRoot '.hygiene'
$null = New-Item -ItemType Directory -Force -Path $StateDir -ErrorAction SilentlyContinue

# --- helpers ---------------------------------------------------------------
$script:Freed = 0L
$script:Notes = New-Object System.Collections.Generic.List[string]

function Get-DirBytes([string]$Path) {
    if (-not (Test-Path $Path)) { return 0L }
    try {
        $sum = (Get-ChildItem $Path -Recurse -Force -File -ErrorAction SilentlyContinue |
                Measure-Object Length -Sum).Sum
        if ($null -eq $sum) { 0L } else { [long]$sum }
    } catch { 0L }
}

function Remove-Path([string]$Path) {
    if (-not (Test-Path $Path)) { return }
    $bytes = Get-DirBytes $Path
    try {
        Remove-Item $Path -Recurse -Force -ErrorAction Stop
        $script:Freed += $bytes
    } catch {
        # Remove-Item chokes on >260-char paths, which the packaging-smoke
        # scratch nests well past (observed 312 chars). robocopy mirrors an
        # empty dir over the target natively beyond MAX_PATH, clearing the tree
        # so the next checkout's clean step does not fail and wipe the repo.
        try {
            $empty = Join-Path $env:TEMP ("cadrumo-empty-" + [Guid]::NewGuid().ToString('N'))
            $null = New-Item -ItemType Directory -Force -Path $empty -ErrorAction Stop
            $null = robocopy $empty $Path /MIR /NFL /NDL /NJH /NJS /NC /NS /NP
            Remove-Item $Path -Recurse -Force -ErrorAction SilentlyContinue
            Remove-Item $empty -Recurse -Force -ErrorAction SilentlyContinue
            if (Test-Path $Path) {
                $script:Notes.Add("skip-locked:$([IO.Path]::GetFileName($Path))")
            } else {
                $script:Freed += $bytes
            }
        } catch {
            # locked / in-use by a concurrent job: leave it, log, never fail.
            $script:Notes.Add("skip-locked:$([IO.Path]::GetFileName($Path))")
        }
    }
}

function Should-RunHeavy([string]$Tag) {
    $marker = Join-Path $StateDir "$Tag.stamp"
    if (Test-Path $marker) {
        $age = (Get-Date) - (Get-Item $marker).LastWriteTime
        if ($age.TotalHours -lt $HeavySweepThrottleHrs) { return $false }
    }
    Set-Content -Path $marker -Value (Get-Date -Format o) -ErrorAction SilentlyContinue
    return $true
}

# Purge immediate children of $Root matching $Globs whose top-level LastWriteTime
# is older than $MaxAgeHrs. Age check is a cheap stat - no recursion until removal.
function Purge-StaleDirs([string]$Root, [string[]]$Globs, [int]$MaxAgeHrs, [string]$ExemptName = $null, [int]$ExemptKeepHrs = 0) {
    if (-not (Test-Path $Root)) { return }
    $cutoff = (Get-Date).AddHours(-$MaxAgeHrs)
    foreach ($g in $Globs) {
        Get-ChildItem $Root -Directory -Force -Filter $g -ErrorAction SilentlyContinue | ForEach-Object {
            if ($ExemptName -and $_.Name -eq $ExemptName) {
                $keepCut = (Get-Date).AddHours(-$ExemptKeepHrs)
                if ($_.LastWriteTime -ge $keepCut) { return }
            }
            if ($_.LastWriteTime -lt $cutoff) { Remove-Path $_.FullName }
        }
    }
}

# Bound a cache dir to $CapGB by evicting oldest immediate children until under.
# Granular at the child level (uv/pip organise per-package dirs) so a miss is
# just a re-download, never corruption.
function Cap-Cache([string]$Path, [int]$CapGB, [string]$Tag) {
    if (-not (Test-Path $Path)) { return }
    if (-not (Should-RunHeavy $Tag)) { return }
    $cap = [long]$CapGB * 1GB
    $children = Get-ChildItem $Path -Force -ErrorAction SilentlyContinue |
                Sort-Object LastWriteTime   # oldest first
    $total = 0L
    $sizes = @{}
    foreach ($c in $children) { $b = Get-DirBytes $c.FullName; $sizes[$c.FullName] = $b; $total += $b }
    if ($total -le $cap) { return }
    foreach ($c in $children) {
        if ($total -le $cap) { break }
        Remove-Path $c.FullName
        $total -= $sizes[$c.FullName]
    }
    $script:Notes.Add("cap:$Tag")
}

# --- (a) stale _work/_temp beyond the current job --------------------------
# The runner cleans the current job's temp; crashed jobs strand dirs here.
$temp = if ($env:RUNNER_TEMP) { $env:RUNNER_TEMP } else { Join-Path $WorkRoot '_temp' }
if (Test-Path $temp) {
    $cutoff = (Get-Date).AddHours(-$LaneMaxAgeHrs)
    Get-ChildItem $temp -Force -ErrorAction SilentlyContinue |
        Where-Object { $_.LastWriteTime -lt $cutoff } |
        ForEach-Object { Remove-Path $_.FullName }
}

# --- (b) per-run lane roots older than 24h ---------------------------------
Purge-StaleDirs $WorkRoot $LaneGlobs $LaneMaxAgeHrs
Purge-StaleDirs $temp     $LaneGlobs $LaneMaxAgeHrs
# lane roots + var/ residue inside the reused checkout (var/ is gitignored)
Get-ChildItem $WorkRoot -Directory -Force -ErrorAction SilentlyContinue | ForEach-Object {
    $var = Join-Path $_.FullName 'cadrumo\var'
    if (Test-Path $var) {
        Purge-StaleDirs $var $LaneGlobs $LaneMaxAgeHrs
        # release-cohort staging + oracle work older than 24h (evidence exempt <7d)
        Purge-StaleDirs $var @('release-cohort*', 'oracle-emit-work*', '*.tar.gz') $LaneMaxAgeHrs $EvidenceExempt $EvidenceKeepHrs
    }
}

# --- (c) bound the persistent speed caches ---------------------------------
# uv: native prune first (fast, removes unreachable), then size cap (throttled).
$uv = Get-Command uv -ErrorAction SilentlyContinue
if ($uv) { try { & uv cache prune 2>&1 | Out-Null } catch {} }
$uvCache = if ($env:UV_CACHE_DIR) { $env:UV_CACHE_DIR } else { Join-Path $env:LOCALAPPDATA 'uv\cache' }
Cap-Cache $uvCache $UvCapGB 'uv'
Cap-Cache (Join-Path $env:LOCALAPPDATA 'pip\cache') $PipCapGB 'pip'
Cap-Cache (Join-Path $env:APPDATA 'npm-cache') $NpmCapGB 'npm'

# --- (d) guarded, dangling-only docker hygiene against the host daemon ------
# The two Linux runner containers run on this host. Prune only removes what is
# unreferenced: named volumes (cadrumo-runner-state*) and running containers
# are never touched. Throttled + guarded so it stays fast and optional.
$docker = Get-Command docker -ErrorAction SilentlyContinue
if ($docker -and (Should-RunHeavy 'docker')) {
    try {
        $ping = & docker info --format '{{.ServerVersion}}' 2>$null
        if ($LASTEXITCODE -eq 0 -and $ping) {
            & docker container prune -f 2>&1 | Out-Null           # stopped only
            & docker image prune -f 2>&1 | Out-Null               # dangling only
            & docker volume prune -f 2>&1 | Out-Null              # unreferenced only
            & docker builder prune -f --keep-storage '5GB' 2>&1 | Out-Null
            $script:Notes.Add('docker')
        }
    } catch {}
}

# --- (f) audit summary + log rotation --------------------------------------
try {
    if ((Test-Path $LogFile) -and ((Get-Item $LogFile).Length -gt $LogMaxBytes)) {
        Move-Item $LogFile "$LogFile.1" -Force -ErrorAction SilentlyContinue
    }
    $freedMB = [math]::Round($script:Freed / 1MB, 1)
    $notes = if ($script:Notes.Count) { ($script:Notes -join ',') } else { 'none' }
    # PS 5.1-safe fallbacks (the runner may invoke .ps1 hooks under Windows PowerShell).
    $job = if ($env:GITHUB_JOB) { $env:GITHUB_JOB } else { '-' }
    $run = if ($env:GITHUB_RUN_ID) { $env:GITHUB_RUN_ID } else { '-' }
    $line = "{0} job={1} run={2} freed={3}MB pruned={4}" -f `
        (Get-Date -Format o), $job, $run, $freedMB, $notes
    Add-Content -Path $LogFile -Value $line -ErrorAction SilentlyContinue
} catch {}

exit 0
