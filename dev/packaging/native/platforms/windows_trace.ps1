param(
    [Parameter(Mandatory=$true)][string]$Package,
    [Parameter(Mandatory=$true)][string]$BuildRoot,
    [string]$Output = ''
)
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path "$PSScriptRoot/../../../..").Path
$pathPython = "$repo/.venv/Scripts/python.exe"
if (-not (Test-Path -LiteralPath $pathPython)) { throw 'The project virtualenv Python is required to validate CMake build outputs' }
Push-Location $repo
try {
    $buildJson = & $pathPython -B -c "from pathlib import Path; import json,sys; from dev.packaging.native.build_directory import require_enrolled_build; from dev.packaging.native.build_paths import build_paths; root=require_enrolled_build(Path(sys.argv[1])); paths=build_paths(root); print(json.dumps({'build': str(root), 'testing': str(paths['testing'])}))" $BuildRoot
    if ($LASTEXITCODE) { throw 'Native trace build ownership validation failed' }
} finally {
    Pop-Location
}
$build = $buildJson | ConvertFrom-Json
$buildRoot = [IO.Path]::GetFullPath([string]$build.build)
$testingRoot = [IO.Path]::GetFullPath([string]$build.testing)
$testingPrefix = $testingRoot.TrimEnd([char[]]@([IO.Path]::DirectorySeparatorChar, [IO.Path]::AltDirectorySeparatorChar)) + [IO.Path]::DirectorySeparatorChar
New-Item -ItemType Directory -Force -Path $testingRoot | Out-Null
if ([string]::IsNullOrWhiteSpace($Output)) {
    $traceRoot = Join-Path $testingRoot ("traces/trace-" + [Guid]::NewGuid().ToString('N'))
} elseif ([IO.Path]::IsPathRooted($Output)) {
    $traceRoot = [IO.Path]::GetFullPath($Output)
} else {
    $traceRoot = [IO.Path]::GetFullPath((Join-Path $testingRoot $Output))
}
$traceRoot = [IO.Path]::GetFullPath($traceRoot)
if ($traceRoot.Equals($testingRoot, [StringComparison]::OrdinalIgnoreCase) -or
    -not $traceRoot.StartsWith($testingPrefix, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Trace output must remain beneath the CMake testing output directory'
}
$relativeTrace = [IO.Path]::GetRelativePath($testingRoot, $traceRoot)
$cursor = $testingRoot
foreach ($part in ($relativeTrace -split '[\\/]')) {
    if ([string]::IsNullOrWhiteSpace($part) -or $part -eq '.') { continue }
    if ($part -eq '..') { throw 'Trace output must remain beneath the CMake testing output directory' }
    $cursor = Join-Path $cursor $part
    if (Test-Path -LiteralPath $cursor) {
        $item = Get-Item -LiteralPath $cursor -Force
        if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw 'Trace output must not use linked directories'
        }
    }
}
$packagePath = (Resolve-Path -LiteralPath $Package).Path
if (Test-Path -LiteralPath $traceRoot) { throw 'Use a fresh local trace directory' }
New-Item -ItemType Directory -Force -Path $traceRoot | Out-Null
$storageRoot = Join-Path $traceRoot 'storage'
$temporaryRoot = Join-Path $storageRoot 'tmp'
$cacheRoot = Join-Path $storageRoot 'cache'
New-Item -ItemType Directory -Force -Path $temporaryRoot, $cacheRoot | Out-Null
$storageNames = @('CADRUMO_STORAGE_ROOT', 'CADRUMO_LOCAL_STORAGE_ROOT', 'CADRUMO_TEMP_DIR', 'CADRUMO_TOOL_CACHE_DIR', 'XDG_CACHE_HOME', 'TEMP', 'TMP', 'TMPDIR')
$originalStorageEnvironment = @{}
foreach ($name in $storageNames) {
    $originalStorageEnvironment[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
}
$etl = Join-Path $traceRoot 'capture.etl'
$instance = 'CadrumoNative-' + [Guid]::NewGuid().ToString('N')
$profile = Join-Path $PSScriptRoot 'windows-filesystem.wprp'
try {
    $env:CADRUMO_STORAGE_ROOT = $storageRoot
    $env:CADRUMO_LOCAL_STORAGE_ROOT = $storageRoot
    $env:CADRUMO_TEMP_DIR = $temporaryRoot
    $env:CADRUMO_TOOL_CACHE_DIR = $cacheRoot
    $env:XDG_CACHE_HOME = $cacheRoot
    foreach ($name in @('TEMP', 'TMP', 'TMPDIR')) {
        [Environment]::SetEnvironmentVariable($name, $temporaryRoot, 'Process')
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
        & $pathPython -B -m dev.packaging.native.platforms.windows_trace_analysis --build $buildRoot $traceRoot
    } finally {
        Pop-Location
    }
    if ($LASTEXITCODE) { throw 'Trace containment verification failed' }
} finally {
    foreach ($name in $storageNames) {
        [Environment]::SetEnvironmentVariable([string]$name, $originalStorageEnvironment[$name], 'Process')
    }
}
