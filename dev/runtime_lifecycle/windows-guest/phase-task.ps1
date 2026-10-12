param([Parameter(Mandatory)][string]$Request,[Parameter(Mandatory)][guid]$ExpectedUuid,[Parameter(Mandatory)][ValidatePattern('^S-1-5-21-[0-9-]+$')][string]$ExpectedSid)
$ErrorActionPreference='Stop';$ProgressPreference='SilentlyContinue'
$absoluteRequest=[IO.Path]::GetFullPath($Request)
if($absoluteRequest -notmatch '^C:\\acceptance\\runs\\[a-fA-F0-9]{32}\\request\.json$'){throw 'request_path_invalid'}
$exitCode=1;$phase='request-read';$directory=Split-Path $absoluteRequest
try {
 $settings=Get-Content -LiteralPath $Request -Raw|ConvertFrom-Json
 if($settings.cohort -notin 'P1','P2' -or $settings.scope -notin 'user','machine' -or $settings.phase -notin 'precommit-rollback','hold','login','scope-conflict','scope-verify','gui-stop','gui-user','gui-restore','upgrade-rollback','machine-upgrade','cleanup'){throw 'request_contract_invalid'}
 if($settings.phase -in 'gui-stop','gui-user','gui-restore' -and $settings.scope -ne 'machine'){throw 'machine_gui_phase_scope_invalid'}
 if($settings.uuid -ne $ExpectedUuid.ToString() -or $settings.sid -ne $ExpectedSid){throw 'request_guest_binding_invalid'}
 if((Get-CimInstance Win32_ComputerSystemProduct).UUID -ne $settings.uuid){throw 'wrong_guest'}
 $phase=$settings.phase
 $root='C:\acceptance';$cohort="$root\$($settings.cohort)";$directory=Split-Path $Request
 $python="$cohort\app\python.exe";$owner="$cohort\owners"
  $code="import sys; sys.path.insert(0, r'$owner'); from dev.runtime_lifecycle.installed import main; main()"
  $campaignState=if($phase -eq 'precommit-rollback'){"$directory\precommit-rollback.json"}else{"$root\campaigns\$($settings.scope).json"}
  $arguments=@('--plan',"$cohort\intents\maintenance-$($settings.scope).json",'--runner',"$cohort\services\cadrumo-msi-maintenance.exe",'--installed-vm-id',$settings.uuid,'--installed-account-sid',$settings.sid,'--installed-guest-kind','qemu','--phase',$phase,'--campaign-state',$campaignState)
  if($phase -in 'scope-conflict','scope-verify'){$opposite=if($settings.scope -eq 'user'){'machine'}else{'user'};$arguments+=@('--conflicting-plan',"$cohort\intents\maintenance-$opposite.json")}
  if($settings.successor){$arguments+=@('--successor-plan',"$root\P2\intents\maintenance-$($settings.scope).json",'--successor-runner',"$root\P2\services\cadrumo-msi-maintenance.exe")}
  try {$ErrorActionPreference='Continue'; & $python -I -B -c $code @arguments 1>"$directory\stdout.txt" 2>"$directory\stderr.txt"} finally {$ErrorActionPreference='Stop'}
 if($null -eq $LASTEXITCODE){throw 'native_exit_status_missing'}
 $exitCode=$LASTEXITCODE
} catch {
 @{phase=$phase;code=$_.FullyQualifiedErrorId;type=$_.Exception.GetType().FullName}|ConvertTo-Json -Compress|Set-Content -LiteralPath "$directory\transport-error.json"
} finally {
 @{phase=$phase;state='completed';exitCode=$exitCode;completedAtUtc=[DateTime]::UtcNow}|ConvertTo-Json -Compress|Set-Content -LiteralPath "$directory\status.json.tmp"
 Move-Item -LiteralPath "$directory\status.json.tmp" -Destination "$directory\status.json"
}
exit $exitCode

