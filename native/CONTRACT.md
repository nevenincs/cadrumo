# Native distribution contract

## Explicit build target and dependency inputs

`CADRUMO_TARGET` selects a canonical target from
`dev/packaging/runtime_wheelhouse_contract.py`. A configured binary directory
cannot be reused for another target. `windows-x64` remains the Windows physical
mapping spelling; the canonical distribution target is `windows-x86-64`.
The four configure presets declare target identity. Linux/macOS require an
explicit compiler/sysroot toolchain, reviewed SDK pins and matching native
runner; preset existence does not establish support.

`native/toolchain.json` keeps common tool versions and a `targets` object with
per-target Rust triples and CPython acquisition pins. Windows uses the pinned
official NuGet SDK. Linux x86-64/AArch64 and macOS ARM64 use the reviewed Astral
Python Build Standalone 20251209 full shared-library SDKs for normal-GIL CPython
3.13.11, with exact archive hashes and target/ABI provenance. The authorized
selection is recorded in `scratch/provisioning-state-map/B2-native-decisions.md`.
Missing or mismatched pins refuse provisioning. Acquisition retains provider
metadata and all embedded dependency notices; assembly stages those notices and
the canonical CPython notice through the declared license inventory.

For tar.zst SDKs, configure `CADRUMO_ZSTD` as an explicit absolute builder
executable. Its content hash and canonical source provenance enter
`generated/build-toolchain.json`; the path is not a target SDK pin. Standalone
provisioning accepts `--build-toolchain <file>` with that configured decoder.
Linux assembly requires explicit `CADRUMO_READELF` and `CADRUMO_PATCHELF` tools;
macOS requires `CADRUMO_INSTALL_NAME_TOOL`, `CADRUMO_CODESIGN` and an explicit
`CADRUMO_NATIVE_SIGNING_IDENTITY`. Native tools are checked against configured
content identities and are never discovered through the runtime PATH.

The selected host interpreter, compiler, linker, Rust tools, uv and toolchain file
are recorded in the same builder provenance. Explicit sysroots use bounded,
deterministic file inventories in builder sidecars; links may not escape the
SDK or form cycles. Changed configured tool bytes require reconfiguration;
each action invalidates only for the toolchain inputs it consumes. Pure Python
product wheels do not include native compiler or sysroot identities. CMake and
Cargo share the selected linker configuration; cross/sysroot builds require the
reviewed `CADRUMO_RUST_LINKER` wrapper.
Configured provisioning, product and build-tool actions execute the selected,
hashed uv path; standalone commands may supply `--uv`. Native Cargo outputs live
in `cargo/native`, separate from `cargo/desktop`. A changed native toolchain
identity cleans only the admitted native target directory under an OS lock,
then publishes its identity after a successful Cargo command. Debug and Release
are the supported profiles; single-configuration generators require an explicit
`CMAKE_BUILD_TYPE`.

Provisioning selects the base dependency closure from the lock with target
markers and wheel ABI/floor checks. It installs exact wheel URLs with required
SHA256 hashes, explicit target and Python version; it never executes the SDK
interpreter. `runtime-inputs.json` records the selected wheel identities. Product
wheel construction uses host CPython at the exact release-builder patch, and
assembly rejects duplicate distributions, mixed cohort versions and target/ABI
metadata disagreement. Optional integrations remain separate capabilities.

Private build-cache schema 3 hashes every regular output and records contained
SDK link text, target identity and target bytes, traversing each directory once.
Escaping links, cycles, and added, missing or changed files refuse reuse,
including changes that preserve size. CMake invokes that validation on every
shared provisioning/product action. Earlier cache schemas rebuild.
Archive extraction rejects links, special files and ambiguous member names and
restores executable permission bits from Unix ZIP entries. Runtime, loader,
relocation and desktop acceptance still require the extracted target artifact.

CMake defines compilation, installation and ZIP packaging. All four target
mappings and native backends are enrolled; final native, relocation, deployment
floor and interactive acceptance remain target-specific gates. Enrollment and
fixture execution alone do not establish a supported complete release.
The existing Python product owns application
behavior. Native code owns bootstrap before Python exists.

## Source and generated ownership

| Concern | Authored owner | Generated output |
| --- | --- | --- |
| C interpreter host and CPython initialization | `native/interpreter/windows/`, `native/interpreter/posix/` and shared bridge | `<binary-dir>/bin/<Config>/` |
| Shared Rust platform implementation and C ABI | `native/platform/` | `<binary-dir>/cargo/native/` |
| Rust application library and compatibility probes | `native/application/` | `<binary-dir>/cargo/native/<rust-target>/<profile>/` |
| Shared package declarations and physical platform mappings | `native/package-layout.json`, `native/platforms/` | `<binary-dir>/generated/` |
| Build-time contract projection | `dev/packaging/native/` | C header, Rust constants, JSON contract |
| Build graph and packaging targets | `CMakeLists.txt`, `CMakePresets.json`, `native/cmake/` | Selected CMake binary directory |
| Package assembly operations | `dev/packaging/native/` | `<binary-dir>/stage/<Config>/app/` |
| Product identity | `src/cadrumo/core/product_identity.py` | Native product identity |
| Settings names and validation | `src/cadrumo/core/config.py` | Reserved environment names |
| Storage defaults, overrides and tool locations | `src/cadrumo/core/config.py`, `storage_environment.py`, `storage_taxonomy_locations.py` | Native Settings projection |
| Exact Python version | `dev/packaging/release-python-version` | Build input |
| Third-party dependency closure | `pyproject.toml`, `uv.lock`, existing constraint exporter | Installed locked dependencies |
| Python release cohort | `dev/packaging/python_cohort.py` | Existing three-wheel cohort |
| Bundled user documentation | `docs/` and its `dev/docs/` build driver; language set in `native/package-layout.json` | `<binary-dir>/user-docs/` |

Shared packaging owns dependency installation, product wheel assembly, standard-library
ZIP creation, manifests, artifact verification dispatch and cleanup. Physical names
come from the selected `native/platforms/` contract. Windows SDK acquisition, PE
relocation, pywin32 patches, executable resources and hostile-loader tests belong to
`dev/packaging/native/platforms/windows*.py`; its native build belongs to
`native/cmake/platforms/Windows.cmake`. The Windows runtime bootstrap lives under
`native/interpreter/windows/`. POSIX SDK acquisition and shared inventory live in
`dev/packaging/native/platforms/posix.py`; Linux ELF and macOS Mach-O relocation
remain with their respective backend modules. POSIX initialization/bootstrap
lives in `native/interpreter/posix/`. The selected contract's `bootstrap` field
owns the assembly dependency; backend names do not infer a source directory.
No Windows mapping is silently reused for another target.

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
The standalone `application.package` CTest uses `live-package-tests` without a
release expectation; the artifact probe uses `live-release-tests` and receives
the verifier's archive-bound release expectation. Both feature selections are
intentional.
For a separately extracted or installed artifact, configure the absolute
`CADRUMO_APPLICATION_TEST_PACKAGE_ROOT` and run
`ctest -C Release -R "^application\." --output-on-failure` in that build directory. This verifies that
selected artifact and does not establish a successful fresh `bundle` build.

## Platform mappings

`P` means installed package root; `U` means the effective storage root that the
storage owner declares in `src/cadrumo/core/storage_environment.py`. An absolute
`CADRUMO_LOCAL_STORAGE_ROOT` wins in every mode. Without it, a source checkout
uses `var/storage` beneath the checkout and an installed package uses the
per-user, per-channel default in the mutable-root row. The storage owner decides
the mode by where the package tree lives, never by the working directory.
`<name>` is `cadrumo` for the stable channel and `cadrumo-<channel>` for any
other, such as `cadrumo-preview`; the channel comes from the identity projection.

| Location in assembled ZIP | Windows x64 | Linux x86-64/AArch64 | macOS ARM64 |
| --- | --- | --- | --- |
| Executables | `P/python.exe`; application images such as `P/cadrumo.exe` and `P/cadrumo-manager.exe`; console entrypoints such as `P/bin/cadrumo-runtime.exe` and components in `P/bin/` | `P/python`, `P/cadrumo`, `P/cadrumo-manager`; console entrypoints in `P/bin/` | Same declared flat executable placement as Linux |
| Python | `P/python.zip`; dependencies in `P/cadrumo/site-packages/`; controlled `P/cadrumo/python.pth` | `P/python.zip`, `P/lib/cadrumo/site-packages/`, controlled `P/lib/cadrumo/python.pth` | Same declared Python placement as Linux |
| Native modules/libraries | `P/bin/`, qualified extensions beneath `bin/packages/` | `P/bin/`; qualified extension identities retained | `P/bin/`; qualified extensions and relocated install names |
| Immutable resources | `P/data/`, `P/docs/` | `P/data/`, `P/docs/` | `P/data/`, `P/docs/` |
| Mutable root | `%LOCALAPPDATA%\<name>`; checkout `var/storage`; delivered-artifact tests supply an explicit root | `$XDG_DATA_HOME/<name>` when `XDG_DATA_HOME` is absolute, else `$HOME/.local/share/<name>` | `$HOME/Library/Application Support/<name>` |
| Secure state | Existing Settings/taxonomy beneath the selected root | Same logical owner | Same logical owner |
| Loader | Static bootstrap CRT; explicit absolute DLL load with restricted search, then registered bundle directories | Relative ELF RUNPATH for every transitive dependency; audit LD_* and libc floor | Relative install names and rpaths; signing and hardened-runtime validation |

This table describes assembled artifact mappings. Installer/AppImage formats and
the macOS application wrapper have their own distribution definitions and native
acceptance; they do not change the current ZIP map. Linux new outputs use the
reviewed manylinux_2_28 builder, and macOS retains the canonical 14.0 product
floor. SDK enrollment does not prove deployment-floor or signing acceptance.
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
its arguments. The declared entrypoints are `aeat`, `cadrumo-mcp` and
`cadrumo-runtime`; they ship in the native directory as `P/bin/aeat.exe`,
`P/bin/cadrumo-mcp.exe` and `P/bin/cadrumo-runtime.exe`. Consumers such as the
desktop locate them through the generated inventory, never a spelled path.
The generated contract lists their file names; the platform library maps a
declared entrypoint image in `P/bin/` back to `P` and
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
package bootstrap before application code runs. CTest checks that each staged
entrypoint's help exits successfully. Product ZIP verification requires each
entrypoint's exit status and standard output for help and for an unknown option
to equal `python.exe` running the same console script, refuses a copy displaced
to the package root, then starts `cadrumo-runtime.exe` against an isolated
storage root with hostile Python variables and completes the verified runtime
handshake with the runtime's exact process image. The probe stops the runtime
through its process scope; it registers no service and leaves no process.

The interpreter excludes environment-derived Python paths, virtualenv discovery,
user site, automatic current-directory imports, sitecustomize and executable `.pth`
files. Necessary wheel path additions must be generated from inspected package
metadata. `-m`, `-c`, scripts, stdin and child startup use the bundled executable.
The caller's working directory is retained for explicit script/file arguments;
it is not an implicit import root. This is environment isolation, not a sandbox.

### Application images

The platform mapping's `application_images` list declares the native executables
that are not interpreter hosts. The `entrypoints` map stays reserved for console
scripts. Each entry carries:

| Field | Meaning |
| --- | --- |
| `name` | Image name; the file name adds the mapping's executable suffix, so `cadrumo` is `cadrumo.exe` on Windows |
| `placement` | Package-relative directory; only `.`, the package root, is implemented, and the loader refuses any other |
| `target` | CMake target that builds the image; the stage depends on it |
| `artifact` | CMake variable, defined in the root or `native/` directory scope, holding the image's absolute build path; a generator expression is allowed |
| `desktop` | Marks the one image that receives desktop registration; that image needs the bundled documentation |
| `signed` | The image belongs to the release signing inventory; no signing step consumes it yet |
| `startup` | Optional, default false; `true` adds the image to `startup_files` |
| `version_arguments` | Arguments that make the image print the product version |

The loader refuses an unknown or missing field, a duplicate name or artifact
variable, a second desktop image, a name that is a console entrypoint, and a file
name that equals, ignoring case, the first component of any declared package path
or file. Configure lists each image and whether it stages. `bundle` depends on
each staged image's target and artifact. Assembly copies each artifact into the
package before the manifest is hashed. It refuses an image without a supplied
artifact, an artifact that is missing or lies outside the CMake binary directory,
and an artifact for an image the package does not stage. The package manifest
hashes each image like any other file. CTest runs each staged image with its
version arguments as `bundle.image.<file>`. Product ZIP verification requires each
staged image to be hashed, its startup membership to match its declaration and its
output to carry the product version.

`cadrumo.exe` comes from `desktop-host-build` through
`CADRUMO_DESKTOP_HOST_EXECUTABLE`, which the desktop project defines, and
`scripts/tauri.mjs` refuses a build whose Cargo binary is another file. It is not a
startup file. It never runs the package bootstrap and checks the interpreter's
digest itself, so hashing it at every interpreter start would refuse Python over a
file Python never loads. `python.exe --check-package`, payload validation and ZIP
verification hash it. With `CADRUMO_PACKAGE_USER_DOCS=OFF` the package omits it,
because the desktop project always builds the documentation and the desktop serves
it; ZIP verification then requires its absence. The source build configures the
desktop project, so configuring it requires `npm` and `node`.

`cadrumo-manager.exe` comes from `rust_manager` through
`CADRUMO_MANAGER_EXECUTABLE`, which `cmake/Manager.cmake` defines in the `native/`
directory scope. It is the per-user runtime manager, not the desktop application,
so every package stages it, with or without the documentation. It is not a
startup file. Its Windows version resource names the manager: `FileDescription`
is the channel's manager name, such as `CADRUMO Background Services`,
`ProductName` is the channel's product name, `FileVersion` and `ProductVersion`
are the release version and `OriginalFilename` is `cadrumo-manager.exe`. The
crate's build script writes that resource and the process manifest without a
resource compiler, from the `CADRUMO_ID_*` identity projection.

## Mutable data and reconciliation

The native bootstrap projects canonical storage environment names and defaults.
Python continues to own bucket routing, encryption, authorization and member
defaults. A checkout keeps its repository-local default and an installed package
uses the per-user, per-channel default of the platform mappings. A relative
`CADRUMO_LOCAL_STORAGE_ROOT` anchors at the checkout in development and is
refused when installed. Python resolves only the stable channel's default; a
native package pins the root for its own channel before Python starts. The
native host is installed when its package root holds the package manifest and
in development when a checkout marker is above the executable; otherwise it
refuses. It never reads the working directory. Installed Windows resolves the
default through `FOLDERID_LocalAppData`, not the environment, and replays the
generated storage-root vectors in the `platform.resolver` test. No
storage is migrated: a tree that an earlier installed build created beneath a
launch directory is neither read nor moved, and an operator who wants it sets
`CADRUMO_LOCAL_STORAGE_ROOT` to it.

Package-only anchors are declared once. Existing taxonomy members remain owned
by Python and are projected at build time. The native host clears inherited Python
configuration and reserved Settings except the product allowlist that
`Settings.storage_env_var_names()` returns: the primary root variable
`CADRUMO_LOCAL_STORAGE_ROOT` and the settings field of each operator-overridable
taxonomy member. The development root variable `CADRUMO_STORAGE_ROOT` and the
development tool locations are not in it. Package-owned `CADRUMO_EXTERNAL_BIN_DIRS`
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

CMake owns configure, builder setup, registry publication, build, installation and
ZIP packaging. A fresh configuration uses `uv` to converge the pinned release
interpreter and locked development dependencies in `<binary-dir>/_deps/builder`.
An explicit `CADRUMO_DEV_PYTHON` selects an externally managed release interpreter;
setup validates its version and cleanup never removes it. Compiler, Rust, Node and
uv executables remain host toolchain prerequisites. The `just build-native`,
`just test-native-bundle`, `just build-native-package` and `just test-native-package`
recipes select the host's CMake preset and target; they no longer publish authority
or prepare a separate interpreter before CMake.

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
helper is an OS diagnostics tool. Linux/macOS adapters compile the enrolled native
hosts through explicit target toolchains; actual runner acceptance remains
separately recorded. Windows toolchain selection is scoped by
`native/cmake/WindowsToolchain.cmake`; Cargo gets explicit compiler-library and
linker paths without changing the caller's shell.

### Names, artifacts and targets

`<Config>` is exactly `Debug` or `Release`. The default binary directory is
`build/windows-x64`. Production is `python.exe`; the distinct development host is
always `python_d.exe`. Both use the pinned release CPython ABI and locked wheels.
Debug controls compiler optimization/symbols; `_d` identifies the development host,
not a CPython debug ABI. The `python_d` target always exists and is excluded from
the default build. Set `-DCADRUMO_INCLUDE_DEVELOPMENT_BINARY=ON` at configure time
to include it alongside production in the same package; shipping it is optional.

The standalone projects `native/desktop` and `native/cmake/distribution` carry
their own `CMakePresets.json`. A standalone project's binary directory is
`build/<configure preset name>` at the repository root, such as
`build/desktop-windows-x64`. CMake reads those presets from the project's source
directory: configure with `cmake -S <project> --preset <name>` and build with
`cmake --build <binary directory> --config <Config>`.

Configuration refuses any other binary directory. `native/cmake/BinaryDirectory.cmake`
admits only `build/<name>` at the repository root, where `<name>` is a configure
preset of the project being configured; a directory of another name, or an
enrolled name elsewhere, stops with the enrolled names.

| Path beneath the binary directory | Contents |
| --- | --- |
| `_deps/builder/` | Configure-owned release builder, retained by output cleanup |
| `_deps/python-sdk/` | Verified pinned CPython SDK, independent of runtime wheel changes |
| `_deps/runtime/` | Locked third-party wheels installed for staging |
| `_deps/build-tools/` | Pinned SVG renderer; never shipped |
| `product/build/wheels/` | Existing CADRUMO three-wheel cohort built from source |
| `product/dependencies/` | Exact production closure plus those product wheels |
| `generated/` | Native contracts, metadata, icon and resource source |
| `bin/<Config>/`, `lib/<Config>/`, `symbols/<Config>/` | Native executables/DLLs, import libraries and symbols |
| `cargo/native/` | Native Rust build products; isolated from `cargo/desktop/` |
| `tmp/` | Preset-scoped compiler and MSBuild scratch files; retained during cleanup targets because MSBuild can still be using them |
| `stage/<Config>/app/` | Complete application tree used by install and CPack |
| `install/` | Default local install prefix; override with `cmake --install --prefix` |
| `packages/<Config>/` | ZIP artifacts |
| `testing/<Config>/`, `verification/<Config>/` | Test state and extracted-artifact evidence |
| `user-docs/build/`, `user-docs/work/` | The language roots one documentation compile wrote, with its log and private storage |
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
| default / `zip` | Build the full application and its install-based ZIP |
| `bundle` | Build native hosts, product wheels and complete staged package |
| `setup-native-builder` | Converge the configure-owned builder or validate the selected external interpreter |
| `registry_authority` | Reuse the existing publication; compile when its descriptor or selected database is missing |
| `registry_authority_rebuild` | Explicitly recompile and publish authority, even when it exists |
| `native_contract`, `native_metadata` | Generate content-stable C/Rust contracts and executable resources |
| `rust_platform_static`, `rust_platform_shared`, `rust_platform_consumer` | Build one platform library format or its Rust consumer; `rust_platform` groups the libraries |
| `rust_application`, `rust_manager`, `desktop-host-build` | Build each application library, manager executable or desktop executable |
| `python`, `python_d` | Compile production or development host and bridge |
| `cadrumo_entrypoint_<name>` | Compile one declared console entrypoint host, such as `cadrumo-runtime.exe` |
| `python_sdk` | Acquire and verify the pinned CPython SDK |
| `python_dependencies` | Install the selected runtime wheel closure, reusing the SDK |
| `python_product` | Build and install the CADRUMO wheel cohort into dependency staging |
| `user_docs` | Build every declared documentation language and stage the shippable subset; a `bundle` prerequisite unless `CADRUMO_PACKAGE_USER_DOCS=OFF` |
| `user_docs_build`, `user_docs_stage` | Compile documentation or prepare its shippable subset independently |
| `desktop-frontend-install`, `desktop-frontend-chrome`, `desktop-frontend-palette`, `desktop-frontend-build`, `desktop-host-prepare` | Prepare each desktop dependency, generated input, asset bundle or host snapshot independently |
| `verify` | Build bundle/ABI consumers, run CTest including real dependency imports |
| `install` / `cmake --install` | Copy staged package to the chosen prefix |
| `package` | Standard CPack target; use `zip` for content-aware archive reuse |
| `verify-package` | Build ZIP, extract into a Unicode/spaces path, run cohesion and runtime probes |
| `clean` | Generator's standard build-output cleanup |
| `clean-stage` | Remove stage, testing and verification trees |
| `clean-packages` | Remove ZIP and CPack staging trees |
| `clean-dependencies` | Remove downloaded SDK/dependencies and product wheel staging |
| `clean-native` | Remove bin, lib, symbols and Cargo outputs; retain configure metadata |
| `clean-desktop` | Remove declared desktop build outputs and test state |
| `clean-docs` | Remove documentation build roots, work state and the staged subset |
| `clean-<target>` | Remove the target's owned outputs; keep shared prerequisites and other configurations |
| `clean-all` | Remove enrolled outputs in every configuration and bounded cleanup groups; retain configuration, builder and installation receipts |

Explicit cleanup never removes source files, the installed application or an
arbitrary path. It validates the CMake source owner and each resolved child path.
Shared provisioning and product actions record input fingerprints and output inventories
so switching configurations can reuse them. Selected authority and wheel metadata
inputs participate in the product dependency graph. Do not run independent builds
or cleanup concurrently in the same binary directory.
A subsequent build regenerates removed prerequisites. Run build before
`cmake --install`; that command copies an already assembled tree.

Content checks run on every invocation for the generated contracts/resources,
SDK, wheel closure, frontend, documentation, assembly and ZIP. Receipts bind input
bytes, command selections and complete output inventories. Missing or altered
outputs invalidate reuse. Unchanged generated files retain timestamps, including
when regenerated bytes match. Runtime wheel selection excludes development-only
lock changes; desktop tool changes do not invalidate native provisioning. Native
compilers and Cargo retain their normal source timestamp rules: touching a raw
C/Rust source may rebuild its owning binary. Changes to shared code correctly
rebuild its consumers. Individual Cargo clean targets remove public outputs;
`clean-native` and `clean-desktop` also clear the shared compiler caches.
Authority publication is an explicitly selected build input. Normal CMake and
wheel builds reuse its descriptor and selected database when present, and compile
when either is missing. Source or compiler changes do not trigger republication.
After registry or compiler edits, run
`cmake --build build/windows-x64 --config Release --target registry_authority_rebuild`
(select the appropriate binary directory), or `just registry-publish-authority`.
Malformed descriptors and altered database bytes still fail artifact validation.
`just init` retains its explicit source-currency publication step. Fresh CI
checkouts compile the missing authority; jobs restoring a published authority
must explicitly republish if they require a fresh compile. Registry currency
checks remain separate from ordinary builds.

`clean-setup-native-builder` removes a CMake-owned builder and forces configure
to restore it before the next individual build. An explicitly selected external
interpreter is retained with an ownership message. `clean-desktop-frontend-install`
removes the checkout's shared npm installation under the install lock; subsequent
frontend builds restore it. That explicit cleanup affects every binary directory
using the checkout.

The root install rule preserves source permissions, including executable bits on
POSIX hosts. Both installation and the ZIP consume the same staged application.

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
`user_docs`: its directory beneath `paths.docs`, the manifest name, the entry
address, the search address, the language set and the `media_types` table of
files the documentation scheme serves. Each language must be one of
the product's output languages, and English must be declared. `native/cmake/Docs.cmake`
defines the `user_docs` target for the source build and the standalone desktop
project; `bundle` and `desktop-host-build` depend on it.

`dev/packaging/native/docs_build.py` compiles the documentation once for every
declared language (`python -m dev.docs.compile_once --html-root`), as a user-scope
build from a private source copy, and each language's root is composed at
`user-docs/build/html/<lang>/`. The pages are read once however many languages are
declared. Ambient `CADRUMO_DOCS_*` settings are dropped and the compile gets its own
storage root. The site's one search index is then built over every root, under the
`full` Pagefind contract, into the English root. The cli-sequence golden check runs
in that one compile. The step fingerprints the contents of `inputs-user-docs.txt`:
documentation sources, documentation tooling, `src/`, the layout and the selected
published authority. Unchanged inputs reuse the previous roots. The documentation
does not depend on the platform or on the build directory, so a build configuration
whose inputs outside its own build directory match the site another configuration of
the checkout built copies that site from the development cache (`user-docs`) instead
of compiling again; the cache holds one site, checked against its recorded inventory
before it is reused. A stale published authority fails the target, and the owner's
refusal is printed as the `cause:` line. The previous search index is removed before
the compile, so staging can never accept an older root after a failed build.

`dev/packaging/native/docs_stage.py` stages the addresses of the published site
layout: English at `P/docs/user/` and every other language at
`P/docs/user/<lang>/`, where the owner's language switcher links. Those are the
addresses the documentation scheme answers, not the layout of the files stored;
the stored layout is below. Sphinx build state (`.doctrees`, `.buildinfo`, `_sources`)
and site-language directories nested in a source root are not copied. Only files
whose name `user_docs.media_types` types are copied, because the documentation
scheme answers every other file with 404; staging prints what it left out.
Staging refuses a language without its entry page or Pagefind module, an entry or
search file the table does not type, a linked source entry and a non-portable
path. In pages and stylesheets it refuses a loaded resource that names an
`http:`, `https:` or protocol-relative URL, a reference inside the package to a
file type the scheme does not serve, an inline event-handler attribute and a
`javascript:` URL. Loaded resources are the `src`, `href`, `srcset`,
`imagesrcset`, `data`, `poster`, `action` and `formaction` URLs of resource and
form elements, a refresh `meta`, and `url()`, `src()`, `image-set()` and
`@import` in stylesheets and `style` content. A followed `a` or `area` link may
leave the package, because the desktop opens `https:` and `mailto:` links
externally and refuses other schemes. Each refusal names the reference, its
location count and the first page and line.

The package holds one documentation structure and each language's text, not one
site per language. `P/docs/user/` therefore carries:

| Stored | Holds |
| --- | --- |
| `structure/<site path>` | A page's structure: its bytes with a slot wherever the languages differ, `U+E000`, the slot number in lowercase base 36, `U+E001`. For a file identical in every language, that file, stored once |
| `text/<language>.json` | A JSON array of that language's strings; element `N` is slot `N` |
| `languages/<language>/<site path>` | The files one language alone has and that are not pages |

`dev/docs/shared_structure.py` writes the structures and the strings and is the
format's definition. The addresses a request asks for are unchanged: the apex
language's site is at the top and every other language under `<language>/`.

`P/docs/user/manifest.json` is the documentation handler's input:

| Field | Meaning |
| --- | --- |
| `schema` | Manifest schema, currently `2` |
| `languages` | Declared languages, in declared order |
| `apex_language` | Language served at the documentation root, `en` |
| `entries` | Entry page address per language, such as `index.html` and `es/index.html` |
| `search` | The one search index address, at the site's apex, such as `pagefind/pagefind.js` |
| `script_hashes` | CSP `sha256-<base64>` values of every executing inline `<script>`, hashed after HTML newline normalization; inert types such as `application/json` are omitted |
| `stored` | Where each stored kind lives relative to `P/docs/user/`: `structure`, `languages`, and `text` per language |
| `pages` | The site paths served by composing a structure with a language's text |
| `files` | Every stored file relative to `P/docs/user/`, with its SHA-256; the manifest does not list itself |

`entries` and `search` are addresses; `stored`, `pages` and `files` describe the
files the package holds. The desktop host serves only what those describe and
derives the documentation origin's CSP from `script_hashes`;
[Desktop shell](#desktop-shell) describes the handler. It reads the manifest
once at startup and does not rehash a file per request; the package checks below
own the digests. The shell CSP does not govern the documentation.

Admission refuses a schema other than `2`, an entry or search address that
resolves to nothing servable, a `stored.text` whose languages are not exactly
`languages`, a text file outside `files`, and a page whose structure is outside
`files`.

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

## Desktop shell

`cadrumo.exe` is a Tauri host in `native/desktop/src-tauri/` with a React shell in
`native/desktop/frontend/`. Without arguments on an interactive desktop it opens
one window. With arguments, after `--headless`, or without an interactive desktop
it runs the installed CLI as a passthrough in the caller's directory. `--gui`
forces the window: it exits with 69 and `desktop_unavailable` when no interactive
desktop exists, and with 64 when other arguments follow it. On Windows an
interactive desktop means a visible window station with an input desktop the
process can open; on Linux a non-empty `WAYLAND_DISPLAY` or `DISPLAY`. macOS
refuses the window with `unsupported_platform`. One window runs per user and
channel; the [Desktop single instance](#desktop-single-instance) section records
that contract.

### Launch projection and storage root

The Windows desktop image uses the GUI subsystem, so Explorer does not allocate
a console window. CLI launches attach to an existing parent console while
preserving inherited file and pipe handles; they never allocate a new console.

The host takes its package root from `CADRUMO_DESKTOP_PACKAGE_ROOT` when that is
set and otherwise from its own directory. It checks the package manifest's
platform and ABI against the generated contract and the interpreter against its
manifest digest. On Windows, default member settings use the shared native
platform preparation and generated canonical Settings, storage and logging
defaults, without starting Python. Explicit nonblank member overrides or an
unusual home-directory configuration use the fixed query below. Profile and
pointer validation stays with the canonical account CLI read after the window
opens. Other platforms always use the query.

The fallback runs the fixed query `src-tauri/src/python/environment.py`
as `python.exe -I -c` with the caller's environment and working directory, a 30 s
deadline, 1 MiB of standard output and 64 KiB of standard error. The output is
parsed and never retained, because the environment can hold credentials.

The query reports the child environment, the storage root, the log directory,
log file, line format and rotation limits, the output language and the user's
home directory. The child environment carries `CADRUMO_LOCAL_STORAGE_ROOT` set to
the absolute root that `configured_storage_root()` resolved, and the query refuses
with `storage_root_disagreement` when Settings resolves a different root. The host
refuses a projection with a relative path, a log file outside the log directory,
an empty line format, an output language that is not lowercase ASCII, a pin under
a name outside the product allowlist, or an environment that does not carry
exactly that root under that name. The
host, every terminal kind and the CLI passthrough therefore share one root
whatever their working directory. The host adds no storage, log or Settings
variable of its own.

The webview profile directory is the absolute path the projection resolves for the
storage taxonomy's `webview` member (`U/webview`, override
`CADRUMO_WEBVIEW_DIR`), and the host refuses a projection without one. The
window state, `window-state.json`, lives in the same directory: the host restores
each window's size, position and maximized state when the window is ready,
shrunk and moved to lie within a current display, and on close writes the
record to a temporary file, flushes it and renames it over the previous record.
A missing or unreadable record means the configured defaults. No webview command
reads or writes it.

### Origins and the documentation scheme

Origins are computed at startup from the window's `useHttpsScheme` setting, never
stored:

| Origin | Windows | Linux |
| --- | --- | --- |
| Shell | `http://tauri.localhost`, or `https://` with `useHttpsScheme` | `tauri://localhost` |
| Documentation | `http://cadrumo-docs.localhost`, or `https://` likewise | `cadrumo-docs://localhost` |

A Tauri development build also admits the `devUrl` origin as a shell origin.
`native/desktop/scripts/configuration.mjs` writes the documentation origin of the
target platform into the shell policy at build time, and the host recomputes both
origins at startup. The host refuses to start unless the shell
policy's `frame-src` is exactly the documentation origin.

`src-tauri/src/docs/` serves the read-only `cadrumo-docs` scheme from
`P/docs/user/`, composing a page from its structure and its language's text on
the way out. It reads `manifest.json` once at startup and never walks or
rehashes the tree; the package checks above own the digests. Each request is
answered as follows:

- Methods other than GET and HEAD receive 405 with `Allow: GET, HEAD`.
- A host other than the scheme's own `localhost` receives 404. Wry hands every
  `http(s)://cadrumo-docs.*` host to the handler, so the handler checks it.
- A path with a backslash, a colon, an empty or dot segment, a control
  character, a Windows reserved name or character, or a percent escape of `/`,
  `\`, `.`, `%` or a control receives 400. A path ending in `/` names its
  `index.html`.
- A file name the media-type table does not type receives 404. The address's
  own name decides the type, whatever the address is stored as.
- The address is then resolved against the manifest. Its first segment names
  its language when that segment is a declared language other than
  `apex_language`, and the rest is the site path; otherwise the language is
  `apex_language` and the site path is the whole address. The handler serves
  `<stored.languages>/<language>/<site path>` when `files` lists it, else
  composes `<stored.structure>/<site path>` with that language's text when
  `pages` lists the site path, else serves `<stored.structure>/<site path>`
  when `files` lists it, else answers 404. A stored path is no address of its
  own: a request for `structure/index.html`, `text/en.json` or
  `languages/es/x` asks for a site path nothing answers.
- A link or reparse point and a file resolving outside the canonical root
  receive 404. Structures and text files are read under the same containment.
- A page whose structure is not UTF-8, names a slot its language has no string
  for or is malformed, or whose text cannot be read as a list of strings,
  receives 500. No response carries part of a composed page.
- A served address carries its media type, the `Content-Length` of what it
  answers with, the documentation policy, `X-Content-Type-Options: nosniff` and
  `Cache-Control: no-cache`. Refusals carry the same policy and `nosniff` with
  an empty body.
- A language's text is read once and kept, because one file carries the strings
  of every page of that language.

A response sent before the policy is fixed carries
`default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'`.
In a Tauri development build `CADRUMO_DESKTOP_DOCS_ROOT` may name a staged tree
that carries its own `manifest.json`; other builds ignore it and serve only a
tree inside the package.

The media types come from `user_docs.media_types` in `native/package-layout.json`,
which the generated contract carries. `names` matches a whole file name first;
`extensions` then matches the text after the name's last dot. Both comparisons
are exact and case-sensitive, and a name neither section types is not served.
Staging reads the same table, so no file ships that the scheme would refuse.

| Key | Media type |
| --- | --- |
| `pagefind-entry.json` | `application/json` |
| `html` | `text/html; charset=utf-8` |
| `css` | `text/css; charset=utf-8` |
| `js`, `mjs` | `text/javascript; charset=utf-8` |
| `json` | `application/json` |
| `woff2` | `font/woff2` |
| `svg` | `image/svg+xml` |
| `png` | `image/png` |
| `wasm` | `application/wasm` |
| `pf_meta`, `pf_index`, `pf_fragment`, `pf_filter`, `pagefind` | `application/octet-stream` |

### Content security policies

The shell document's policy comes from `src-tauri/tauri.conf.json.in`, whose
template frames nothing; the build replaces `frame-src 'none'` with the
documentation origin:

```text
default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src ipc: http://ipc.localhost; object-src 'none'; frame-src <documentation origin>; base-uri 'self'; form-action 'none'
```

Every documentation response carries this policy, built from the manifest's
`script_hashes` and every shell origin:

```text
default-src 'self'; script-src 'self' 'wasm-unsafe-eval' <script hashes>; worker-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; object-src 'none'; frame-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors <shell origins>
```

Pagefind instantiates WebAssembly from bytes and runs a same-origin classic
worker, so `'wasm-unsafe-eval'` and `worker-src 'self'` appear on the
documentation origin only. `connect-src 'self'` keeps documentation scripts away
from the IPC fetch transport, and `frame-ancestors` lets only the shell frame the
documentation.

### Launch token and command dispatch

Tauri treats every registered custom scheme as a local origin, and on Windows the
webview runs initialization scripts in every frame, so capabilities cannot keep
the documentation frame from IPC. The refusal is the host's own:

- **Token.** The host mints 32 bytes from the operating system's random source
  per launch and keeps their hexadecimal form in memory only. The type has no
  debug, display or serialized form, so it cannot reach logs or responses.
- **Top-frame gate.** The initialization script `src-tauri/src/shell/token.js`
  returns at once unless `window.top === window` and `location.origin` is a shell
  origin. Otherwise it defines a non-writable, non-configurable
  `window.__CADRUMO_SHELL__` whose `token` getter returns the token once and
  deletes itself.
- **Dispatcher.** `src-tauri/src/app.rs` routes every app command through one
  token check, so no command is registered without it. A JSON-object call
  presents the `token` argument. Any other body presents the `x-cadrumo-token`
  header: a raw body, or the JSON byte array that Tauri's postMessage fallback
  makes of one. The comparison takes constant time for a token of the right
  length. A mismatch is refused with `invalid_arguments` for the `webview`
  operation and recorded in host diagnostics. Command names must be unique
  across modules or the host refuses to start.
- **No plugin commands.** The configuration grants no capability. The clipboard
  plugin is registered for its Rust API only, and the opener is a Rust crate, so
  the webview reaches neither except through token-checked app commands.

### Channel interceptor

`src-tauri/src/shell/channel.rs` delivers every channel frame, terminal frames
and log batches alike, by evaluating
`window.__TAURI_INTERNALS__.runCallback(<callback>, {message, index})` in the
shell document. It consumes every frame. Tauri would otherwise keep larger frames
in a per-webview queue that any frame of the webview could drain with the channel
fetch command, which the access control exempts and which uses sequential ids. A
frame that cannot be evaluated is recorded as a failure and dropped, never
queued.

These barriers do not depend on frame-level capability scoping. No automated
test yet drives the packaged window from inside the documentation frame. If such
a test shows any delivery to that frame, the documentation moves to a separate
webview.

### Terminal sessions

The optional console/Python panel is closed by default. Each terminal is created
only on its first visible selection; a remembered open tab starts that tab alone.
Hiding or switching an activated tab retains its terminal and process.

Before opening xterm, the shell loads every bundled JetBrains Mono subset so
its glyph-width cache never measures a temporary fallback font. A failed font
load selects a system-only fallback for the document's lifetime. The WebGL
renderer positions cells explicitly and draws continuous box/block glyphs at
unit line height. Unsupported graphics or unrecovered context loss falls back
to xterm's DOM renderer without replacing the PTY. Hidden font-size changes
defer fitting until the pane has dimensions again.

The dedicated TUI uses native ANSI color roles, with light and dark Cadrumo
palettes owned by the desktop. Changing appearance recolors existing content
and hidden panes without restarting a process or writing to its input. The
console and Python panes follow appearance unless their explicit always-dark
preference is selected. The TUI pane and its header follow desktop appearance.
Only the dedicated TUI launch sets `TERM_PROGRAM=cadrumo`; standalone Textual
surfaces retain their own RGB themes. The embedded TUI's appearance action
emits `OSC 777;cadrumo;appearance;toggle ST`. Only the TUI pane recognizes that
exact presentation request and toggles the frontend preference. Other OSC
payloads and terminal kinds cannot invoke it; it carries no runtime state.

`src-tauri/src/terminal/` keeps at most one live PTY session per kind:

| Kind | Program | Starts in | Process role |
| --- | --- | --- | --- |
| `console` | Windows: `PowerShell\7\pwsh.exe` under `ProgramW6432` or `ProgramFiles`, else `System32\WindowsPowerShell\v1.0\powershell.exe` under `SystemRoot`, with `-NoLogo`; Linux: the account's login shell from `/etc/passwd` | User home | `console` |
| `python` | `P/python.exe` with no arguments | User home | `repl` |
| `tui` | `P/python.exe -m cadrumo.entrypoints.tui` | Storage root | `tui` |

Every kind receives the same pinned child environment; `console` also gets
`P/bin/` first on `PATH`. The shell program is resolved as an absolute path from
fixed system locations, never through `PATH`. `console` and `python` refuse to
start when the home directory is not an absolute directory or lies inside the
storage root, so a relative write cannot land a plaintext file in custody. On
Windows the host clears the inherited "ignore Ctrl+C" attribute before starting
any terminal child, so Ctrl+C reaches it.

| Command | Arguments | Result and refusals |
| --- | --- | --- |
| `terminal_open` | `token`, `kind`, `cols`, `rows`, `frames` (a channel) | `{session}`. Ids increase for the host's lifetime. A live session of the kind is refused with `session_unavailable`; an exited one is settled and replaced. |
| `terminal_write` | Raw body of at most 64 KiB, or a JSON byte array of at most 65,536 items; headers `x-cadrumo-token` and `x-cadrumo-session` (decimal id) | Accepted into a queue of 8 writes. A full queue is refused with `queue_full`, which is not recorded as a failure, and the shell retries. |
| `terminal_ack` | `token`, `session`, `offset` | Cumulative data-byte offset. A stale offset changes nothing; an offset past the delivered bytes is `invalid_arguments`; a replaced or closed id is `session_unavailable`. |
| `terminal_resize` | `token`, `session`, `cols`, `rows` | Each dimension 2 to 1000, else `invalid_arguments`. |
| `terminal_close` | `token`, `session` | `{}` once the session has settled. Otherwise the kill failure or `cleanup_failed`, and the session stays owned. |
| `diagnostics_snapshot` | `token`, `after` | Host diagnostics after a cursor. |

One channel per session carries every frame, so `exited` always follows the last
`data` frame. Each frame is one tag byte followed by its payload:

| Tag | Frame | Payload |
| --- | --- | --- |
| 0 | `data` | PTY output, 1 to 8192 bytes |
| 1 | `started` | UTF-8 JSON `{"pid": number}` |
| 2 | `exited` | UTF-8 JSON `{"code": number \| null}` |
| 3 | `failed` | UTF-8 JSON `{"error": {"code", "operation", "message"}}` |

Only `data` payload bytes count toward acknowledgements. The reader reads the
PTY in chunks of at most 8 KiB and stops reading once 512 KiB are
unacknowledged, so the child blocks on its own write and no byte is dropped. It
resumes when fewer than 128 KiB remain unacknowledged; a paused reader rechecks
at least every 50 ms, and a stop request releases it at once.

A finisher thread owns each child. After the child exits it closes the PTY,
joins the reader and writer, sends any `failed` frames and then `exited`. A
session stopped by the host sends no further frames. Settling kills a running
child and waits up to 3 s for the finisher; a session that misses the deadline
stays owned and its failure is returned. A window close request settles every
kind under one shared 3 s deadline and attempts each kind even when another
fails. A failure keeps the window open and is recorded. The start of a
shell-document load settles every session, and host exit settles again. PTY
bytes never enter host diagnostics or the log view.

### Log aggregation

`src-tauri/src/logs/` merges Python file records and in-memory native events,
polled every 100 ms. `source` is an open enumeration:

- `python`: the log file the query reports (`cadrumo.log` in the log directory)
  and its numbered rotations, which Python writes through its secret-scrubbing
  filter. The
  line format comes from the query, so the host holds no copy of it.
  Continuation lines such as tracebacks become the record's `detail`, up to
  64 KiB. A record completes after its file has been quiet for 250 ms. Python
  records carry their raw timestamp and parse canonical UTC timestamps with
  milliseconds into `timestampMs`. Older offset-free timestamps retain a null
  `timestampMs`. The projected `diagnostic_context` suffix on the first physical
  header line supplies a bounded
  JSON object of scrubbed scalar fields, including the writing process role and
  pid and an opaque `diagnostic_id` when an attempt is active. A missing or
  truncated suffix leaves the original message readable without attribution.
  Multiline message continuations and tracebacks remain detail; JSON-looking
  continuation text never replaces the header's context.
- `host`: the host's diagnostics events, logged as `desktop`, with an RFC 3339
  UTC timestamp, a level and the child role and pid, or the host's identity for
  host events. Monotonic event sequences avoid replay after ring rotation. The
  scalar context carries lifecycle stage/outcome, child phase/exit code and
  safe failure code, operation, OS error kind and numeric OS code when known.
  Captured child output is never requested, so terminal bytes cannot appear.

Each record exposes `context` alongside `process`. Parsed instants display in
the viewer's local timezone; offset-free legacy timestamps display unchanged.
Process identity, startup phase, outcome and correlation are visible in the row,
with complete scalar context beside continuation lines in the expanded detail.
Text filtering and copied lines include this context; copied timestamps retain
the original text. Python suffix objects are limited to 32 scalar fields with
strings of at most 512 characters.

The reader identifies a file by its first 1 KiB, not its name, and keeps a read
offset per file, so late, skipped, partial or racing rotations lose and repeat
nothing. It opens a file only for one read with default sharing, so a writer's
rename is never blocked, and it never infers a process exit from a file event.
The first poll reads at most 16 MiB across the existing files, newest first; a
poll reads at most 4 MiB per file. Lines longer than 16 KiB are truncated and
bytes are decoded as lossy UTF-8. Nothing is written, truncated, rotated or
deleted, and no record is persisted.

The source state is `available` when the file or a rotation was read and
`missing` when no log file exists yet. It is `unreadable`, with a failure, when
the log directory cannot be listed, the line format cannot be parsed, or reading
fails in two polls in a row; one failure can be a racing rotation. Its `detail`
names the log file.

`logs_subscribe` (`token`, `records` channel) returns `{subscription, state}`. The
ring holds 10,000 records, and a subscription's first batch carries at most the
newest 5,000.
Each subscription then receives at most one batch per 100 ms and none when
nothing changed. A batch is `{records, dropped, state}`, where `dropped` counts
records the ring overwrote before this subscription saw them. At most 8
subscriptions exist; a ninth evicts the oldest. A shell-document load ends every
subscription. `logs_unsubscribe` (`token`, `subscription`) refuses an unknown id
with `invalid_arguments`.

The host also writes its own diagnostics events to `cadrumo-native.jsonl` in the
log directory, rotated by the same Settings limits.

### Shell commands

| Command | Arguments | Result and refusals |
| --- | --- | --- |
| `desktop_environment` | `token` | `{outputLanguage, docs: {origin, languages: [{code, entry}]}}`, with each entry as a URL on the documentation origin, in manifest language order. |
| `open_external` | `token`, `url` | Opens the URL with the system's registered handler. Only lowercase `https://` with a host and no user information, or `mailto:` with an address, written as printable ASCII without a backslash and at most 8192 bytes; anything else is `invalid_arguments`. |
| `shell_clipboard_read` | `token` | `{text}`. |
| `shell_clipboard_write` | `token`, `text` | At most 1 MiB of UTF-8, else `invalid_arguments`. |
| `shell_context_menu` | `token`, `items`, optional `x` and `y` | `{chosen}`: the id of the enabled item chosen, or null when the menu closed without a choice. |

`shell_context_menu` takes 1 to 64 items, each `{id, label, enabled, shortcut?}`
or `{separator: true}`, with at least one action. Ids, labels and shortcuts are
at most 128, 256 and 64 characters without control characters, and ids are
unique. The host names each native item `ctx/<popup>/<id>` and doubles every `&`
so labels show literally. `x` and `y` come together, as a logical position in
shell CSS pixels within 1,000,000 of the origin; without them the menu opens at
the cursor. One popup is open at a time, and a second request is refused with
`session_unavailable`. The command is asynchronous because the Windows popup
blocks until the menu closes. A sentinel queued on the main thread afterwards
resolves a dismissal to null after any pending menu event. Other platforms
refuse it with `unsupported_platform`.

### WebView2 requirements

The installed WebView2 runtime must expose `ICoreWebView2_22`, which lets iframe
and worker requests reach a custom scheme, and `ICoreWebView2Settings3`, which
can turn off browser accelerator keys. This contract states the interfaces, not
a runtime version. When each webview is ready the host probes both through the
platform crate (`native/platform/src/desktop.rs`). It then turns off the default
context menus and the browser accelerator keys (reload, print, find, zoom and
developer tools) and reads both settings back. A missing interface is refused as
`unsupported_platform` and any other failure as `webview_failed`, both for the
`webview` operation. The host records the failure in its diagnostics and ends
with exit status 1.

### Runtime and sign-in dependency

The desktop holds no runtime connection and no runtime authority, and keeps no
session, receipt or credential. The TUI tab runs the TUI process and shows only
its output, including the reason the TUI writes on standard error and its exit
when no runtime admits it. Starting or reaching a runtime manager is not
implemented: the desktop starts and stops nothing.

Sign-in and profiles go through the packaged command line
(`src-tauri/src/shell/sign_in/`). Each command below spawns one short-lived
`aeat --format json config …` from the package, with the storage environment
the host pinned; the image is checked against the package manifest once, when
the window starts. One runs at a time: `sign_in_status` and `profile_list` wait
for the one that is running, for as long as the slowest command may take, and
the others are refused with `queue_full`. A child has 30 seconds from its own
start, and the creation of a profile 300, because the product derives a
profile's key from its password slowly on purpose; a child that passes its
deadline is stopped and the command refused with `timed_out`, which says
nothing of whether a creation was made. Output above 64 KiB is refused with
`output_limit`. The host decodes the schema 2 envelope and requires the
command's own name in an answer; a refusal may carry no command name, as one
made before the product has read its command does. Of a refusal only the code
crosses to the window, with
the seconds of a throttle: never a message or other context. Children are
stopped when the window closes.

| Command | Arguments | Command line | Result and refusals |
| --- | --- | --- | --- |
| `sign_in_status` | `token` | `config sign-in-status` | `{supported, state, active_profile, runtimeAvailable, refusal}`. `state` is `present`, `absent` or `unknown`; `active_profile` is the selected profile's label or null. Reading it never resumes or extends a sign-in. |
| `sign_in_submit` | Raw UTF-8 password body, whose JSON encoding must fit the product's 8192-byte read (twice over for a creation); header `x-cadrumo-token`; optional header `x-cadrumo-profile` | `config login --secrets-stdin`, then `-- LABEL` when a profile is named | `{kind: "signed-in"}`, or `{kind: "refused", code, retryAfterSeconds}`. Unnamed, it signs in to the selected profile. One attempt: nothing is retried. |
| `sign_out` | `token` | `config logout` | `{remainingAccess: {automationEnabled, automationRevoked: false}}`. A refusal rejects with `{code, retryAfterSeconds}`. |
| `profile_list` | `token` | `config profile list` | `{profiles: [{name, active}], complete}`, in the product's order. It needs no password, session or runtime. `complete` is false when the product reports that it could not read its profiles coherently: the list is then no evidence of which profiles exist. |
| `profile_create` | Raw UTF-8 password body, whose JSON encoding must fit the product's 8192-byte read (twice over for a creation); headers `x-cadrumo-token` and `x-cadrumo-profile` | `config profile create --quiet --secrets-stdin -- LABEL` | `{kind: "created", name}`, or `{kind: "refused", code, retryAfterSeconds}`. The new profile is selected and left signed out. A label already in use is refused with the code `profile_already_exists`. One attempt: nothing is retried. |

`x-cadrumo-profile` carries a profile's label as UTF-8, percent-encoded, since
a header carries no other text. The product prints no profile identity, so the
label, which is unique on a computer, is how a profile is named. The host
passes the label after `--` so that none of it is read as an option. On
Windows the product's command line still rewrites an argument there: it
expands environment variables, file-name patterns and a leading home
directory, so that `%USERNAME% y Cia` or `Taller [2025]` would name another
profile. The host therefore refuses with `invalid_arguments` a label that is
empty, longer than 160 characters, surrounded by white space, holding a
control character or one of `*`, `?`, `[`, `%` and `$`, or beginning with a
hyphen or a tilde. The window names a profile only when it is not the selected
one, so a selected profile under such a label is still signed in to, unnamed.
The password is written once to the child's standard
input as one JSON object, `passphrase` alone or with the same text as
`passphrase_confirmation` for a creation, from a buffer that is wiped when
dropped, and the input is then closed. The copies the webview and its transport
hold cannot be wiped.

These commands are implemented on Windows. Elsewhere `sign_in_status` reports
`supported: false` and the others are refused with `unsupported_platform`.

### Desktop build and test procedure

The desktop is a standalone CMake project. Configure it with
`cmake -S native/desktop --preset desktop-windows-x64`, whose binary directory is
`build/desktop-windows-x64`; the other targets' presets are
`desktop-linux-x86-64`, `desktop-linux-aarch64` and `desktop-macos-arm64`. Pass
`CADRUMO_NATIVE_CONTRACT` naming the generated
`contract.json` of a configured source build, and `CADRUMO_DESKTOP_PACKAGE_ROOT`
naming an assembled package such as `stage/<Config>/app/`. Set
`CADRUMO_DEV_PYTHON` when the checkout's development interpreter is not found.
`frontend/scripts/bootstrap.mjs`, `tests/run-packaged.ps1` and
`tests/run-backend.ps1` read the host's preset and use its binary directory
unless another directory is passed.
The standalone project's host runs from its Cargo output and finds the package
through `CADRUMO_DESKTOP_PACKAGE_ROOT`. The source build configures this project
only when a desktop image is staged, which requires the documentation; a `bundle`
with the documentation then stages `cadrumo.exe` at the package root as an
[application image](#application-images). Without it, configuring the source build
needs neither Node.js nor npm.

| Target | Operation |
| --- | --- |
| `desktop-frontend-install` | Run `npm ci` in the frontend only when `node_modules/.package-lock.json` does not match `package-lock.json` for this platform, or `package.json` and the lockfile declare a dependency differently; the check reads the installed tree, which every binary directory shares |
| `desktop-frontend-check` | Type check, lint and `prettier --check` of the frontend, scripts and tests |
| `desktop-frontend-build`, `desktop-frontend-test` | Regenerate chrome strings and palette, then build the frontend or run its browser tests |
| `desktop-frontend-generated` | Write the chrome strings and the palette into the binary directory (`desktop/frontend-generated`), never into the source tree: with `npm ci`, all that developing the frontend in a browser needs (`native/desktop/frontend/README.md`) |
| `user_docs` | Build and stage the user documentation, as above |
| `desktop-host-build` | Build the frontend and the documentation, then `cadrumo.exe` with `--locked`; refuse a binary other than `CADRUMO_DESKTOP_HOST_EXECUTABLE` and record it in `generated/desktop-<Config>.json` |
| `desktop-host-test` | `cargo test` with the live package tests against `CADRUMO_DESKTOP_PACKAGE_ROOT`, one test thread, storage under `desktop/testing/storage` |
| `desktop-host-clippy` | Clippy on all targets with warnings denied |
| `desktop-headless-test` | Byte-for-byte CLI passthrough parity with the package interpreter, under a hostile Python environment |
| `desktop-paths-test`, `desktop-configuration-test` | Build-path and generated Tauri configuration checks |
| `desktop-run` | Start the built `cadrumo.exe` against `CADRUMO_DESKTOP_PACKAGE_ROOT` |

The host sources are copied into `desktop/host/` in the source tree's own layout
(`desktop/src-tauri`, `application`, `platform`), so manifest path dependencies
resolve inside the declared directory.

`node --test native/desktop/tests/shell-token.test.mjs` checks the top-frame gate
of the token script.

The window cannot be checked without an interactive desktop. A process in
Windows Session 0, where services and service-hosted runners and agents run, has
no visible window station, so the host selects the CLI passthrough and `--gui` exits
with 69. A person therefore runs the window smoke from an interactive logon
session. Set `CADRUMO_LOCAL_STORAGE_ROOT` to a disposable absolute directory first
unless the run should use the default root, build `desktop-run`, and check:

- The window opens on the documentation index in the output language, and a
  documentation search returns results.
- The Console tab shows a PowerShell prompt in the home directory and the Python
  tab shows `>>>`. The TUI pane shows the TUI, or its refusal line and exit when
  no runtime admits it.
- The Logs tab lists host events and Python records and no terminal text.
- F5, Ctrl+R, Ctrl+P and F12 change nothing, and right-click opens no browser
  menu in either the shell or the documentation.
- An `https:` link in the documentation opens in the system browser.
- Closing the window ends `cadrumo.exe` and every terminal child, and the next
  launch restores the window's size, position and maximized state.
- A second launch brings the open window forward and exits with 0.

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
  own session's two events. When they exist it first consumes an acknowledgement
  already set, with a zero-timeout wait, then sets the activation event and waits
  up to 500 ms for the acknowledgement; an acknowledgement means the window was
  activated, and the claimant exits with 0. Without one it checks the lock again
  and sends a new request.
- When the lock is held and the claimant's session has no activation event for
  500 ms, the holder is in another session. The claimant sets nothing, writes
  `{"outcome":"open_in_other_session"}` as one line on standard error and exits
  with 0.
- The holder acknowledges only a request it accepted. Once its window is closing it
  stops acknowledging, so claimants keep checking until the lock is released. A
  claimant gives up after 10 s with a `timed_out` launch error.
- Events have no content: a request carries nothing from the claimant, and an
  acknowledgement does not name the request it answers. Consuming a set
  acknowledgement before each request keeps a late one, given after its claimant
  stopped waiting, from answering a later claim. An acknowledgement the holder sets
  for a request it took before that point can still answer the later claim; the
  holder was then still accepting requests.

The names are predictable: the family is public, and any local account can look up
another account's SID. Another local account can therefore create any of these
objects first, from any session and without a privilege. A claimant refuses such an
object, since it cannot open it with full access or does not own it, so the GUI
launch exits with 77 and `instance_lock_foreign` while the other account keeps a
handle to the object open. Nothing reaches that account: no request, no
acknowledgement and no handle to the user's own objects. The headless CLI
passthrough is unaffected. Administrators and `SYSTEM` can deny the GUI in other
ways too, so this risk concerns other standard accounts.

A private namespace whose boundary holds the user's SID would prevent this, since
`CreatePrivateNamespace` requires the caller to be within the boundary. It is not
used. Microsoft documents neither whether such a namespace is visible from the
user's other sessions nor a lifetime this lock can rely on. The documentation says
the namespace can no longer be opened once its creator's handle closes. On Windows
11 build 26200 it stays open while any process holds a namespace handle, and once
none does, `CreatePrivateNamespace` makes a separate namespace in which a second
claimant would take a second lock.

On Linux the objects live in `$XDG_RUNTIME_DIR`, which must deny group and other
access, so no other account can create or reach them.

| Object | Name |
| --- | --- |
| Lock | `<family>.desktop.lock`, held with an exclusive `flock` |
| Activation | `<family>.desktop.session.<session>.activate`, a Unix stream socket the holder binds |

- `<session>` is `XDG_SESSION_ID`, or `unnamed` when it is unset. It is letters,
  digits, `-` and `_`.
- On taking the lock, the holder removes every
  `<family>.desktop.session.*.activate` socket, then binds its own.
- A claimant connects to its own session's socket and writes nothing. The holder
  reads nothing and writes the byte `0x01` for a request it accepted, on the
  connection that carried it, so a late acknowledgement reaches no later claim.
  Timing, the other-session report and the exit status match Windows; a socket that
  is missing or refuses the connection counts as absent.

macOS runs no desktop GUI and takes no lock.

## Manager startup and supervision

The Windows manager admits an unelevated interactive session, escapes a parent
job once when permitted, and retains its session lock while its hidden top-level
window runs. Startup verifies the selected package and queries its installed
interpreter for the canonical physical storage identity and application version.
The query uses the same strict child environment as runtime launch and acquires
no runtime endpoint. Ownership supplies either a start permit, direct same-session
adoption, or an observer/wait role; observers never signal another session's runtime.

Supervisor heartbeat messages carry required `in_flight_operations`, an exact
nonnegative operation count or JSON `null` when observation is unavailable. A
hosted profile is not an in-flight operation, and unknown counts never prove idle.
Python and Rust readers share conformance vectors in
`manager/tests/protocol_vectors.json`. Session-end fences admissions before
settling workers; cancellation waits for that supervisor to finish before restart.

Installed Windows manager packages use the version-independent layout projected
from `native/package-layout.json`: `versions/<major.minor.patch>/` contains the
unchanged package, including its root-level manager and desktop images. The prefix
contains a copy of the manager image as the stable entry and a closed
`data/installation.json` marker (schema, application ID, channel, platform and ABI).
The distribution writes `Software/<application-id>/EntryPoint` for its current
machine-scope MSI registration. Discovery reads the 64-bit Windows registry view
in both HKCU and HKLM; archives derive their prefix from this declared layout.

`native/application` owns the shared read-only catalogue. It bounds the directory
inventory, refuses redirected paths, checks identity, target and ABI, verifies the
complete package inventory and manager executable, and selects the newest numeric
version. Incomplete or incompatible versions do not win. The stable entry must
match a manager in a complete compatible version. These consistency checks do not
authenticate a publisher or sandbox a concurrent same-user file writer.
The desktop dispatches the verified stable entry. After native admission and job
escape, that entry (or an older version's manager) redirects to the selected
version before taking the session lock or runtime ownership. The successor repeats
admission and resolves the canonical installed default; an override never becomes
managed through environment clearing. Dispatch still acknowledges launch only.

This startup composition supports the selected complete package. Version cutover,
manager IPC and tray controls remain separate plan work. A failed-version marker
blocks startup/adoption conservatively until the installation catalogue can
interpret it. GUI-subsystem startup failure is visible after interactive admission;
session 0 remains refused without UI. Tests of the hidden window's own queue do
not constitute real session-1 logoff or desktop package acceptance.

## Native distribution definitions

`native/cmake/distribution` packages an already assembled payload. Its shared
identity projection covers Windows x64, Linux x64/ARM64 and macOS ARM64. The
application ID is `md.neve.cadrumo`; the preview channel adds `.preview`. Upgrade
UUIDs are deterministic per application/channel, target and machine installation
scope. They do not change with the version. MSI product/package codes retain their
separate release lifetimes. Publisher, license, version and names come from the
existing Python product and project metadata owners.

Configure with CMake 4.4.3, `-S native/cmake/distribution`, the target's preset and
`-DCADRUMO_PAYLOAD=<absolute-payload>`. The presets are `distribution-windows-x64`,
`distribution-linux-x86-64`, `distribution-linux-aarch64` and
`distribution-macos-arm64`; each sets `CADRUMO_TARGET` and the binary directory
`build/<preset name>`. Build `installation_prepare` to validate and stage the
selected payload. Changes to its contents refresh the stage during the build;
unchanged content preserves the existing output. `clean-installation_prepare`
removes generated staging outputs while retaining historical uninstall receipts
under `installation/receipts`.
Set `CADRUMO_DEV_PYTHON` explicitly when the checkout's development interpreter is
not available. `CADRUMO_CHANNEL` selects `stable` or `preview`. An optional
`CADRUMO_DESKTOP_EXECUTABLE` must name an actual file in the hashed payload
inventory, and that file must be the application image the payload manifest's
platform mapping marks `desktop`, such as `cadrumo.exe` on Windows. Only that image
receives desktop registration. macOS requires a root-level desktop executable. Its runtime backend and WebView containment validation
must be completed before a macOS application release.

CPack definitions select MSI/ZIP on Windows, DEB/RPM/TGZ on Linux, and DMG/TGZ on
macOS. Build the CMake `zip` target for the install-defined portable archive.
For a native installer, first build `installation_prepare`, then run
`cpack --config <build>/CPackConfig.cmake -G <generator>` on the native
packaging host. WiX .NET tooling and its matching UI extension are prerequisites
for MSI; current WiX 7 also requires operator acceptance of its OSMF EULA. CPack's
`CPACK_WIX_VERSION=4` selects the WiX XML/tool interface, not a claim that WiX 4
is the latest release. Set `CPACK_WIX_PRODUCT_ICON` to the generated product ICO
when producing the Windows installer. DEB requires dpkg tooling; RPM requires
rpmbuild. Signing, notarization and native launch/upgrade tests remain release gates.

Windows payloads declaring the manager stage under `versions/<version>` with the
stable entry at the installation prefix. The desktop shortcut targets that
version's root-level desktop image; installer-added notices stay outside its
immutable inventory. Payloads without a manager retain the existing `app` layout.
MSI owns Start menu/uninstall registration. Its existing major-upgrade policy,
dual-scope authoring and disposable-host upgrade acceptance remain rollout work;
the catalogue alone does not implement manager cutover or obsolete-version removal.
Linux installs under `/opt/cadrumo` with desktop/icon registrations
under `/usr/share`. Preview uses separate names. macOS packages a CADRUMO.app
bundle for the Applications folder. Runtime storage remains owned by Settings;
these definitions add no services, scheduled tasks or automatic launch.

For development, `cmake --install <build> --prefix <absolute-test-prefix>` uses
relative installation definitions. Set `CADRUMO_UNINSTALL_PREFIX` to that exact
prefix, then build the `uninstall` target. The external `installation/metadata/installation.json`
receipt binds removal to the installed package manifest and unchanged file hashes.
When staging has advanced, select the retained receipt for the older installation
with `CADRUMO_UNINSTALL_RECEIPT`.
Changed files and unowned content remain. Symlink/junction traversal and filesystem
root removal are refused. Native package managers own uninstall for system packages;
the prefix helper is for isolated development installations. It refuses removal
when multiple version packages share the prefix, preserving their common entry
and marker until the package owner implements version removal.
