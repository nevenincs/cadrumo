# Native distribution contract

CMake defines compilation, installation and ZIP packaging.
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
| Bundled user documentation | `docs/` and its `dev/docs/` build driver; language set in `native/package-layout.json` | `build/windows-x64/user-docs/` |

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

| Location | Windows x64 | Linux mapping, unimplemented | macOS mapping, deferred |
| --- | --- | --- | --- |
| Executables | `P/python.exe`, future `P/cadrumo.exe`; console entrypoints such as `P/bin/cadrumo-runtime.exe` and components in `P/bin/` | Private prefix `P/bin/`; system command wrappers depend on packaging format | `Cadrumo.app/Contents/MacOS/` |
| Python | `P/python.zip`; dependencies in `P/cadrumo/site-packages/`; controlled `P/cadrumo/python.pth` | Private `P/lib/cadrumo/python.zip` and site-packages | `Contents/Resources/python.zip` and site-packages |
| Native modules/libraries | `P/bin/`, qualified extensions beneath `bin/packages/` | Private `P/lib/`; extension identities retained | `Contents/Frameworks/`, extension package subtrees |
| Immutable resources | `P/data/`, `P/docs/` | `P/share/cadrumo/` | `Contents/Resources/data/` and `docs/` |
| Mutable root | Canonical Settings override or repository-local default; supplied explicitly for delivered-artifact tests | Same logical Settings owner; delivery default pending | Same logical Settings owner; delivery default deferred |
| Secure state | Existing Settings/taxonomy beneath the selected root | Same logical owner | Same logical owner |
| Loader | Static bootstrap CRT; explicit absolute DLL load with restricted search, then registered bundle directories | Relative ELF RUNPATH for every transitive dependency; audit LD_* and libc floor | Relative install names and rpaths; signing and hardened-runtime validation |

Linux deb/rpm, relocatable archive and AppImage are unresolved alternatives.
No build target or placeholder implementation claims those formats work.
macOS needs a native toolchain, architecture selection, codesigning and dyld validation.
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

### Console entrypoints

`native/package-layout.json` names the console scripts that ship as native
executables, with their version-resource descriptions. Each name must be a
`[project.scripts]` entry in `pyproject.toml`; the layout loader refuses any
other. The platform mapping supplies the executable suffix. CMake compiles
the same host source once per entrypoint with the script name fixed at
compile time, so `cadrumo-runtime.exe` cannot be redirected to other code by
its arguments. Entrypoints ship in the native directory, for example
`P/bin/cadrumo-runtime.exe`. The generated contract lists their file names; the
platform library maps a declared entrypoint image in `P/bin/` back to `P` and
refuses one found anywhere else. Every other image, including `python.exe` and
the desktop `cadrumo.exe`, keeps the package root as its own directory. Because
`P/bin/` also holds the bundled DLLs, every host links with
`/DEPENDENTLOADFLAG:0x800` so its load-time imports resolve from System32, and
assembly refuses a bundled DLL whose name matches a host import.

An entrypoint host performs the same platform preparation, loader setup and
isolated initialization as `python.exe`, then runs the installed console
script through `_cadrumo_bootstrap.run_entrypoint`. All arguments pass to the
script; the host intercepts none. `sys.executable` remains `python.exe`,
because runtime workers and the supervised KDF child relaunch it with
interpreter arguments. Entrypoint executables are startup files, hashed by the
package bootstrap before application code runs. CTest checks each staged entrypoint's
usage output. Product ZIP verification forwards help and an unknown option
through each entrypoint, refuses a copy displaced to the package root, then starts `cadrumo-runtime.exe` against an isolated
storage root with hostile Python variables and completes the verified runtime
handshake with the runtime's exact process image. The probe stops the runtime
through its process scope; it registers no service and leaves no process.

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
cmake --install build/windows-x64 --config Release
cmake --build --preset package-release
cmake --build --preset release --target verify-package
```

`native/cmake/BuildPaths.cmake` owns build output directories and cleanup
groups. CMake writes `build-paths.json` in the binary directory; Python helpers
consume it without fallback directory definitions. Test fixtures use the test
runner's temporary storage. Every build output must have a declared CMake owner, output path and generation
target or configure operation. Undeclared generation is a build defect. Names
describe artifact function, platform and configuration. Development-status labels
are prohibited. Build directories contain
only declared build products and tool-managed intermediate files.

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
| `user-docs/build/`, `user-docs/work/` | Documentation owner build roots per language, with their logs and private storage |
| `user-docs/stage/` | Shippable documentation subset and its manifest, copied into each staged package |

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
Both hosts embed `interpreter/windows/host.manifest` directly as process resource
1, including Windows 10 compatibility and `asInvoker` privileges. Linker manifest
generation is disabled; a post-link check rejects any source/resource byte
divergence before staging. ZIP acceptance also checks the reported Windows version.

| Target | Operation |
| --- | --- |
| default / `bundle` | Build native host, product wheels and complete staged package |
| `python`, `python_d` | Compile production or development host and bridge |
| `cadrumo_entrypoint_<name>` | Compile one declared console entrypoint host, such as `cadrumo-runtime.exe` |
| `python_dependencies` | Provision the pinned runtime and locked binary dependencies |
| `python_product` | Build and install the CADRUMO wheel cohort into dependency staging |
| `user_docs` | Build every declared documentation language and stage the shippable subset; a `bundle` prerequisite unless `CADRUMO_PACKAGE_USER_DOCS=OFF` |
| `verify` | Build bundle/ABI consumers, run CTest including real dependency imports |
| `install` / `cmake --install` | Copy staged package to the chosen prefix |
| `package` / `zip` | CPack ZIP delivery; no native installer yet |
| `verify-package` | Build ZIP, extract into a Unicode/spaces path, run cohesion and runtime probes |
| `clean` | Generator's standard build-output cleanup |
| `clean-stage` | Remove stage, testing and verification trees |
| `clean-packages` | Remove ZIP and CPack staging trees |
| `clean-dependencies` | Remove downloaded SDK/dependencies and product wheel staging |
| `clean-native` | Remove bin, lib, symbols and Cargo outputs; retain configure metadata |
| `clean-desktop` | Remove declared desktop build outputs and test state |
| `clean-docs` | Remove documentation build roots, work state and the staged subset |
| `clean-all` | Apply the declared bounded cleanup groups; retain CMake configuration |

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
`python.exe --check-package` hashes the whole package, including delegated
inventories, and rejects extra files.
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

### Bundled user documentation

`native/package-layout.json` declares the bundled user documentation under
`user_docs`: its directory beneath `paths.docs`, the manifest name, the entry and
search files of each language, and the language set. Each language must be one of
the product's output languages, and English must be declared. `native/cmake/Docs.cmake`
defines the `user_docs` target for the source build and the standalone desktop
project; `bundle` and `desktop-host-build` depend on it.

`dev/packaging/native/docs_build.py` runs the documentation owner's build command
once per declared language, in parallel, as a user-scope build from a private source
copy. `CADRUMO_DOCS_BUILD_ROOT` points the owner's path API at `user-docs/build/`,
so each root lands in `user-docs/build/html/<lang>/`. Ambient `CADRUMO_DOCS_*`
settings are dropped, each root gets its own storage root, and the Pagefind contract
is pinned to `full`. The cli-sequence golden check runs on exactly the first declared
root; the other roots use the owner's documented opt-out. The step fingerprints the
contents of `inputs-user-docs.txt`: documentation sources, documentation tooling,
`src/`, the layout and the selected published authority. Unchanged inputs reuse the
previous roots. A stale published authority fails the target, and the owner's refusal
is printed as the `cause:` line. Each root's previous search index is removed before
its build, so staging can never accept an older root after a failed build.

`dev/packaging/native/docs_stage.py` stages the published site layout: English at
`P/docs/user/` and every other language at `P/docs/user/<lang>/`, where the owner's
language switcher links. Sphinx build state (`.doctrees`, `.buildinfo`, `_sources`)
and site-language directories nested in a source root are not copied. Staging refuses
a language without its entry page or Pagefind module, a linked source entry, a
non-portable path, a `script`, `link`, `img`, `source`, `iframe`, `embed`, `object`,
`audio`, `video` or `track` resource that names an `http:`, `https:` or
protocol-relative URL, an inline event-handler attribute and a `javascript:` URL.
Each refusal names the reference, its page count and the first page.

`P/docs/user/manifest.json` is the documentation handler's input:

| Field | Meaning |
| --- | --- |
| `schema` | Manifest schema, currently `1` |
| `languages` | Declared languages, in declared order |
| `apex_language` | Language served at the documentation root, `en` |
| `entries` | Entry page per language relative to `P/docs/user/`, such as `index.html` and `es/index.html` |
| `search` | Pagefind module per language, such as `pagefind/pagefind.js` and `es/pagefind/pagefind.js` |
| `script_hashes` | CSP `sha256-<base64>` values of every executing inline `<script>`, hashed after HTML newline normalization; inert types such as `application/json` are omitted |
| `files` | Every servable file relative to `P/docs/user/`, with its SHA-256; the manifest does not list itself |

The handler is to serve only `files` members, check their digests and derive the
documentation origin's CSP from `script_hashes`. It is not implemented yet. The
desktop shell CSP in `src-tauri/tauri.conf.json.in` does not govern the documentation.

The package manifest does not list each documentation file. It lists
`docs/user/manifest.json` with its hash and declares
`delegated_inventories: {"docs/user": "docs/user/manifest.json"}`, so interpreter
startup checks only the package's own files. `python.exe --check-package`, payload
validation and the Rust package inspection hash the delegated manifest before using
it, merge its entries strictly beneath `docs/user/`, refuse an entry that escapes the
prefix or collides with a listed package file, hash every merged file and reject
unlisted files. Startup files never belong to a delegated inventory. Assembly in a
binary directory configured before this dependency existed stops with a reconfigure
instruction.

The package manifest also states `user_docs: {"directory": "docs/user", "bundled": ...}`.
`CADRUMO_PACKAGE_USER_DOCS` (default `ON`) selects whether `bundle` depends on
`user_docs`, and configure prints the active mode. With `OFF` the package has no
`docs/user/` tree and no documentation inventory, and states `"bundled": false`.
Full checks accept the missing tree only because of that statement and refuse a
statement that disagrees with the inventory or is absent. Payload validation refuses
a desktop executable from a package without bundled documentation. The desktop
project always depends on `user_docs`.

## Native distribution definitions

`native/cmake/distribution` packages an already assembled payload. Its shared
identity projection covers Windows x64, Linux x64/ARM64 and macOS ARM64. The
## Desktop single instance

The desktop GUI holds one lock per user and channel, across installed versions and
install paths. The names and the protocol below are a cross-version contract: a
version that changed them would take a separate lock, and two versions could open
windows at once. The headless CLI passthrough (`cadrumo` with arguments, or
`--headless`) never opens these objects.

`<family>` is the application identifier of the generated Tauri configuration: the
identity projection's `application_id` with its channel suffix, such as
`md.neve.cadrumo` or `md.neve.cadrumo.preview`. Neither the version nor the install
path enters a name. `native/platform/src/desktop.rs` implements the Windows side and
`native/desktop/src-tauri/src/shell/single_instance/` the Linux side and the
desktop's use of both.

On Windows, `<base>` is `Global\<family>.desktop.<SID>`, where `<SID>` is the string
form of the process token user's SID. Named mutexes and events in `Global\` need no
`SeCreateGlobalPrivilege`.

| Object | Name | Created by |
| --- | --- | --- |
| Lock | `<base>.lock`, a mutex | Every claimant, creating or opening it |
| Activation | `<base>.session.<N>.activate`, an auto-reset event | The holder only; `<N>` is its session ID |
| Acknowledgement | `<base>.session.<N>.acknowledge`, an auto-reset event | The holder only |

- Every object is created with the security descriptor `O:<SID>D:P(A;;GA;;;<SID>)`.
  A claimant refuses an object it cannot open with full access, or whose owner is
  not its token user.
- The holder is the thread whose zero-timeout wait on the lock returned
  `WAIT_OBJECT_0` or `WAIT_ABANDONED`. It then creates its session's two events,
  resets both, and keeps the lock until its window has closed.
- A claimant in session `N` that finds the lock held opens, without creating, its
  own session's two events. When they exist it sets the activation event and waits
  up to 500 ms for the acknowledgement; an acknowledgement means the window was
  activated, and the claimant exits with 0. Without one it checks the lock again.
- When the lock is held and the claimant's session has no activation event for
  500 ms, the holder is in another session. The claimant sets nothing, writes
  `{"outcome":"open_in_other_session"}` as one line on standard error and exits
  with 0.
- The holder acknowledges only a request it accepted. Once its window is closing it
  stops acknowledging, so claimants keep checking until the lock is released. A
  claimant gives up after 10 s with a `timed_out` launch error.
- Events have no content: a request carries nothing from the claimant.

On Linux the objects live in `$XDG_RUNTIME_DIR`, which must deny group and other
access.

| Object | Name |
| --- | --- |
| Lock | `<family>.desktop.lock`, held with an exclusive `flock` |
| Activation | `<family>.desktop.session.<session>.activate`, a Unix stream socket the holder binds |

- `<session>` is `XDG_SESSION_ID`, or `unnamed` when it is unset. It is letters,
  digits, `-` and `_`.
- On taking the lock, the holder removes every
  `<family>.desktop.session.*.activate` socket, then binds its own.
- A claimant connects to its own session's socket and writes nothing. The holder
  reads nothing and writes the byte `0x01` for a request it accepted. Timing, the
  other-session report and the exit status match Windows; a socket that is missing
  or refuses the connection counts as absent.

macOS runs no desktop GUI and takes no lock.

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
root-level desktop executable. Its runtime backend and WebView containment validation
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
prefix, then build the `uninstall` target. The external `installation/metadata/installation.json`
receipt binds removal to the installed package manifest and unchanged file hashes.
Changed files and unowned content remain. Symlink/junction traversal and filesystem
root removal are refused. Native package managers own uninstall for system packages;
the prefix helper is for isolated development installations.
