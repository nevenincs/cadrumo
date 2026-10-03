param(
    [Parameter(Mandatory=$true)][string]$Package,
    [Parameter(Mandatory=$true)][string]$Output
)
$ErrorActionPreference = 'Stop'
$packagePath = (Resolve-Path -LiteralPath $Package).Path
$traceRoot = [IO.Path]::GetFullPath($Output)
if (Test-Path -LiteralPath $traceRoot) { throw 'Use a fresh local trace directory' }
New-Item -ItemType Directory -Path $traceRoot | Out-Null
$etl = Join-Path $traceRoot 'capture.etl'
$instance = 'CadrumoNative-' + [Guid]::NewGuid().ToString('N')
$profile = Join-Path $PSScriptRoot 'filesystem.wprp'
wpr -start "${profile}!CadrumoFiles" -filemode -instancename $instance
if ($LASTEXITCODE) { throw 'WPR start failed; an elevated development shell is required' }
try {
    $probe = @'
import json,os,subprocess,sys,tempfile
import pikepdf,pypdfium2,win32api,cryptography.hazmat.bindings._rust
from win32com.shell import shell
from win32com.client import gencache
with tempfile.NamedTemporaryFile() as f:
 f.write(b'cadrumo native trace')
 f.flush()
child=subprocess.check_output([sys.executable,'-c','import os,tempfile; f=tempfile.TemporaryFile(); f.write(b"child trace"); f.close(); print(os.getpid())'],text=True)
print(json.dumps({'pids':[os.getpid(),int(child)],'user_root':os.path.dirname(os.environ['CADRUMO_LOCAL_STORAGE_ROOT']),'cache':gencache.GetGeneratePath()}))
'@
    $result = & "$packagePath/python.exe" -c $probe
    if ($LASTEXITCODE) { throw 'Trace probe failed' }
    $identity = $result | ConvertFrom-Json
    $result | Set-Content -LiteralPath (Join-Path $traceRoot 'processes.json') -Encoding utf8
} finally {
    wpr -stop $etl -skipPdbGen -instancename $instance
    if ($LASTEXITCODE) { wpr -cancel -instancename $instance; throw 'WPR stop failed' }
}
tracerpt $etl -lr -o NUL -summary (Join-Path $traceRoot 'capture-summary.txt') -y | Out-Null
if ($LASTEXITCODE) { throw 'Trace summary failed' }
$selector = '*[System[Provider[@Name="Microsoft-Windows-Kernel-File"] and Execution[@ProcessID=' + $identity.pids[0] + ' or @ProcessID=' + $identity.pids[1] + ']]]'
Get-WinEvent -Path $etl -Oldest -FilterXPath $selector | ForEach-Object {
    $xml = [xml]$_.ToXml()
    $row = @{pid=$_.ProcessId; id=$_.Id; data=@{}}
    foreach($item in $xml.Event.EventData.Data) { $row.data[$item.Name] = $item.InnerText }
    $row | ConvertTo-Json -Compress -Depth 4
} | Set-Content -LiteralPath (Join-Path $traceRoot 'application-events.jsonl') -Encoding utf8
# Keep only the target processes and aggregate loss counters, not machine-wide events.
Remove-Item -LiteralPath $etl
& "$PSScriptRoot/../../../.venv/Scripts/python.exe" -m dev.packaging.native.trace_analysis $traceRoot
if ($LASTEXITCODE) { throw 'Trace containment verification failed' }
