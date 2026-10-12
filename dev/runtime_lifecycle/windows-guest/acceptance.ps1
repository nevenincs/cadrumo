param([Parameter(Mandatory)][AllowEmptyString()][string]$Config,
 [Parameter(Mandatory)][string]$Stage,[Parameter(Mandatory)][string]$Source,
 [Parameter(Mandatory)][string]$Output,[switch]$ValidateOnly)
$ErrorActionPreference='Stop'
$ProgressPreference='SilentlyContinue'
. "$PSScriptRoot/transport.ps1"

function Read-AcceptanceConfiguration {
 if(!$Config -or !(Test-Path -LiteralPath $Config -PathType Leaf)){throw 'installed_guest_configuration_required'}
 $settings=Get-Content -LiteralPath $Config -Raw|ConvertFrom-Json
 if($settings.schema -ne 1){throw 'installed_guest_configuration_schema_invalid'}
 foreach($name in 'uuid','sid','computer','account','container','volume','network','guestImage','rdpImage','tlsPin','passwordFile','fixtureRoot','baselineReceipt','baselineReceiptSha256','firmwareVarsSha256','firmwareMacSha256') {
  if($settings.$name -isnot [string] -or !$settings.$name){throw 'installed_guest_configuration_field_missing'}
 }
 $null=[guid]::Parse($settings.uuid)
 if($settings.sid -notmatch '^S-1-5-21-[0-9-]+$' -or $settings.port -isnot [long] -and $settings.port -isnot [int] -or $settings.port -lt 1 -or $settings.port -gt 65535){throw 'installed_guest_identity_invalid'}
 foreach($name in 'computer','account','container','volume','network') {
  if($settings.$name -notmatch '^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,100}$'){throw 'installed_guest_resource_name_invalid'}
 }
 foreach($name in 'tlsPin','baselineReceiptSha256','firmwareVarsSha256','firmwareMacSha256') {
  if($settings.$name -notmatch '^[a-fA-F0-9]{64}$'){throw 'installed_guest_digest_invalid'}
 }
 foreach($name in 'guestImage','rdpImage') {
  if($settings.$name -notmatch '^sha256:[a-fA-F0-9]{64}$'){throw 'installed_guest_image_pin_required'}
 }
 foreach($name in 'fixtureRoot','passwordFile','baselineReceipt') {
  $settings.$name=(Resolve-Path -LiteralPath $settings.$name -ErrorAction Stop).Path
  if((Get-Item -LiteralPath $settings.$name).Attributes -band [IO.FileAttributes]::ReparsePoint){throw 'installed_guest_reparse_refused'}
 }
 if((Get-FileHash -LiteralPath $settings.baselineReceipt -Algorithm SHA256).Hash -ne $settings.baselineReceiptSha256){throw 'installed_guest_baseline_digest_mismatch'}
 $baseline=Get-Content -LiteralPath $settings.baselineReceipt -Raw|ConvertFrom-Json
 if($baseline.uuid -ne $settings.uuid -or $baseline.volume -ne $settings.volume -or $baseline.snapshot -notmatch '^[a-zA-Z0-9_-]{1,32}$' -or $baseline.normalClock -ne $true -or $baseline.uacEnabled -ne $true -or $baseline.helpersAbsent -ne $true -or $baseline.productTransferred -ne $false -or $baseline.productInstalled -ne $false -or $baseline.guestFullyStopped -ne $true -or $baseline.tpmPresent -ne $false){throw 'installed_guest_clean_baseline_required'}
 $settings|Add-Member snapshot $baseline.snapshot
 $settings|Add-Member baselineDirectory (Split-Path $settings.baselineReceipt)
 foreach($pair in @(@('windows.vars','firmwareVarsSha256'),@('windows.mac','firmwareMacSha256'))) {
  $path=Join-Path $settings.baselineDirectory $pair[0]
  if((Get-Item -LiteralPath $path).Attributes -band [IO.FileAttributes]::ReparsePoint -or (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash -ne $settings.($pair[1])){throw 'installed_guest_firmware_digest_mismatch'}
 }
 foreach($cohort in 'P1','P2') {
  $record=$settings.$cohort
  if(!$record -or $record.sha256 -notmatch '^[a-fA-F0-9]{64}$' -or $record.version -notmatch '^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$'){throw 'installed_guest_two_cohorts_required'}
  $record.archive=(Resolve-Path -LiteralPath $record.archive).Path
  $record.receipt=(Resolve-Path -LiteralPath $record.receipt).Path
  if((Get-FileHash -LiteralPath $record.archive -Algorithm SHA256).Hash -ne $record.sha256){throw 'installed_guest_cohort_digest_mismatch'}
  $binding=Get-Content -LiteralPath $record.receipt -Raw|ConvertFrom-Json
  $boundPath=if([IO.Path]::IsPathRooted($binding.path)){[IO.Path]::GetFullPath($binding.path)}else{[IO.Path]::GetFullPath((Join-Path (Split-Path $record.receipt) $binding.path))}
  if($boundPath -ne $record.archive -or $binding.sha256 -ne $record.sha256 -or $binding.bytes -ne (Get-Item -LiteralPath $record.archive).Length){throw 'installed_guest_archive_receipt_mismatch'}
  Assert-SealedGuestArchive $record.archive
 }
 if([version]$settings.P2.version -le [version]$settings.P1.version -or $settings.P1.sha256 -eq $settings.P2.sha256){throw 'installed_guest_newer_successor_required'}
 return $settings
}

function Read-CohortInventory($Record) {
 $zip=[IO.Compression.ZipFile]::OpenRead($Record.archive)
 $reader=$null
 try {
  $entry=$zip.GetEntry('cohort.json')
  if(!$entry -or $entry.Length -gt 65536){throw 'installed_guest_inventory_invalid'}
  $reader=[IO.StreamReader]::new($entry.Open())
  $inventory=$reader.ReadToEnd()|ConvertFrom-Json
  if($inventory.version -cne $Record.version){throw 'installed_guest_inventory_version_mismatch'}
  return $inventory
 } finally {if($reader){$reader.Dispose()};$zip.Dispose()}
}

function Assert-CurrentCohort($Settings) {
 $previous=Read-CohortInventory $Settings.P1
 $current=Read-CohortInventory $Settings.P2
 $archive=[IO.Compression.ZipFile]::OpenRead($Settings.P2.archive)
 try {
  $members=[Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
  foreach($entry in $archive.Entries|Where-Object {$_.FullName -match '^(app|services)/' -and !$_.FullName.EndsWith('/')}) {
   $target=Join-Path $Stage $entry.FullName
   if(!(Test-Path -LiteralPath $target -PathType Leaf)){throw 'installed_current_cohort_file_missing'}
   if((Get-Item -LiteralPath $target).Attributes -band [IO.FileAttributes]::ReparsePoint){throw 'installed_current_cohort_reparse_refused'}
   $stream=$entry.Open();$hash=[Security.Cryptography.SHA256]::Create()
   try {$digest=[BitConverter]::ToString($hash.ComputeHash($stream)).Replace('-','')} finally {$hash.Dispose();$stream.Dispose()}
   if($digest -ne (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash){throw 'installed_current_cohort_hash_mismatch'}
   $null=$members.Add($entry.FullName)
  }
  foreach($directory in 'app','services') {
   $base=Join-Path $Stage $directory
   foreach($file in Get-ChildItem -LiteralPath $base -Recurse -File) {
    $relative="$directory/"+[IO.Path]::GetRelativePath($base,$file.FullName).Replace('\','/')
    if(!$members.Contains($relative)){throw 'installed_current_cohort_member_missing'}
   }
  }
 } finally {$archive.Dispose()}
 foreach($relative in 'dev/__init__.py','dev/runtime_lifecycle/__init__.py','dev/runtime_lifecycle/harness.py','dev/runtime_lifecycle/installed.py','dev/runtime_lifecycle/client_probes.py','dev/packaging/__init__.py','dev/packaging/command_execution.py') {
  $digest=(Get-FileHash -LiteralPath (Join-Path $Source $relative) -Algorithm SHA256).Hash
  if($current.files.PSObject.Properties["owners/$relative"].Value -ne $digest -or $previous.files.PSObject.Properties["owners/$relative"].Value -ne $digest){throw 'installed_current_campaign_owner_mismatch'}
 }
 $dispatcher=(Get-FileHash -LiteralPath (Join-Path $Source 'native/desktop/src-tauri/src/python/manager_dispatch.py') -Algorithm SHA256).Hash
 if($current.files.PSObject.Properties['metadata/native/manager_dispatch.py'].Value -ne $dispatcher -or $previous.files.PSObject.Properties['metadata/native/manager_dispatch.py'].Value -ne $dispatcher){throw 'installed_current_dispatcher_mismatch'}
}

function Invoke-FixtureDocker([string[]]$Arguments,[int]$Timeout=150) {
 $start=[Diagnostics.ProcessStartInfo]::new('docker.exe')
 foreach($argument in $Arguments){$start.ArgumentList.Add($argument)}
 $start.UseShellExecute=$false;$start.CreateNoWindow=$true
 $start.RedirectStandardOutput=$true;$start.RedirectStandardError=$true
 $process=[Diagnostics.Process]::Start($start)
 try {
  $stdout=$process.StandardOutput.ReadToEndAsync();$stderr=$process.StandardError.ReadToEndAsync()
  if(!$process.WaitForExit($Timeout*1000)){$process.Kill();$null=$process.WaitForExit(5000);throw 'installed_guest_docker_deadline'}
  if($process.ExitCode -ne 0){throw 'installed_guest_docker_failed'}
  return $stdout.GetAwaiter().GetResult()
 } finally {$process.Dispose()}
}

function Assert-FixtureCustody {
 $container=Invoke-FixtureDocker @('inspect','--format','{{json .Id}}',$script:GuestContainer)|ConvertFrom-Json
 if($script:ContainerId -and $container -ne $script:ContainerId){throw 'installed_guest_container_replaced'}
 $script:ContainerId=$container
 $labels=Invoke-FixtureDocker @('inspect','--format','{{json .Config.Labels}}',$script:GuestContainer)|ConvertFrom-Json
 $volume=Invoke-FixtureDocker @('volume','inspect','--format','{{json .Labels}}',$settings.volume)|ConvertFrom-Json
 foreach($value in $labels,$volume) {
  if($value.'cadrumo.fixture' -ne 'runtime-lifecycle-windows-guest' -or $value.'cadrumo.guest.uuid' -ne $script:GuestUuid){throw 'installed_guest_resource_custody_mismatch'}
 }
 $image=(Invoke-FixtureDocker @('inspect','--format','{{.Image}}',$script:GuestContainer)).Trim()
 $mounts=Invoke-FixtureDocker @('inspect','--format','{{json .Mounts}}',$script:GuestContainer)|ConvertFrom-Json
 if($image -ne $settings.guestImage -or @($mounts|Where-Object {$_.Type -eq 'volume' -and $_.Name -eq $settings.volume -and $_.Destination -eq '/storage'}).Count -ne 1){throw 'installed_guest_storage_or_image_mismatch'}
}

function Stop-FixtureGuest {
 Assert-FixtureCustody
 if((Invoke-FixtureDocker @('inspect','--format','{{.State.Running}}',$script:GuestContainer)).Trim() -eq 'true') {
  Invoke-FixtureDocker @('stop','-t','120',$script:GuestContainer) -Timeout 135|Out-Null
 }
 Assert-FixtureCustody
 if((Invoke-FixtureDocker @('inspect','--format','{{.State.Running}}',$script:GuestContainer)).Trim() -ne 'false'){throw 'installed_guest_did_not_stop'}
}

function Restore-FixtureBaseline {
 Stop-FixtureGuest
 $users=Invoke-FixtureDocker @('ps','--filter',"volume=$($settings.volume)",'--format','{{.ID}}')
 if($users.Trim()){throw 'installed_guest_disk_still_active'}
 # Fixed paths and argument-validated snapshot; no destructive path computed from guest data.
 $shell='set -eu; test "$(sha256sum /baseline/windows.vars | cut -d " " -f1)" = "$1"; test "$(sha256sum /baseline/windows.mac | cut -d " " -f1)" = "$2"; qemu-img snapshot -a "$3" /storage/data.qcow2; cp /baseline/windows.vars /storage/windows.vars; cp /baseline/windows.mac /storage/windows.mac; sync'
 $helper="cadrumo-restore-$script:InvocationId-$([guid]::NewGuid().ToString('N'))"
 try {
  Invoke-FixtureDocker @('run','--rm','--name',$helper,'--label','cadrumo.fixture=runtime-lifecycle-windows-guest','--label',"cadrumo.guest.uuid=$script:GuestUuid",'--network','none','--entrypoint','/bin/bash','--mount',"type=volume,source=$($settings.volume),target=/storage",'--mount',"type=bind,source=$($settings.baselineDirectory),target=/baseline,readonly",$settings.guestImage,'-c',$shell,'restore',$settings.firmwareVarsSha256.ToLowerInvariant(),$settings.firmwareMacSha256.ToLowerInvariant(),$settings.snapshot)|Out-Null
 } finally {
  $remaining=(Invoke-FixtureDocker @('ps','-a','--filter',"name=^/$helper$",'--format','{{.ID}}')).Trim()
  if($remaining) {
   $labels=Invoke-FixtureDocker @('inspect','--format','{{json .Config.Labels}}',$remaining)|ConvertFrom-Json
   if($labels.'cadrumo.fixture' -ne 'runtime-lifecycle-windows-guest' -or $labels.'cadrumo.guest.uuid' -ne $script:GuestUuid){throw 'installed_guest_restore_custody_mismatch'}
   Invoke-FixtureDocker @('stop','-t','10',$remaining)|Out-Null
   if((Invoke-FixtureDocker @('ps','--filter',"name=^/$helper$",'--format','{{.ID}}')).Trim()){throw 'installed_guest_restore_did_not_settle'}
  }
 }
 Assert-FixtureCustody
 Invoke-FixtureDocker @('start',$script:GuestContainer)|Out-Null
}

function Wait-FixtureSession {
 param([long]$PriorBootTicks=0)
 $deadline=[DateTime]::UtcNow.AddSeconds(240)
 do {
  $candidate=$null
  try {
   $candidate=Open-GuestSession
   if($PriorBootTicks -gt 0) {
    $bootTicks=Invoke-Command -Session $candidate -ArgumentList $script:GuestUuid -ScriptBlock {
     param($uuid)
     $ErrorActionPreference='Stop'
     if((Get-CimInstance Win32_ComputerSystemProduct).UUID -ne $uuid){throw 'wrong_guest'}
     (Get-CimInstance Win32_OperatingSystem).LastBootUpTime.ToUniversalTime().Ticks
    }
    if($bootTicks -isnot [long] -or $bootTicks -le 0){throw 'installed_guest_boot_identity_invalid'}
    if($bootTicks -eq $PriorBootTicks){throw 'installed_guest_prior_boot_still_running'}
    $script:Facts.Add(@{scope='machine';phase='reboot';priorBootTicks=$PriorBootTicks;bootTicks=$bootTicks;state='settled'})
   }
   $ready=$candidate;$candidate=$null
   return $ready
  } catch {
   if([DateTime]::UtcNow -ge $deadline){throw 'installed_guest_native_readiness_deadline'}
  } finally {if($candidate){Remove-PSSession $candidate}}
  Start-Sleep -Seconds 2
 } while($true)
}

function Wait-GuestInteractiveSession($Session,$Login) {
 $deadline=[DateTime]::UtcNow.AddSeconds(90)
 do {
  if($Login.process.HasExited){throw 'installed_guest_rdp_login_exited'}
  $ready=Invoke-Command -Session $Session -ArgumentList $script:GuestUuid,$script:GuestSid -ScriptBlock {
   param($uuid,$sid)
   if((Get-CimInstance Win32_ComputerSystemProduct).UUID -ne $uuid){throw 'wrong_guest'}
   $sessions=@(Get-CimInstance Win32_Process -Filter "Name='explorer.exe'"|Where-Object {(Invoke-CimMethod -InputObject $_ -MethodName GetOwnerSid).Sid -eq $sid}|Select-Object -ExpandProperty SessionId -Unique)
   $sessions.Count -eq 1 -and $sessions[0] -gt 0
  }
  if($ready){return}
  if([DateTime]::UtcNow -ge $deadline){throw 'installed_guest_interactive_login_deadline'}
  Start-Sleep -Seconds 2
 } while($true)
 # Explorer is only launch readiness; installed.main verifies actual token/LSA/CredRead.
}

function Retain-GuestEvidence($Session,$Run,[string]$Scope,[string]$Phase) {
 $evidence=Join-Path $directory "$Scope-$Phase-$($run.id)"
 $null=New-Item -ItemType Directory -Path $evidence
 $files=Invoke-Command -Session $Session -ArgumentList $run -ScriptBlock {
  param($run)
  foreach($name in 'stdout.txt','stderr.txt','status.json','transport-error.json','precommit-rollback.json') {
   $path=Join-Path $run.runPath $name
   if(Test-Path -LiteralPath $path -PathType Leaf){$path}
  }
 }
 foreach($file in $files){Copy-Item -LiteralPath $file -Destination $evidence -FromSession $Session}
 # Boot is read-only; maintenance receipts belong only to bounded task runs.
 if($Phase -ne 'boot') {
  $receipts=Invoke-Command -Session $Session -ArgumentList $run -ScriptBlock {
   param($run)
   $ErrorActionPreference='Stop'
   $created=[DateTime]::Parse($run.createdAtUtc).ToUniversalTime()
   $selected=0
   foreach($cohort in 'P1','P2') {
    $root="C:\acceptance\$cohort\intents"
    foreach($parent in @('C:\acceptance',"C:\acceptance\$cohort",$root)) {
     $entry=Get-Item -LiteralPath $parent
     if(!$entry.PSIsContainer -or ($entry.Attributes -band [IO.FileAttributes]::ReparsePoint)){throw 'native_failure_evidence_root_invalid'}
    }
    foreach($entry in Get-ChildItem -LiteralPath $root -Filter 'native-maintenance-failure-*.json') {
     if($entry.Name -cnotmatch '^native-maintenance-failure-[a-fA-F0-9]{32}\.json$'){continue}
     if($entry.CreationTimeUtc -lt $created){continue}
     $selected++
     if($selected -gt 32){throw 'native_failure_evidence_count_exceeded'}
     if($entry.PSIsContainer -or ($entry.Attributes -band [IO.FileAttributes]::ReparsePoint) -or $entry.Length -gt 65536 -or $entry.DirectoryName -ine $root){throw 'native_failure_evidence_file_invalid'}
     @{cohort=$cohort;path=$entry.FullName;name=$entry.Name;bytes=$entry.Length;sha256=(Get-FileHash -LiteralPath $entry.FullName -Algorithm SHA256).Hash.ToLowerInvariant();createdAtUtc=$entry.CreationTimeUtc.ToString('O')}
    }
   }
  }
  $retained=[Collections.Generic.List[object]]::new()
  foreach($receipt in $receipts) {
   if($receipt.cohort -notin 'P1','P2' -or $receipt.name -cnotmatch '^native-maintenance-failure-[a-fA-F0-9]{32}\.json$'){throw 'native_failure_evidence_binding_invalid'}
   $destination=Join-Path $evidence $receipt.cohort
   $null=New-Item -ItemType Directory -Path $destination -Force
   $target=Join-Path $destination $receipt.name
   Copy-Item -LiteralPath $receipt.path -Destination $target -FromSession $Session
   if((Get-Item -LiteralPath $target).Length -ne $receipt.bytes -or (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash -ine $receipt.sha256){throw 'native_failure_evidence_copy_mismatch'}
   $retained.Add(@{run=$run.id;runCreatedAtUtc=$run.createdAtUtc;cohort=$receipt.cohort;file="$($receipt.cohort)/$($receipt.name)";sha256=$receipt.sha256;bytes=$receipt.bytes;createdAtUtc=$receipt.createdAtUtc})
  }
  [IO.File]::WriteAllText((Join-Path $evidence 'native-maintenance-failures.json'),(ConvertTo-Json -InputObject @($retained.ToArray()) -Depth 5),[Text.UTF8Encoding]::new($false))
 }
 return $evidence
}

function Invoke-NativePhase($Session,[string]$Scope,[string]$Phase,[switch]$Successor,
 [ValidateSet('P1','P2')][string]$Cohort='P1') {
 $run=Start-GuestPhase -Session $Session -Scope $Scope -Phase $Phase -Cohort $Cohort -Successor:$Successor -SealedCohortAuthorized
 $deadline=[DateTime]::UtcNow.AddMinutes(30);$timedOut=$false
 do {
  $status=Get-GuestPhase $Session $run
  if($status.state -eq 'completed'){break}
  if([DateTime]::UtcNow -ge $deadline){$timedOut=$true;break}
  Start-Sleep -Seconds 2
 } while($true)
 $evidence=Retain-GuestEvidence $Session $run $Scope $Phase
 if($timedOut){$script:Facts.Add(@{cohort=$Cohort;scope=$Scope;phase=$Phase;task=$run.id;exitCode=1});throw 'installed_guest_native_phase_deadline'}
 $status=Complete-GuestTask $Session $run
 $script:Facts.Add(@{cohort=$Cohort;scope=$Scope;phase=$Phase;task=$run.id;exitCode=$status.exitCode})
 if($status.exitCode -ne 0){throw "installed_guest_native_phase_failed_$Phase"}
 $receipt=Get-Content -LiteralPath "$evidence/stdout.txt" -Raw|ConvertFrom-Json
 if($Phase -eq 'precommit-rollback') {
  if($receipt.precommit_rollback -ne 'passed'){throw 'installed_guest_precommit_not_proven'}
 } elseif($Phase -eq 'cleanup') {
  if($receipt.schema -ne 1 -or $receipt.scope -ne $Scope -or $receipt.phase -ne 'cleanup' -or $receipt.result -ne 'passed' -or $receipt.full_installation_acceptance -ne 'passed' -or @($receipt.pending).Count -ne 0){throw 'installed_guest_cleanup_acceptance_incomplete'}
 }
}

$settings=Read-AcceptanceConfiguration
Assert-CurrentCohort $settings
if($ValidateOnly){Write-Output 'Installed guest configuration and current cohort bindings validated; no guest executed.';exit 0}
$script:InvocationId=[guid]::NewGuid().ToString('N')
$script:FixtureRoot=$settings.fixtureRoot;$script:PasswordFile=$settings.passwordFile
$script:GuestUuid=$settings.uuid;$script:GuestSid=$settings.sid;$script:GuestPin=$settings.tlsPin
$script:GuestPort=$settings.port;$script:GuestAccount=$settings.account;$script:GuestComputer=$settings.computer
$script:GuestContainer=$settings.container;$script:GuestNetwork=$settings.network;$script:RdpImage=$settings.rdpImage
$script:Facts=[Collections.Generic.List[object]]::new()
$session=$null;$login=$null;$accepted=$false
$directory=Join-Path $Output $script:InvocationId
$null=New-Item -ItemType Directory -Path $directory
try {
 Assert-FixtureCustody
 foreach($scope in 'user','machine') {
  foreach($campaign in 'precommit','full') {
   Restore-FixtureBaseline
   $session=Wait-FixtureSession
   foreach($cohort in 'P1','P2') {
    $label="$script:InvocationId-$scope-$campaign-$cohort"
    $null=Stage-GuestCohort -SealedArchive $settings.$cohort.archive -ArchiveReceipt $settings.$cohort.receipt -ExpectedSha256 $settings.$cohort.sha256 -ExpectedVersion $settings.$cohort.version -Cohort $cohort -ArchiveLabel $label
    $null=Copy-GuestCohort -Session $session -Cohort $cohort -ExpectedSha256 $settings.$cohort.sha256 -ExpectedVersion $settings.$cohort.version -ArchiveLabel $label -SealedCohortAuthorized
   }
   Disable-GuestAutoLogin $session
   $pin=Get-GuestRdpPin $session
   $login=Start-GuestRdpLogin $pin.sha256
   Wait-GuestInteractiveSession $session $login
   if($campaign -eq 'precommit') {
    Invoke-NativePhase $session $scope 'precommit-rollback' -Cohort P2
   } else {
    Invoke-NativePhase $session $scope 'hold'
    if($scope -eq 'user') {
     $null=Logoff-GuestInteractiveSession $session
     $null=Stop-GuestRdpClient $login;$login=$null
     $pin=Get-GuestRdpPin $session;$login=Start-GuestRdpLogin $pin.sha256
     Wait-GuestInteractiveSession $session $login
    } else {
     $null=Stop-GuestRdpClient $login;$login=$null
     $priorBootTicks=Invoke-Command -Session $session -ArgumentList $script:GuestUuid -ScriptBlock {
      param($uuid)
      $ErrorActionPreference='Stop'
      if((Get-CimInstance Win32_ComputerSystemProduct).UUID -ne $uuid){throw 'wrong_guest'}
      $bootTicks=(Get-CimInstance Win32_OperatingSystem).LastBootUpTime.ToUniversalTime().Ticks
      & C:\Windows\System32\shutdown.exe /r /t 0
      if($LASTEXITCODE -ne 0){throw 'native_reboot_failed'}
      $bootTicks
     }
     if($priorBootTicks -isnot [long] -or $priorBootTicks -le 0){throw 'installed_guest_boot_identity_invalid'}
     Remove-PSSession $session;$session=$null
     $session=Wait-FixtureSession -PriorBootTicks $priorBootTicks
     $boot=Invoke-GuestBootPhase $session -SealedCohortAuthorized
     $null=Retain-GuestEvidence $session $boot $scope 'boot'
     $script:Facts.Add(@{scope=$scope;phase='boot';exitCode=$boot.exitCode})
     if($boot.exitCode -ne 0){throw 'installed_guest_native_boot_failed'}
     $pin=Get-GuestRdpPin $session;$login=Start-GuestRdpLogin $pin.sha256
     Wait-GuestInteractiveSession $session $login
    }
    Invoke-NativePhase $session $scope 'login'
    Invoke-NativePhase $session $scope 'scope-conflict'
    if($scope -eq 'user') {
     Invoke-NativePhase $session $scope 'scope-verify'
     Invoke-NativePhase $session $scope 'upgrade-rollback' -Successor
    } else {
     foreach($phase in 'gui-stop','gui-user','gui-restore'){Invoke-NativePhase $session $scope $phase}
     Invoke-NativePhase $session $scope 'machine-upgrade' -Successor
    }
    Invoke-NativePhase $session $scope 'cleanup' -Successor
   }
   $null=Stop-GuestRdpClient $login;$login=$null
   Remove-PSSession $session;$session=$null
  }
 }
 Assert-CurrentCohort $settings
 $accepted=$true
} finally {
 # Whole-fixture custody settles any unsuccessful native phase; no failed cleanup is relabeled.
 $campaignPassed=$accepted;$accepted=$false;$settlementFailed=$false
 try {if($login){$null=Stop-GuestRdpClient $login}} catch {$settlementFailed=$true;throw} finally {
  try {if($session){Remove-PSSession $session}} catch {$settlementFailed=$true;throw} finally {
   try {Stop-FixtureGuest;$accepted=$campaignPassed -and !$settlementFailed} finally {
    @{schema=1;invocation=$script:InvocationId;P1=$settings.P1.sha256;P2=$settings.P2.sha256;accepted=$accepted;facts=$script:Facts}|ConvertTo-Json -Depth 10|Set-Content -LiteralPath "$directory/result.json" -Encoding utf8
   }
  }
 }
}
if(!$accepted){throw 'installed_guest_acceptance_failed'}
Write-Output 'Actual installed user and machine campaigns, rollback and native cleanup passed in this invocation.'
