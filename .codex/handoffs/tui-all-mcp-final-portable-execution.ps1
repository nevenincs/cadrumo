param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('Collect', 'Serial', 'Parallel')]
    [string]$Batch
)

# Prepared command only. Root releases execution after fresh canonical publication.
$ErrorActionPreference = 'Stop'
# Retain failed native-command exit codes so post-run hash bookends still execute.
$PSNativeCommandUseErrorActionPreference = $false
$WorkspaceRoot = 'Y:/code/cadrumo-worktrees/tui-all-mcp'
Set-Location -LiteralPath $WorkspaceRoot
$Plan = Get-Content -LiteralPath '.codex/handoffs/tui-all-mcp-final-portable-execution.json' -Raw | ConvertFrom-Json
$Selection = $Plan.batches.$Batch
$SelectedPaths = @($Selection.paths)
foreach ($SelectedPath in $SelectedPaths) {
    if (-not (Test-Path -LiteralPath $SelectedPath -PathType Leaf)) {
        throw "Selected cohort module missing: $SelectedPath"
    }
}

$env:CADRUMO_AUTHORITY_ROOT = (Resolve-Path -LiteralPath '.authority').Path
$env:CADRUMO_PLAYWRIGHT_BROWSERS_DIR = (Resolve-Path -LiteralPath 'var/storage/components/playwright').Path
$Stamp = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffZ')
$Prefix = ".logs/tui-all-mcp-final-$($Batch.ToLower())-$Stamp"
$Before = "$Prefix-before.json"
$After = "$Prefix-after.json"
$Comparison = "$Prefix-input-stability.json"
$OutputLog = "$Prefix.txt"
$Bookend = '.codex/handoffs/tui-all-mcp-final-source-bookends.py'
$Python = '.venv/Scripts/python.exe'

$VerificationHead = & git rev-parse HEAD
if ($LASTEXITCODE -ne 0) { throw "Read-only HEAD observation failed" }
& $Python $Bookend capture --output $Before --head $VerificationHead
if ($LASTEXITCODE -ne 0) { throw 'Pre-execution source bookend failed' }

$PytestArguments = @('run', '--no-sync', 'pytest', "-n$($Selection.workers)", '-m', $Plan.marker_expression)
if ($Batch -eq 'Collect') {
    $PytestArguments += @('--collect-only', '-q')
} else {
    $PytestArguments += @('-v')
}
$PytestArguments += $SelectedPaths
Write-Output "Executing $Batch cohort; exact output log $OutputLog"
& uv @PytestArguments *> $OutputLog
$TestExitCode = $LASTEXITCODE

$VerificationHead = & git rev-parse HEAD
if ($LASTEXITCODE -ne 0) { throw "Read-only HEAD observation failed" }
& $Python $Bookend capture --output $After --head $VerificationHead
if ($LASTEXITCODE -ne 0) { throw 'Post-execution source bookend failed' }
& $Python $Bookend compare --before $Before --after $After --output $Comparison
$StabilityExitCode = $LASTEXITCODE

Get-Content -LiteralPath $OutputLog -Tail 16
Write-Output "Test exit $TestExitCode; input stability exit $StabilityExitCode; comparison $Comparison"
if ($TestExitCode -ne 0) { exit $TestExitCode }
exit $StabilityExitCode
