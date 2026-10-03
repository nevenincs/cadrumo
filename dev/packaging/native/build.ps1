param(
    [Parameter(Mandatory=$true)][string]$CPythonRoot,
    [string]$RustRoot = '',
    [string]$Output = '.artifacts/native'
)
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path "$PSScriptRoot/../../..").Path
$out = [IO.Path]::GetFullPath($Output, $repo)
$pythonRoot = (Resolve-Path -LiteralPath $CPythonRoot).Path
$pin = (Get-Content -LiteralPath "$repo/dev/packaging/release-python-version" -Raw).Trim()
$pins = Get-Content -LiteralPath "$repo/native/toolchain.json" -Raw | ConvertFrom-Json
if (-not $RustRoot) { $RustRoot = "$env:USERPROFILE/.rustup/toolchains/$($pins.rust)-$($pins.rust_target)" }
$actual = & "$pythonRoot/python.exe" -I -c 'import platform; print(platform.python_version())'
if ($actual -ne $pin) { throw "Expected CPython $pin, got $actual" }
$vswhere = "${env:ProgramFiles(x86)}/Microsoft Visual Studio/Installer/vswhere.exe"
$vs = & $vswhere -version '[17.0,18.0)' -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
if (-not $vs) { throw 'Visual Studio 2022 C++ tools are required' }
$toolset = $pins.msvc
$sdk = $pins.windows_sdk
if (-not (Test-Path -LiteralPath "$vs/VC/Tools/MSVC/$toolset")) { throw "Missing MSVC $toolset" }
$originalPath = $env:PATH
$originalRustc = $env:RUSTC
$originalFlags = $env:RUSTFLAGS
$originalContract = $env:CADRUMO_CONTRACT_RS
try {
    $env:PATH = "$RustRoot/bin;$vs/VC/Tools/MSVC/$toolset/bin/Hostx64/x64;$env:PATH"
    $env:RUSTC = "$RustRoot/bin/rustc.exe"
    if (-not ((& $env:RUSTC --version).StartsWith("rustc $($pins.rust) "))) { throw "Rust $($pins.rust) required" }
    if (-not ((& cmake --version)[0] -eq "cmake version $($pins.cmake)")) { throw "CMake $($pins.cmake) required" }
    & "$repo/.venv/Scripts/python.exe" -m dev.packaging.native.generate "$out/generated"
    if ($LASTEXITCODE) { throw 'Contract generation failed' }
    $env:CADRUMO_CONTRACT_RS = "$out/generated/contract.rs"
    $env:RUSTFLAGS = '-C target-feature=+crt-static'
    & "$RustRoot/bin/cargo.exe" build --locked --manifest-path "$repo/native/platform/Cargo.toml" --release --target $pins.rust_target --target-dir "$out/cargo"
    if ($LASTEXITCODE) { throw 'Rust platform build failed' }
    $platform = "$out/cargo/x86_64-pc-windows-msvc/release"
    & cmake -S "$repo/native" -B "$out/build" -G 'Visual Studio 17 2022' -A x64 -T "version=$toolset" "-DCMAKE_SYSTEM_VERSION=$sdk" "-DCMAKE_GENERATOR_INSTANCE=$vs" "-DCPYTHON_ROOT=$pythonRoot" "-DCONTRACT_DIR=$out/generated" "-DPLATFORM_LIB=$platform/cadrumo_platform.lib" "-DPLATFORM_DLL_LIB=$platform/cadrumo_platform.dll.lib"
    if ($LASTEXITCODE) { throw 'CMake configure failed' }
    & cmake --build "$out/build" --config Release
    if ($LASTEXITCODE) { throw 'C host build failed' }
    Copy-Item -LiteralPath "$platform/cadrumo_platform.dll" -Destination "$out/build/Release/"
    foreach ($consumer in @("$out/build/Release/platform_static_consumer.exe", "$out/build/Release/platform_dll_consumer.exe", "$platform/platform-consumer.exe")) {
        & $consumer
        if ($LASTEXITCODE) { throw "ABI consumer failed: $consumer" }
    }
} finally {
    $env:PATH = $originalPath
    $env:RUSTC = $originalRustc
    $env:RUSTFLAGS = $originalFlags
    $env:CADRUMO_CONTRACT_RS = $originalContract
}
