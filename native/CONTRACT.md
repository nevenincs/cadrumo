# Native distribution contract

Status: Windows CMake Debug/Release ZIP acceptance and Release installation pass.
Current acceptance evidence is recorded below; historical evidence is labeled separately.
Linux and macOS are mappings to
prove, not supported native builds. The existing Python product owns application
behavior. Native code owns bootstrap before Python exists.

## Source and generated ownership

| Concern | Authored owner | Generated output |
| --- | --- | --- |
| C interpreter host and CPython initialization | `native/interpreter/windows/` | `build/windows-x64/bin/<Config>/` |
| Shared Rust platform implementation and C ABI | `native/platform/` | `build/windows-x64/cargo/` |
| Rust application library and compatibility probes | `native/application/` | `build/windows-x64/cargo/<rust-target>/<profile>/` |
| Shared package declarations and physical platform mappings | `native/package-layout.json`, `native/platforms/` | `build/windows-x64/generated/` |
| Build-time contract projection | `dev/packaging/native/` | C header, Rust constants, JSON contract |
| Build graph and packaging targets | `CMakeLists.txt`, `CMakePresets.json`, `native/cmake/` | `build/windows-x64/` |
| Package assembly operations | `dev/packaging/native/` | `build/windows-x64/stage/<Config>/app/` |
| Product identity | `src/cadrumo/core/product_identity.py` | Native product identity |
| Settings names and validation | `src/cadrumo/core/config.py` | Reserved environment names |
| Storage defaults, overrides and tool locations | `src/cadrumo/core/config.py`, `storage_environment.py`, `storage_taxonomy_locations.py` | Native Settings projection |
| Exact Python version | `dev/packaging/release-python-version` | Build input |
| Third-party dependency closure | `pyproject.toml`, `uv.lock`, existing constraint exporter | Installed locked dependencies |
| Python release cohort | `dev/packaging/python_cohort.py` | Existing three-wheel cohort |

Shared packaging owns dependency installation, product wheel assembly, standard-library
ZIP creation, manifests, artifact verification dispatch and cleanup. Physical names
come from the selected `native/platforms/` contract. Windows SDK acquisition, PE
relocation, pywin32 patches, executable resources and hostile-loader tests belong to
`dev/packaging/native/platforms/windows*.py`; its native build belongs to
`native/cmake/platforms/Windows.cmake`. The Windows runtime bootstrap lives under
`native/interpreter/windows/`. Unsupported platforms fail explicitly; no Windows
mapping is silently reused for Linux or macOS.

Generated files never become an alternative authored inventory. Development
generators do not ship. Each assembly starts in a fresh directory. Runtime paths
are resolved from the executable and the canonical Settings storage contract,
never compiled from the build machine. Runtime state is separate from the
immutable application package.

Both Rust crates use the CMake Cargo command in `native/cmake/Rust.cmake` and
the selected platform adapter's compiler/linker environment. `rust_application`
participates in the default build and `bundle`; Cargo owns its incremental input
tracking, including embedded probe source. Debug and Release map to Cargo's
development and release profiles beneath the selected CMake binary directory.
The application `.rlib` is a build artifact for a Rust consumer, not a Python
extension or a runtime file to install. It does not enter the package manifest.

`verify` includes `application.rust` and `application.package` through CTest.
The package test consumes the selected layout's manifest location, checks its
complete file inventory, probes the delivered interpreter against every declared
distribution version, and checks the original inventory again. It uses a disposable
browser cache and calls the existing Python readiness owner. This checks the staged
package. `verify-package` runs both the Python acceptance suite and the CMake-selected
Rust compatibility probe against the same freshly extracted ZIP. Its result records
the archive hash, manifest hash, extracted root and application-probe outcome; a failed
Rust probe prevents a passing result. The staged-package override does not redirect
this artifact check.
For a separately extracted or installed artifact, configure the absolute
`CADRUMO_APPLICATION_TEST_PACKAGE_ROOT` and run
`ctest -C Release -R "^application\." --output-on-failure` in that build directory. This verifies that
selected artifact and does not establish a successful fresh `bundle` build.

## Platform mappings

`P` means installed package root; `U` means the effective storage root selected
by the existing Settings contract. OS-specific delivered-user defaults remain a
storage-owner integration obligation; this interpreter does not invent them.

| Location | Windows x64 proof target | Linux mapping, unimplemented | macOS mapping, deferred |
| --- | --- | --- | --- |
| Executables | `P/python.exe`, future `P/cadrumo.exe`; components in `P/bin/` | Private prefix `P/bin/`; system command wrappers depend on packaging format | `Cadrumo.app/Contents/MacOS/` |
| Python | `P/python.zip`; dependencies in `P/cadrumo/site-packages/`; controlled `P/cadrumo/python.pth` | Private `P/lib/cadrumo/python.zip` and site-packages | `Contents/Resources/python.zip` and site-packages |
| Native modules/libraries | `P/bin/`, qualified extensions beneath `bin/packages/` | Private `P/lib/`; extension identities retained | `Contents/Frameworks/`, extension package subtrees |
| Immutable resources | `P/data/`, `P/docs/` | `P/share/cadrumo/` | `Contents/Resources/data/` and `docs/` |
| Mutable root | Canonical Settings override or repository-local default; supplied explicitly for delivered-artifact tests | Same logical Settings owner; delivery default pending | Same logical Settings owner; delivery default deferred |
| Secure state | Existing Settings/taxonomy beneath the selected root | Same logical owner | Same logical owner |
| Loader | Static bootstrap CRT; explicit absolute DLL load with restricted search, then registered bundle directories | Relative ELF RUNPATH for every transitive dependency; audit LD_* and libc floor | Relative install names and rpaths; signing and hardened-runtime validation |

Linux deb/rpm, relocatable archive and AppImage are unresolved alternatives.
No build target or placeholder implementation claims those formats work.
macOS needs a native toolchain, architecture selection, codesigning and dyld proof.
Windows relocation passed real package-qualified extensions and transitive-DLL
artifact tests, including public pywin32 COM imports and pikepdf/qpdf.
Library-owned resources retain their wheel locations; assembly projects the
application authority into `data/authority` through its existing setting.

## Bootstrap and ABI

The host uses CPython 3.13's full initialization API, not the Limited API.
Headers, import library and runtime must be one exact build. The executable
does not import Python before `main`: it configures DLL lookup and explicitly
loads the bundled runtime. Python initialization lives in a private bridge DLL.
Upstream CPython behavior is retained through `PyConfig` and `Py_RunMain`.

The Rust platform provider is the sole native path/environment policy owner.
Its versioned C ABI uses fixed-width status and length fields, UTF-8 strings,
opaque context pointers, provider-owned buffers and a provider release function.
No Rust object, exception or allocator ownership crosses the ABI. Consumers check
the ABI before creating a context. Both C linkage consumers passed; delivery uses
static linkage so platform loading needs no application DLL before main. Static
copies share code policy, not process state.

The interpreter excludes environment-derived Python paths, virtualenv discovery,
user site, automatic current-directory imports, sitecustomize and executable `.pth`
files. Necessary wheel path additions must be generated from inspected package
metadata. `-m`, `-c`, scripts, stdin and child startup use the bundled executable.
The caller's working directory is retained for explicit script/file arguments;
it is not an implicit import root. This is environment isolation, not a sandbox.

## Mutable data and reconciliation

The native bootstrap projects canonical storage environment names and defaults.
Python continues to own bucket routing, encryption, authorization and member
defaults. Repository-local defaults and explicitly supplied storage overrides are
preserved; no LocalAppData policy is introduced. Existing local storage is outside this foundation's scope. The
host neither inspects nor migrates it; rollout transition policy remains deferred.

Package-only anchors are declared once. Existing taxonomy members remain owned
by Python and are projected at build time. The native host clears inherited Python
configuration and reserved Settings except the storage override allowlist generated
by `Settings.storage_env_var_names()`. Package-owned `CADRUMO_EXTERNAL_BIN_DIRS`
accepts existing absolute directories for external executables. These directories
affect child-process PATH, not DLL search. No development environment template is
copied into the package.

Temporary and cache locations follow the canonical storage declarations. Managed browsers,
model services, WebView profiles, exports and update staging require later owner
integration and write tracing; setting environment variables alone does not prove
their containment. OS-maintained logs, crash dumps and external browsers remain
outside the application's filesystem policy.

## Repeatable Windows commands

Run from the repository using its development environment. `native/toolchain.json`
pins MSVC, SDK, Rust, CMake and the SHA256 of the official CPython NuGet SDK. The
Python version comes from the existing release pin. Provisioning downloads that
SDK and the locked base dependency closure; optional integrations remain outside
this base package. The C host is compiled locally; CPython is the official binary
build, with matching headers and import library. No CPython source patch is applied.

```text
cmake --preset windows-x64
cmake --build --preset release
cmake --build --preset release --target verify
cmake --build --preset debug --target python_d
cmake --install build/windows-x64 --config Release --prefix "Y:/cadrumo-proof/CADRUMO espacio á 漢字"
cmake --build --preset package-release
cmake --build --preset release --target verify-package
```

CMake owns the build graph. Python helpers perform portable filesystem and wheel
operations; PowerShell is not part of the build. The separate Windows `platforms/windows_trace.ps1`
helper is an OS diagnostics tool. Linux/macOS compilation remains unimplemented.
Toolchain selection is scoped by `native/cmake/WindowsToolchain.cmake`; Cargo gets
explicit compiler-library and linker paths without changing the caller's shell.

### Names, artifacts and targets

`<Config>` is exactly `Debug` or `Release`. The default binary directory is
`build/windows-x64`. Production is `python.exe`; the distinct development host is
always `python_d.exe`. Both use the pinned release CPython ABI and locked wheels.
Debug controls compiler optimization/symbols; `_d` identifies the development host,
not a CPython debug ABI. The `python_d` target always exists and is excluded from
the default build. Set `-DCADRUMO_INCLUDE_DEVELOPMENT_BINARY=ON` at configure time
to include it alongside production in the same package; shipping it is optional.

| Path beneath the binary directory | Contents |
| --- | --- |
| `_deps/runtime/` | Verified CPython SDK and locked third-party wheels installed for staging |
| `_deps/build-tools/` | Pinned SVG renderer; never shipped |
| `product/build/wheels/` | Existing CADRUMO three-wheel cohort built from source |
| `product/dependencies/` | Exact production closure plus those product wheels |
| `generated/` | Native contracts, metadata, icon and resource source |
| `bin/<Config>/`, `lib/<Config>/`, `symbols/<Config>/` | Native executables/DLLs, import libraries and symbols |
| `cargo/` | Rust build products |
| `tmp/` | Preset-scoped compiler and MSBuild scratch files; retained during cleanup targets because MSBuild can still be using them |
| `stage/<Config>/app/` | Complete application tree used by install and CPack |
| `install/` | Default local install prefix; override with `cmake --install --prefix` |
| `packages/<Config>/` | ZIP artifacts |
| `testing/<Config>/`, `verification/<Config>/` | Test state and extracted-artifact evidence |

ZIP names are `CADRUMO-<version>-b<build>-windows-x64-<Config>.zip`, with one
matching top-level folder. `CADRUMO_BUILD_NUMBER` defaults to the Git commit count;
`CADRUMO_BUILD_DATE` is a cached UTC configure timestamp, respecting
`SOURCE_DATE_EPOCH`. CI may explicitly supply both. The version belongs to
`pyproject.toml`. The executable banner, Windows version/icon resources and
`data/build.json` carry the same identity. The icon derives from the existing
`docs/_static/cadrumo-favicon.svg`.

The Windows preset scopes `TEMP`, `TMP` and `TMPDIR` to its build tree before
compiler discovery and builds. The host embeds a long-path-aware Windows manifest
so deeply nested product resources remain readable after Unicode/path relocation.

| Target | Operation |
| --- | --- |
| default / `bundle` | Build native host, product wheels and complete staged package |
| `python`, `python_d` | Compile production or development host and bridge |
| `python_dependencies` | Provision the pinned runtime and locked binary dependencies |
| `python_product` | Build and install the CADRUMO wheel cohort into dependency staging |
| `verify` | Build bundle/ABI consumers, run CTest including real dependency imports |
| `install` / `cmake --install` | Copy staged package to the chosen prefix |
| `package` / `zip` | CPack ZIP delivery; no native installer yet |
| `verify-package` | Build ZIP, extract into a Unicode/spaces path, run cohesion and runtime probes |
| `clean` | Generator's standard build-output cleanup |
| `clean-stage` | Remove stage, testing and verification trees |
| `clean-packages` | Remove ZIP and CPack staging trees |
| `clean-dependencies` | Remove downloaded SDK/dependencies and product wheel staging |
| `clean-native` | Remove bin, lib, symbols, Cargo and generated contracts/resources |
| `clean-all` | Apply all four bounded cleanup groups; retain CMake configuration |

Explicit cleanup never removes source files, the installed application or an
arbitrary path. It validates the CMake source owner and each resolved child path.
Shared provisioning and product actions record input fingerprints and output inventories
so switching configurations can reuse them. Selected authority and wheel metadata
inputs participate in the product dependency graph. Do not run independent builds
or cleanup concurrently in the same binary directory.
A subsequent build regenerates removed prerequisites. Run build before
`cmake --install`; that command copies an already assembled tree.

CPack writes each configuration's artifact locator after creating its archive.
The locator records archive and manifest SHA256 hashes and the development-host
presence from that package. Reconfiguring CMake leaves existing locators unchanged.
ZIP verification rejects a replaced archive before clearing previous acceptance
output and records the exact hashes tested. These hashes establish integrity,
not publisher authentication.

### Runtime library and cohesion

`python.zip` contains compiled standard-library modules and runtime resources.
Tests, GUI demos, tkinter/IDLE, ensurepip and SDK development directories do not
ship. The remaining runtime stdlib is retained because application imports can be
dynamic. Only the locked base third-party dependency closure and the three CADRUMO
wheels enter `cadrumo/site-packages/`; development and optional extras are excluded.
`Lib`, `Libs`, `Scripts`, headers and import libraries stay in build inputs. Native
extensions and their libraries are relocated under `bin/` with qualified module
names recorded in `data/native-modules.json`.

The platform contract explicitly removes Pillow's unused `ImageTk.py` and
`_imagingtk` extension alongside the excluded Tk standard library. The assembler
requires these exclusions to match and records each removed file, hash and reason
in the package manifest. Every retained native module is imported by the smoke test.

`cadrumo/python.pth` is generated data: only reviewed package-relative directories
are allowed, matching the native manifest. `site` does not execute arbitrary `.pth`
files. Startup checks build identity, file presence and essential file hashes;
`python.exe --check-package` hashes the whole package and rejects extra files.
This detects missing, damaged or mixed artifacts; it is not an authenticated
signature or a sandbox for Python code.

The product step takes a stable snapshot through existing source-tree helpers,
stages the selected published authority, and runs the existing wheel build hooks
for all three product distributions. The hook verifies authority currency and
publishes a current snapshot generation when necessary. It then installs all three
matching wheels into dependency staging. This Windows development build is not a
sealed release-cohort promotion; the cross-platform release lane remains separate.
The assembler relocates that authority once to `data/authority`. Neither runtime
startup nor the native assembler compiles it.

The generated extension map retains qualified module names. pywin32's three
path directives become explicit import paths, and its two extension DLLs receive
ordinary extension specs; its executable `.pth` directive is not run. PDFium's
generated ctypes loader receives one checked replacement of its library location.
The pywin32 package receives one checked replacement of registry environment setup
with bundled COM extension paths and `U/cache/pywin32/gen_py`. Qualified
`win32com.*` extension aliases follow its public import surface. Both patches are
recorded with before/after hashes in `data/package-manifest.json`. The assembler
refuses unreviewed `.pth` files and conflicting DLL basenames. Installed wheel
RECORD locations describe original wheel contents; the package manifest owns the
assembled file inventory and hashes. This foundation does not support pip mutation
of the installed package.

Windows PE import tables identify extensions used as transitive libraries, such as
`axscript.pyd`. Their directories join DLL search and their basenames must be
unambiguous. Ordinary package-qualified extensions load by absolute path and may
share a basename, as SQLAlchemy's two `_util_cy` extensions do. Smoke tests import
both the CPython SDK extensions and every retained third-party extension identity.

## Current CMake verification, 2026-10-03

The current Debug CMake `verify-package` target passed with both `python.exe` and
`python_d.exe` in the extracted ZIP. Each passed build identity, role, full package
cohesion, production imports, child identity and explicit binary-override probes.
The subsequent hostile-environment suite passed. CTest passed all four tests in
both Debug and Release, including C static/DLL and Rust ABI consumers.

The production-only Release ZIP also passed the full acceptance suite. Each
configuration's `verification/<Config>/result.json` records its archive and
manifest hashes, build identity and tested interpreter names. Both locators
remain unchanged after a subsequent CMake configuration.

The smoke test imports 119 native identities and checks all 80 installed
distributions: 77 locked third-party distributions and the three CADRUMO 0.5.1
wheels. The product wheel build uses existing authority validation. Publication
locks, transaction descriptors and temporary export staging/backup directories do
not enter the source snapshot or dependency fingerprints. Compiler code and source
normalization rules participate in CMake invalidation.

`cmake --install` produced the outside-checkout installation
`Y:/code/cadrumo-native-proof/CADRUMO final á 漢字`. Its full cohesion and dependency
smoke checks passed from an unrelated working directory. A separate hostile-input
copy passed CLI startup, child startup, Python environment conflicts, missing and
invalid dependencies, native search conflicts, ignored executable `.pth` and
unchanged installed hashes. Evidence is
`build/windows-x64/verification/Release/verification.json`.

The current installed interpreter and child passed Windows kernel-file tracing:
71,288 scoped events, four writes, zero lost events, all observed mutations beneath
the declared user root. Evidence is
`Y:/code/cadrumo-native-proof/final-release-trace/summary.json` and
`application-events.jsonl`. The raw capture was removed. The Windows profile uses
nonpaged buffers and an executable-name filter, then retains only the tested PIDs;
see [Microsoft's WPR filtering guidance](https://devblogs.microsoft.com/performance-diagnostics/filtering-events-using-wpr/).
An earlier capture with lost events was rejected. This proves the exercised
parent/child probe, not arbitrary Python containment or every application workflow.

Five named cleanup targets passed in a separate configured proof tree, retaining
configuration and unrelated files. In-source configuration is refused before
compiler/scratch setup. The two existing storage-projection tests, Ruff and ty pass.
The final Release installation's manifest matches the verified Release ZIP.
The authored Windows long-path manifest is included in source snapshots through
an explicit ignore-rule exception. Archive replacement refusal has a focused
regression test; reconfiguration preserves both archive locators.

## Historical artifact evidence, prior layout

Evidence below belongs to the compiled Known Folder bootstrap. Its native source
is preserved in `.artifacts/native/repeatable/product/source/native/`, with its
generator in that snapshot's `dev/packaging/native/`. Later concurrent edits to
the working-tree platform provider select repository/cwd defaults and preserve
storage overrides. The commands above must be revalidated against that policy
before the current source can claim the same results. No concurrent edits were
reverted to manufacture a matching tree.

The fresh provision/product/assemble flow produced
`.artifacts/native/repeatable/package/python.exe`, with 77 locked third-party
distributions and CADRUMO's three matching 0.5.1 product wheels. Verification ran
from `C:/Users/hello/cadrumo-native-proof/CADRUMO fresh á 漢字`, outside the checkout.
`.artifacts/native/verification.json` records native/pure imports, PDF operations,
product metadata and authority, CLI startup, child identity, hostile Python settings
and DLLs, missing/invalid dependencies, ignored `.pth`, and unchanged package hashes.

The repeatable WPR trace captured 2,013 parent/child filesystem events with four
actual file writes and zero lost events. All observed file mutations were under
the declared user root. Scoped evidence is
`C:/Users/hello/cadrumo-native-proof/repeatable-trace/summary.json` and
`application-events.jsonl` in that directory. The helper requires nonpaged trace
buffers, checks final event loss, refuses unresolved write paths, and removes the
machine-wide capture after extracting target-process events. Its profile covers
file creation, writes, set-information, deletion, rename/link, security and extended
attribute changes. This measures the import/tempfile/COM-cache probe and its child;
it does not claim containment of every future application workflow.

Linux needs its format, libc floor and transitive ELF loader proof. macOS needs
native compilation, architecture and signing decisions, dyld proof and compatible
wheels (the current all-platform exporter cannot obtain the pinned pikepdf wheel).
Neither platform has a native interpreter backend here. Rebuilding CPython itself from source,
release signing and sealed cross-platform cohort promotion are also later work.

## Native distribution definitions

`native/cmake/distribution` packages an already assembled payload. Its shared
identity projection covers Windows x64, Linux x64/ARM64 and macOS ARM64. The
application ID is `md.neve.cadrumo`; the preview channel adds `.preview`. Upgrade
UUIDs are deterministic per application/channel, target and machine installation
scope. They do not change with the version. MSI product/package codes retain their
separate release lifetimes. Publisher, license, version and names come from the
existing Python product and project metadata owners.

Configure with CMake 4.4.3, `-S native/cmake/distribution`, a fresh `-B` directory,
`-DCADRUMO_TARGET=<canonical-target>` and `-DCADRUMO_PAYLOAD=<absolute-payload>`.
Set `CADRUMO_DEV_PYTHON` explicitly when the checkout's development interpreter is
not available. `CADRUMO_CHANNEL` selects `stable` or `preview`. An optional
`CADRUMO_DESKTOP_EXECUTABLE` must name an actual file in the hashed payload
inventory; only that entrypoint receives desktop registration. macOS requires a
root-level desktop executable. Its runtime backend and WebView containment proof
must be completed before a macOS application release.

CPack definitions select MSI/ZIP on Windows, DEB/RPM/TGZ on Linux, and DMG/TGZ on
macOS. Run `cpack --config <build>/CPackConfig.cmake -G <generator>` on the native
packaging host. WiX .NET tooling and its matching UI extension are prerequisites
for MSI; current WiX 7 also requires operator acceptance of its OSMF EULA. CPack's
`CPACK_WIX_VERSION=4` selects the WiX XML/tool interface, not a claim that WiX 4
is the latest release. Set `CPACK_WIX_PRODUCT_ICON` to the generated product ICO
when producing the Windows installer. DEB requires dpkg tooling; RPM requires
rpmbuild. Signing, notarization and native launch/upgrade tests remain release gates.

MSI installs under Program Files/CADRUMO/app and owns Start menu/uninstall
registration. Linux installs under `/opt/cadrumo` with desktop/icon registrations
under `/usr/share`. Preview uses separate names. macOS packages a CADRUMO.app
bundle for the Applications folder. Runtime storage remains owned by Settings;
these definitions add no services, scheduled tasks or automatic launch.

For development, `cmake --install <build> --prefix <absolute-test-prefix>` uses
relative installation definitions. Set `CADRUMO_UNINSTALL_PREFIX` to that exact
prefix, then build the `uninstall` target. The external `installation.json`
receipt binds removal to the installed package manifest and unchanged file hashes.
Changed files and unowned content remain. Symlink/junction traversal and filesystem
root removal are refused. Native package managers own uninstall for system packages;
the prefix helper is for isolated development installations.
