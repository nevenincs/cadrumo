# Acceptance transport only; dot-sourcing performs no guest actions.
function Assert-GuestTls {
 $tcp=[Net.Sockets.TcpClient]::new()
 $tls=$null
 try {
  $tcp.Connect('127.0.0.1',$script:GuestPort)
  $tls=[Net.Security.SslStream]::new($tcp.GetStream(),$false,{param($sender,$cert,$chain,$errors)
   $leaf=[Security.Cryptography.X509Certificates.X509Certificate2]::new($cert)
   $now=[DateTime]::UtcNow
   $leaf.GetCertHashString([Security.Cryptography.HashAlgorithmName]::SHA256) -eq $script:GuestPin -and $now -ge $leaf.NotBefore.ToUniversalTime() -and $now -le $leaf.NotAfter.ToUniversalTime()
  })
  $tls.ReadTimeout=5000;$tls.WriteTimeout=5000
  $tls.AuthenticateAsClient($script:GuestComputer)
 } finally {if($tls){$tls.Dispose()};$tcp.Dispose()}
}
function Open-GuestSession {
 # Separate pre/post leaf-pin probes bind the trusted loopback fixture route;
 # WSMan uses native certificate-time validation with session-only CA/CN exceptions.
 # This is not a certificate callback on the WSMan connection itself.
 Assert-GuestTls
 $secret=Get-Content -LiteralPath $script:PasswordFile|ConvertTo-SecureString
 $credential=[pscredential]::new("$script:GuestComputer\$script:GuestAccount",$secret)
 $options=New-PSSessionOption -SkipCACheck -SkipCNCheck -SkipRevocationCheck -Culture en-US -UICulture en-US -OpenTimeout 10000 -OperationTimeout 30000
 $session=New-PSSession -ComputerName 127.0.0.1 -Port $script:GuestPort -UseSSL -Authentication Negotiate -Credential $credential -SessionOption $options -ErrorAction Stop
 try {
  $identity=Invoke-Command -Session $session -ArgumentList $script:GuestAccount -ScriptBlock {param($account);$p=Get-CimInstance Win32_ComputerSystemProduct;$s=Get-CimInstance Win32_ComputerSystem;@{uuid=$p.UUID;manufacturer=$s.Manufacturer;model=$s.Model;sid=(Get-LocalUser $account).SID.Value}}
  if($identity.uuid -ne $script:GuestUuid -or $identity.manufacturer -ne 'QEMU' -or $identity.model -ne 'CadrumoRuntimeGuest' -or $identity.sid -ne $script:GuestSid){throw 'guest_native_identity_mismatch'}
  Assert-GuestTls
  return $session
 } catch {Remove-PSSession $session;throw}
}
function New-GuestPlans {
 param([Parameter(Mandatory)][string]$CohortDirectory,[ValidateSet('P1','P2')][string]$Cohort)
 $kit=Get-Content -LiteralPath "$CohortDirectory/services/kit.json" -Raw|ConvertFrom-Json
 if($kit.schema -ne 1){throw 'canonical_kit_schema_invalid'}
 $destination=Join-Path $CohortDirectory 'intents'
 New-Item -ItemType Directory -Path $destination -Force|Out-Null
 foreach($scope in 'user','machine') {
  $plan=@{schema=1;scope=$scope;prefix="C:\CadrumoAcceptance\$scope"}
  foreach($key in 'version','manifest_sha256','desktop_present','contract'){$plan[$key]=$kit.maintenance.PSObject.Properties[$key].Value}
  foreach($role in 'version','registration') {
   $artifact=$kit.artifacts.PSObject.Properties["$scope-$role"].Value
   if(!$artifact -or $artifact.path -ne "$scope-$role.msi"){throw 'canonical_kit_artifact_path_invalid'}
   $plan["${role}_product"]=@{path="C:\acceptance\$Cohort\services\$($artifact.path)";sha256=$artifact.sha256;product_code=$artifact.product_code}
  }
  [IO.File]::WriteAllText("$destination/maintenance-$scope.json",($plan|ConvertTo-Json -Depth 40),[Text.UTF8Encoding]::new($false))
 }
}
function Start-GuestPhase {
 param([Parameter(Mandatory)]$Session,[ValidateSet('P1','P2')][string]$Cohort='P1',
 [ValidateSet('user','machine')][string]$Scope,
 [ValidateSet('precommit-rollback','hold','login','scope-conflict','scope-verify','gui-stop','gui-user','gui-restore','upgrade-rollback','machine-upgrade','cleanup')][string]$Phase,
 [switch]$Successor,[switch]$SealedCohortAuthorized)
 if(!$SealedCohortAuthorized){throw 'sealed_cohort_GO_required_before_guest_campaign'}
 if($Phase -in 'gui-stop','gui-user','gui-restore' -and $Scope -ne 'machine'){throw 'machine_gui_phase_scope_invalid'}
 $id=[guid]::NewGuid().ToString('N')
 $request=@{id=$id;uuid=$script:GuestUuid;sid=$script:GuestSid;cohort=$Cohort;scope=$Scope;phase=$Phase;successor=[bool]$Successor}
 Invoke-Command -Session $Session -ArgumentList $request -ScriptBlock {
  param($request)
  $ErrorActionPreference='Stop'
  if((Get-CimInstance Win32_ComputerSystemProduct).UUID -ne $request.uuid){throw 'wrong_guest'}
  $createdAtUtc=[DateTime]::UtcNow.ToString('O')
  $root='C:\acceptance';$directory="$root\runs\$($request.id)"
  New-Item -ItemType Directory -Path $directory -Force|Out-Null
  $request|ConvertTo-Json|Set-Content -LiteralPath "$directory\request.json" -Encoding utf8
  $scheduler=New-Object -ComObject Schedule.Service;$scheduler.Connect()
  $task=$scheduler.NewTask(0)
  $task.RegistrationInfo.Source=$request.uuid
  $task.Principal.UserId=$request.sid;$task.Principal.LogonType=3
  $task.Principal.RunLevel=[int](($request.scope -eq 'machine' -and $request.phase -ne 'gui-user') -or $request.phase -eq 'scope-conflict')
  $task.Settings.Hidden=$true;$task.Settings.ExecutionTimeLimit='PT30M'
  $task.Settings.DisallowStartIfOnBatteries=$false;$task.Settings.StopIfGoingOnBatteries=$false
  $action=$task.Actions.Create(0)
  $action.Path='C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe'
  $action.Arguments='-WindowStyle Hidden -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "C:\acceptance\phase-task.ps1" -Request "'+$directory+'\request.json" -ExpectedUuid '+$request.uuid+' -ExpectedSid '+$request.sid
  $name='CadrumoAcceptance-'+$request.id
  $registered=$scheduler.GetFolder('\').RegisterTaskDefinition($name,$task,2,$request.sid,$null,3)
  $running=$registered.Run($null)
  @{id=$request.id;name=$name;runPath=$directory;phase=$request.phase;scope=$request.scope;createdAtUtc=$createdAtUtc}
 }
}
function Get-GuestPhase {
 param([Parameter(Mandatory)]$Session,[Parameter(Mandatory)]$Run)
 Invoke-Command -Session $Session -ArgumentList $Run,$script:GuestUuid -ScriptBlock {
  param($run,$uuid)
  $scheduler=New-Object -ComObject Schedule.Service;$scheduler.Connect()
  $task=$scheduler.GetFolder('\').GetTask($run.name)
  if($task.Definition.RegistrationInfo.Source -ne $uuid){throw 'foreign_task'}
  $status="$($run.runPath)\status.json"
  if($task.State -notin 2,4 -and (Test-Path -LiteralPath $status)){Get-Content -LiteralPath $status -Raw|ConvertFrom-Json}
  elseif($task.State -notin 2,4 -and ([DateTime]::UtcNow-[DateTime]::Parse($run.createdAtUtc).ToUniversalTime()).TotalSeconds -ge 5) {@{state='completed';exitCode=1;failure='task_settled_without_native_status';taskState=$task.State;lastTaskResult=$task.LastTaskResult;phase=$run.phase}}
  else {@{state='running';taskState=$task.State;lastTaskResult=$task.LastTaskResult;phase=$run.phase}}
 }
}
function Complete-GuestTask {
 # Removing a settled transport task does not prove native campaign cleanup.
 # Missing status is failure; recovery requires the exact stopped-guest baseline.
 param([Parameter(Mandatory)]$Session,[Parameter(Mandatory)]$Run)
 Invoke-Command -Session $Session -ArgumentList $Run,$script:GuestUuid -ScriptBlock {
  param($run,$uuid)
  $scheduler=New-Object -ComObject Schedule.Service;$scheduler.Connect();$folder=$scheduler.GetFolder('\');$task=$folder.GetTask($run.name)
  if($task.Definition.RegistrationInfo.Source -ne $uuid -or $task.State -in 2,4){throw 'task_not_settled_or_not_owned'}
  if(Test-Path -LiteralPath "$($run.runPath)\status.json"){$status=Get-Content -LiteralPath "$($run.runPath)\status.json" -Raw|ConvertFrom-Json}
  elseif(([DateTime]::UtcNow-[DateTime]::Parse($run.createdAtUtc).ToUniversalTime()).TotalSeconds -ge 5){$status=@{state='completed';exitCode=1;failure='task_settled_without_native_status';lastTaskResult=$task.LastTaskResult;phase=$run.phase}}
  else {throw 'task_start_settlement_pending'}
  $folder.DeleteTask($run.name,0)
  $status
 }
}
function Invoke-GuestBootPhase {
 param([Parameter(Mandatory)]$Session,[switch]$SealedCohortAuthorized)
 if(!$SealedCohortAuthorized){throw 'sealed_cohort_GO_required_before_guest_campaign'}
 Invoke-Command -Session $Session -ArgumentList $script:GuestUuid,$script:GuestSid -ScriptBlock {
  param($uuid,$sid)
  if((Get-CimInstance Win32_ComputerSystemProduct).UUID -ne $uuid){throw 'wrong_guest'}
  $id=[guid]::NewGuid().ToString('N');$path="C:\acceptance\runs\$id"
  $null=New-Item -ItemType Directory -Path $path
  $code="import sys; sys.path.insert(0, r'C:\acceptance\P1\owners'); from dev.runtime_lifecycle.installed import main; main()"
  $exitCode=1
  try {
   $ErrorActionPreference='Continue'
   & C:\acceptance\P1\app\python.exe -I -B -c $code --plan C:\acceptance\P1\intents\maintenance-machine.json --runner C:\acceptance\P1\services\cadrumo-msi-maintenance.exe --installed-vm-id $uuid --installed-account-sid $sid --installed-guest-kind qemu --phase boot --campaign-state C:\acceptance\campaigns\machine.json 1>"$path\stdout.txt" 2>"$path\stderr.txt"
   if($null -ne $LASTEXITCODE){$exitCode=$LASTEXITCODE}
  } finally {
   $ErrorActionPreference='Stop'
   @{phase='boot';state='completed';exitCode=$exitCode;completedAtUtc=[DateTime]::UtcNow}|ConvertTo-Json -Compress|Set-Content -LiteralPath "$path\status.json"
  }
  @{id=$id;runPath=$path;phase='boot';scope='machine';exitCode=$exitCode}
 }
}
function Disable-GuestAutoLogin {
 param([Parameter(Mandatory)]$Session)
 Invoke-Command -Session $Session -ArgumentList $script:GuestUuid -ScriptBlock {param($uuid);if((Get-CimInstance Win32_ComputerSystemProduct).UUID -ne $uuid){throw 'wrong_guest'};Set-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon' -Name AutoAdminLogon -Value '0'}
}
function Get-GuestRdpPin {
 param([Parameter(Mandatory)]$Session)
 Invoke-Command -Session $Session -ScriptBlock {
  $rdp=Get-CimInstance -Namespace root/cimv2/TerminalServices -ClassName Win32_TSGeneralSetting -Filter "TerminalName='RDP-tcp'"
  $certificate=Get-ChildItem -LiteralPath 'Cert:\LocalMachine\Remote Desktop'|Where-Object Thumbprint -EQ $rdp.SSLCertificateSHA1Hash
  if(@($certificate).Count -ne 1){throw 'rdp_certificate_identity_unavailable'}
  @{sha256=$certificate.GetCertHashString([Security.Cryptography.HashAlgorithmName]::SHA256);thumbprint=$certificate.Thumbprint}
 }
}
function Start-GuestRdpLogin {
 param([Parameter(Mandatory)][string]$CertificateSha256)
 if($CertificateSha256 -notmatch '^[a-fA-F0-9]{64}$'){throw 'rdp_pin_invalid'}
 $image=$script:RdpImage
 $clientName="cadrumo-rdp-$script:InvocationId-$([guid]::NewGuid().ToString('N'))"
 $cidPath=Join-Path $script:FixtureRoot "$clientName.cid"
 $start=[Diagnostics.ProcessStartInfo]::new('docker.exe')
 foreach($arg in @('run','--rm','--init','-i','--name',$clientName,'--cidfile',$cidPath,'--network',$script:GuestNetwork,'--cpus','1','--memory','384m','--label','cadrumo.fixture=runtime-lifecycle-windows-guest','--label',"cadrumo.guest.uuid=$script:GuestUuid",$image,"/v:$script:GuestContainer`:3389","/u:$script:GuestAccount","/d:$script:GuestComputer",'/sec:nla','/from-stdin:force',"/cert:fingerprint:sha256:$CertificateSha256",'/size:800x600','-clipboard','/log-level:ERROR')){$start.ArgumentList.Add($arg)}
 $start.UseShellExecute=$false;$start.CreateNoWindow=$true;$start.RedirectStandardInput=$true
 $start.RedirectStandardOutput=$true;$start.RedirectStandardError=$true
 $process=[Diagnostics.Process]::Start($start)
 $login=@{process=$process;stdout=$process.StandardOutput.ReadToEndAsync();stderr=$process.StandardError.ReadToEndAsync();container=$clientName;cidPath=$cidPath}
 try {
  $secret=Get-Content $script:PasswordFile|ConvertTo-SecureString
  $process.StandardInput.WriteLine(([pscredential]::new($script:GuestAccount,$secret)).GetNetworkCredential().Password)
  $process.StandardInput.Close()
 } catch {$null=Stop-GuestRdpClient $login;throw}
 return $login
}

function Assert-SealedGuestArchive {
 param([Parameter(Mandatory)][string]$Path)
 Add-Type -AssemblyName System.IO.Compression.FileSystem
 $archive=[IO.Compression.ZipFile]::OpenRead($Path)
 try {
  $names=[Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
  foreach($entry in $archive.Entries) {
   $name=$entry.FullName
   if($name.Contains('\') -or $name.StartsWith('/') -or $name -match '[:<>"|?*\x00-\x1f]' -or $name -match '(^|/)\.{1,2}(/|$)' -or $name -match '//'){throw 'archive_entry_traversal_invalid'}
   $trimmed=$name.TrimEnd('/')
   foreach($segment in $trimmed.Split('/')){if(!$segment -or $segment.EndsWith('.') -or $segment.EndsWith(' ') -or $segment -match '^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])($|\.)'){throw 'archive_windows_path_alias_invalid'}}
   if(!$trimmed -or !$names.Add($trimmed) -or ($trimmed -ne 'cohort.json' -and $trimmed -notmatch '^(app|services|owners|metadata|evidence)(/|$)')){throw 'archive_entry_shape_or_collision_invalid'}
   if((($entry.ExternalAttributes -shr 16) -band 0xF000) -eq 0xA000){throw 'archive_symlink_refused'}
  }
  foreach($required in 'cohort.json','app/python.exe','services/kit.json','metadata/wix/user-registration.wxs','metadata/wix/machine-registration.wxs','metadata/native/manager_dispatch.py'){if(!$names.Contains($required)){throw 'archive_required_entry_missing'}}
 } finally {$archive.Dispose()}
}
function Stage-GuestCohort {
 param([Parameter(Mandatory)][string]$SealedArchive,[Parameter(Mandatory)][string]$ArchiveReceipt,[Parameter(Mandatory)][ValidatePattern('^[a-fA-F0-9]{64}$')][string]$ExpectedSha256,[Parameter(Mandatory)][ValidatePattern('^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$')][string]$ExpectedVersion,[Parameter(Mandatory)][ValidateSet('P1','P2')][string]$Cohort,[ValidatePattern('^[a-zA-Z0-9][a-zA-Z0-9.-]{0,80}$')][string]$ArchiveLabel)
 if(!$ArchiveLabel){$ArchiveLabel=$Cohort}
 $archivePath=(Resolve-Path -LiteralPath $SealedArchive -ErrorAction Stop).Path
 $receiptPath=(Resolve-Path -LiteralPath $ArchiveReceipt -ErrorAction Stop).Path
 $receipt=Get-Content -LiteralPath $receiptPath -Raw|ConvertFrom-Json
 $boundPath=if([IO.Path]::IsPathRooted($receipt.path)){[IO.Path]::GetFullPath($receipt.path)}else{[IO.Path]::GetFullPath((Join-Path (Split-Path $receiptPath) $receipt.path))}
 if($boundPath -ne $archivePath -or $receipt.sha256 -ne $ExpectedSha256 -or $receipt.bytes -ne (Get-Item -LiteralPath $archivePath).Length -or (Get-FileHash -LiteralPath $archivePath -Algorithm SHA256).Hash -ne $ExpectedSha256){throw 'sealed_archive_receipt_mismatch'}
 Assert-SealedGuestArchive -Path $archivePath
 $zip=[IO.Compression.ZipFile]::OpenRead($archivePath)
 $reader=$null
 try {
  $entry=$zip.GetEntry('cohort.json')
  if(!$entry -or $entry.Length -gt 65536){throw 'sealed_cohort_inventory_invalid'}
  $reader=[IO.StreamReader]::new($entry.Open(),[Text.UTF8Encoding]::new($false,$true))
  $inventory=$reader.ReadToEnd()|ConvertFrom-Json
  if($inventory.version -isnot [string] -or $inventory.version -cne $ExpectedVersion){throw 'sealed_cohort_version_invalid'}
 } finally {
  if($reader){$reader.Dispose()}
  $zip.Dispose()
 }
 $directory="$script:FixtureRoot/exchange/transfers"
 $destination="$directory/$ArchiveLabel.zip"
 if(Test-Path -LiteralPath $destination){throw 'transfer_archive_already_exists'}
 New-Item -ItemType Directory -Path $directory -Force|Out-Null
 Copy-Item -LiteralPath $archivePath -Destination $destination -ErrorAction Stop
 @{cohort=$Cohort;archiveLabel=$ArchiveLabel;path=$destination;sha256=$ExpectedSha256;bytes=$receipt.bytes;expectedVersion=$ExpectedVersion;sourceReceipt=$receiptPath}|ConvertTo-Json|Set-Content -LiteralPath "$directory/$ArchiveLabel-archive.json" -Encoding utf8
 return $destination
}
function Copy-GuestCohort {
 param([Parameter(Mandatory)]$Session,[Parameter(Mandatory)][ValidateSet('P1','P2')][string]$Cohort,[Parameter(Mandatory)][ValidatePattern('^[a-fA-F0-9]{64}$')][string]$ExpectedSha256,[Parameter(Mandatory)][ValidatePattern('^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$')][string]$ExpectedVersion,[switch]$SealedCohortAuthorized,[ValidatePattern('^[a-zA-Z0-9][a-zA-Z0-9.-]{0,80}$')][string]$ArchiveLabel)
 if(!$SealedCohortAuthorized){throw 'sealed_cohort_GO_required_before_guest_transfer'}
 if(!$ArchiveLabel){$ArchiveLabel=$Cohort}
 $receipt=Get-Content -LiteralPath "$script:FixtureRoot/exchange/transfers/$ArchiveLabel-archive.json" -Raw|ConvertFrom-Json
 if($receipt.cohort -ne $Cohort -or ($receipt.archiveLabel -and $receipt.archiveLabel -ne $ArchiveLabel) -or $receipt.sha256 -ne $ExpectedSha256 -or $receipt.expectedVersion -isnot [string] -or $receipt.expectedVersion -cne $ExpectedVersion -or $receipt.bytes -le 0 -or $receipt.path -ne "$script:FixtureRoot/exchange/transfers/$ArchiveLabel.zip"){throw 'staged_archive_binding_invalid'}
 $archiveValidator=${function:Assert-SealedGuestArchive}.ToString()
 $planWriter=${function:New-GuestPlans}.ToString()
 Invoke-Command -Session $Session -ArgumentList $Cohort,$script:GuestUuid,$script:GuestSid,$receipt.sha256,$receipt.bytes,$archiveValidator,$planWriter,$ArchiveLabel,$ExpectedVersion -ScriptBlock {
  param($cohort,$uuid,$sid,$expectedSha,$expectedBytes,$archiveValidator,$planWriter,$archiveLabel,$expectedVersion)
  $ErrorActionPreference='Stop'
  $ProgressPreference='SilentlyContinue'
  if((Get-CimInstance Win32_ComputerSystemProduct).UUID -ne $uuid){throw 'wrong_guest'}
  $destination="C:\acceptance\$cohort"
  if(Test-Path -LiteralPath $destination){throw 'guest_cohort_already_exists'}
  if($cohort -eq 'P1' -and ((Test-Path C:\CadrumoAcceptance\user) -or (Test-Path C:\CadrumoAcceptance\machine))){throw 'initial_campaign_prefix_not_fresh'}
  $archive="C:\acceptance\downloads\$archiveLabel.zip"
  New-Item -ItemType Directory -Path C:\acceptance,C:\acceptance\campaigns,C:\acceptance\downloads,C:\CadrumoAcceptance -Force|Out-Null
  foreach($directory in 'C:\acceptance','C:\acceptance\campaigns','C:\acceptance\downloads','C:\CadrumoAcceptance') {
   if((Get-Item -LiteralPath $directory).Attributes -band [IO.FileAttributes]::ReparsePoint){throw 'guest_fixture_reparse_refused'}
  }
  foreach($directory in @('C:\acceptance','C:\CadrumoAcceptance')) {
   $acl=New-Object Security.AccessControl.DirectorySecurity
   $acl.SetAccessRuleProtection($true,$false)
   foreach($owner in @($sid,'S-1-5-18','S-1-5-32-544')){$acl.AddAccessRule((New-Object Security.AccessControl.FileSystemAccessRule([Security.Principal.SecurityIdentifier]::new($owner),'FullControl','ContainerInherit,ObjectInherit','None','Allow')))}
   Set-Acl -LiteralPath $directory -AclObject $acl
  }
  if(!(Test-Path -LiteralPath $archive)){Copy-Item -LiteralPath "\\host.lan\Data\transfers\$archiveLabel.zip" -Destination $archive}
  if((Get-Item -LiteralPath $archive).Length -ne $expectedBytes -or (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash -ne $expectedSha){throw 'guest_archive_digest_mismatch'}
  & ([scriptblock]::Create($archiveValidator)) -Path $archive
  Expand-Archive -LiteralPath $archive -DestinationPath $destination
  $inventory=Get-Content -LiteralPath "$destination\cohort.json" -Raw|ConvertFrom-Json
  if($inventory.version -isnot [string] -or $inventory.version -cne $expectedVersion){throw 'sealed_cohort_version_invalid'}
  $critical=@('app/data/package-manifest.json','services/kit.json','metadata/wix/user-registration.wxs','metadata/wix/machine-registration.wxs','metadata/native/manager_dispatch.py','owners/dev/__init__.py','owners/dev/runtime_lifecycle/__init__.py','owners/dev/runtime_lifecycle/harness.py','owners/dev/runtime_lifecycle/client_probes.py','owners/dev/runtime_lifecycle/installed.py','owners/dev/packaging/__init__.py','owners/dev/packaging/command_execution.py')
  foreach($relative in $critical) {
   $digest=$inventory.files.PSObject.Properties[$relative].Value
   $target=[IO.Path]::GetFullPath((Join-Path $destination $relative))
   if(!$target.StartsWith($destination+'\',[StringComparison]::OrdinalIgnoreCase) -or $digest -notmatch '^[a-fA-F0-9]{64}$' -or (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash -ne $digest){throw 'guest_critical_digest_mismatch'}
  }
  $kit=Get-Content -LiteralPath "$destination\services\kit.json" -Raw|ConvertFrom-Json
  $manifest=Get-Content -LiteralPath "$destination\app\data\package-manifest.json" -Raw|ConvertFrom-Json
  if($kit.maintenance.version -isnot [string] -or $manifest.build.version -isnot [string] -or $kit.maintenance.version -cne $expectedVersion -or $manifest.build.version -cne $expectedVersion){throw 'guest_product_version_binding_invalid'}
  & ([scriptblock]::Create($planWriter)) -CohortDirectory $destination -Cohort $cohort
  New-Item -ItemType Directory -Path "$destination\intents\wix"|Out-Null
  Copy-Item -LiteralPath "$destination\metadata\wix\user-registration.wxs","$destination\metadata\wix\machine-registration.wxs" -Destination "$destination\intents\wix"
  @{cohort=$cohort;version=$expectedVersion;transfer='verified';archiveSha256=$expectedSha;archiveBytes=$expectedBytes;criticalFiles=$critical.Count}
 }
 Copy-Item -LiteralPath "$PSScriptRoot/phase-task.ps1" -Destination C:\acceptance\phase-task.ps1 -ToSession $Session
}
function Logoff-GuestInteractiveSession {
 param([Parameter(Mandatory)]$Session)
 Invoke-Command -Session $Session -ArgumentList $script:GuestUuid,$script:GuestSid -ScriptBlock {
  param($uuid,$sid)
  $ErrorActionPreference='Stop'
  if((Get-CimInstance Win32_ComputerSystemProduct).UUID -ne $uuid){throw 'wrong_guest'}
  $sessions=@(Get-CimInstance Win32_Process -Filter "Name='explorer.exe'"|Where-Object {(Invoke-CimMethod -InputObject $_ -MethodName GetOwnerSid).Sid -eq $sid}|Select-Object -ExpandProperty SessionId -Unique)
  if($sessions.Count -ne 1 -or $sessions[0] -le 0){throw 'dedicated_interactive_session_not_unique'}
  if(!('CadrumoGuestLogoffSession' -as [type])) {
   Add-Type -TypeDefinition @'
using System;
using System.ComponentModel;
using System.Runtime.InteropServices;
public static class CadrumoGuestLogoffSession {
 [StructLayout(LayoutKind.Sequential)] struct Session { public int Id; public IntPtr Name; public int State; }
 [DllImport("wtsapi32.dll", SetLastError=true)] static extern bool WTSEnumerateSessionsW(IntPtr server, int reserved, int version, out IntPtr sessions, out int count);
 [DllImport("wtsapi32.dll", SetLastError=true)] static extern bool WTSQuerySessionInformationW(IntPtr server, int session, int info, out IntPtr value, out int bytes);
 [DllImport("wtsapi32.dll")] static extern void WTSFreeMemory(IntPtr value);
 static bool Exists(int id) {
  IntPtr rows=IntPtr.Zero; int count;
  try {
   if(!WTSEnumerateSessionsW(IntPtr.Zero, 0, 1, out rows, out count)) throw new Win32Exception(Marshal.GetLastWin32Error());
   int size=Marshal.SizeOf(typeof(Session));
   for(int index=0; index<count; index++) {
    Session row=(Session)Marshal.PtrToStructure(IntPtr.Add(rows, checked(index*size)), typeof(Session));
    if(row.Id==id) return true;
   }
   return false;
  } finally { if(rows!=IntPtr.Zero) WTSFreeMemory(rows); }
 }
 public static bool HasUser(int id) {
  if(!Exists(id)) return false;
  IntPtr value=IntPtr.Zero; int bytes;
  try {
   if(!WTSQuerySessionInformationW(IntPtr.Zero, id, 5, out value, out bytes)) {
    int error=Marshal.GetLastWin32Error();
    // Enumeration proves exact-session absence if logoff raced this query.
    if(!Exists(id)) return false;
    throw new Win32Exception(error);
   }
   if(value==IntPtr.Zero || bytes<2) throw new InvalidOperationException("invalid_wts_username");
   return !String.IsNullOrEmpty(Marshal.PtrToStringUni(value));
  } finally { if(value!=IntPtr.Zero) WTSFreeMemory(value); }
 }
}
'@
  }
  if(![CadrumoGuestLogoffSession]::HasUser($sessions[0])){throw 'dedicated_interactive_session_not_logged_on'}
  & C:\Windows\System32\logoff.exe $sessions[0]
  if($LASTEXITCODE -ne 0){throw 'native_logoff_failed'}
  $deadline=[DateTime]::UtcNow.AddSeconds(60)
  while([CadrumoGuestLogoffSession]::HasUser($sessions[0])) {
   if([DateTime]::UtcNow -ge $deadline){throw 'native_logoff_did_not_settle'}
   Start-Sleep -Milliseconds 200
  }
  @{nativeLogoff='settled';requested=$true;session=$sessions[0]}
 }
}
function Stop-GuestRdpClient {
 param([Parameter(Mandatory)]$Login)
 if($Login.container -notlike "cadrumo-rdp-$script:InvocationId-*"){throw 'foreign_rdp_client'}
 $id=(Invoke-FixtureDocker @('ps','-a','--no-trunc','--filter',"name=^/$($Login.container)$",'--format','{{.ID}}')).Trim()
 if($id) {
  $owned=(Get-Content -LiteralPath $Login.cidPath -Raw).Trim()
  if($owned -notmatch '^[a-fA-F0-9]{64}$' -or $id -ne $owned){throw 'rdp_client_kernel_custody_mismatch'}
  $labels=Invoke-FixtureDocker @('inspect','--format','{{json .Config.Labels}}',$id)|ConvertFrom-Json
  $image=(Invoke-FixtureDocker @('inspect','--format','{{.Image}}',$id)).Trim()
  if($image -ne $script:RdpImage -or $labels.'cadrumo.fixture' -ne 'runtime-lifecycle-windows-guest' -or $labels.'cadrumo.guest.uuid' -ne $script:GuestUuid){throw 'foreign_rdp_container'}
  try {Invoke-FixtureDocker @('stop','-t','10',$id) -Timeout 20|Out-Null} catch {
   $current=(Invoke-FixtureDocker @('ps','--no-trunc','--filter',"id=$id",'--format','{{.ID}}')).Trim()
   if($current) {if($current -ne $owned){throw 'foreign_rdp_container'};Invoke-FixtureDocker @('kill',$id) -Timeout 10|Out-Null}
  }
  $deadline=[DateTime]::UtcNow.AddSeconds(15)
  while((Invoke-FixtureDocker @('ps','-a','--no-trunc','--filter',"id=$id",'--format','{{.ID}}')).Trim()) {
   if([DateTime]::UtcNow -ge $deadline){throw 'rdp_container_did_not_settle'}
   Start-Sleep -Milliseconds 200
  }
 }
 if(!$Login.process.HasExited -and !$Login.process.WaitForExit(15000)){throw 'rdp_client_did_not_settle'}
 return @{client='settled';exitCode=$Login.process.ExitCode}
}
