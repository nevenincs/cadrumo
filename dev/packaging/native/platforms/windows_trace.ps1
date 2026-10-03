param(
    [Parameter(Mandatory=$true)][string]$Package,
    [string]$Output = ''
)
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path "$PSScriptRoot/../../../..").Path
$pathPython = "$repo/.venv/Scripts/python.exe"
if (-not (Test-Path -LiteralPath $pathPython)) { throw 'The project virtualenv Python is required to resolve native trace storage' }
Push-Location $repo
try {
    $storageJson = & $pathPython -B -c "from cadrumo.core.storage_environment import configured_storage_root, storage_directory, tool_storage_environment; import json; root=configured_storage_root(); print(json.dumps({'root': str(root), 'build': str(storage_directory('CADRUMO_NATIVE_BUILD_ROOT', 'development/build/native', root=root)), 'temporary': str(storage_directory('CADRUMO_TEMP_DIR', 'tmp', root=root)), 'cache': tool_storage_environment()['XDG_CACHE_HOME']}))"
    if ($LASTEXITCODE) { throw 'Native trace storage resolution failed' }
} finally {
    Pop-Location
}
$storage = $storageJson | ConvertFrom-Json
$buildRoot = [IO.Path]::GetFullPath([string]$storage.build)
$buildPrefix = $buildRoot.TrimEnd([char[]]@([IO.Path]::DirectorySeparatorChar, [IO.Path]::AltDirectorySeparatorChar)) + [IO.Path]::DirectorySeparatorChar
$explicitAbsoluteOutput = -not [string]::IsNullOrWhiteSpace($Output) -and [IO.Path]::IsPathRooted($Output)
if ([string]::IsNullOrWhiteSpace($Output)) {
    $traceRoot = Join-Path $buildRoot ("traces/trace-" + [Guid]::NewGuid().ToString('N'))
} elseif ([IO.Path]::IsPathRooted($Output)) {
    $traceRoot = [IO.Path]::GetFullPath($Output)
} else {
    $traceRoot = [IO.Path]::GetFullPath((Join-Path $buildRoot $Output))
}
$traceRoot = [IO.Path]::GetFullPath($traceRoot)
if (-not $explicitAbsoluteOutput -and (
    $traceRoot.Equals($buildRoot, [StringComparison]::OrdinalIgnoreCase) -or
    -not $traceRoot.StartsWith($buildPrefix, [StringComparison]::OrdinalIgnoreCase)
)) {
    throw 'Trace output must remain beneath CADRUMO_NATIVE_BUILD_ROOT'
}
$packagePath = (Resolve-Path -LiteralPath $Package).Path
if (Test-Path -LiteralPath $traceRoot) { throw 'Use a fresh local trace directory' }
New-Item -ItemType Directory -Force -Path $traceRoot | Out-Null
$storageNames = @('CADRUMO_STORAGE_ROOT', 'CADRUMO_LOCAL_STORAGE_ROOT', 'CADRUMO_TEMP_DIR', 'CADRUMO_TOOL_CACHE_DIR', 'TEMP', 'TMP', 'TMPDIR')
$originalStorageEnvironment = @{}
foreach ($name in $storageNames) {
    $originalStorageEnvironment[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
}
$etl = Join-Path $traceRoot 'capture.etl'
$instance = 'CadrumoNative-' + [Guid]::NewGuid().ToString('N')
$profile = Join-Path $PSScriptRoot 'windows-filesystem.wprp'
try {
    $env:CADRUMO_STORAGE_ROOT = [string]$storage.root
    $env:CADRUMO_LOCAL_STORAGE_ROOT = [string]$storage.root
    $env:CADRUMO_TEMP_DIR = [string]$storage.temporary
    $env:CADRUMO_TOOL_CACHE_DIR = [string]$storage.cache
    foreach ($name in @('TEMP', 'TMP', 'TMPDIR')) {
        [Environment]::SetEnvironmentVariable($name, [string]$storage.temporary, 'Process')
    }
    wpr -start "${profile}!CadrumoFiles" -filemode -recordtempto $traceRoot -instancename $instance
    if ($LASTEXITCODE) { throw 'WPR start failed; an elevated development shell is required' }
    try {
        $probe = @'
import json,os,subprocess,sys,tempfile
import pikepdf,pypdfium2,win32api,cryptography.hazmat.bindings._rust
from win32com.shell import shell
from win32com.client import gencache
with tempfile.NamedTemporaryFile(dir=os.environ['TEMP']) as f:
 f.write(b'cadrumo native trace')
 f.flush()
child=subprocess.check_output([sys.executable,'-c','import os,tempfile; f=tempfile.TemporaryFile(dir=os.environ["TEMP"]); f.write(b"child trace"); f.close(); print(os.getpid())'],text=True)
print(json.dumps({'pids':[os.getpid(),int(child)],'user_root':os.environ['CADRUMO_LOCAL_STORAGE_ROOT'],'cache':gencache.GetGeneratePath()}))
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
    Push-Location $repo
    try {
        & $pathPython -B -m dev.packaging.native.trace_analysis $traceRoot
    } finally {
        Pop-Location
    }
    if ($LASTEXITCODE) { throw 'Trace containment verification failed' }
} finally {
    foreach ($name in $storageNames) {
        [Environment]::SetEnvironmentVariable([string]$name, $originalStorageEnvironment[$name], 'Process')
    }
}
