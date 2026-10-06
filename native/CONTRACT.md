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

`P` means installed package root; `U` means the effective storage root that the
storage owner declares in `src/cadrumo/core/storage_environment.py`. An absolute
`CADRUMO_LOCAL_STORAGE_ROOT` wins in every mode. Without it, a source checkout
uses `var/storage` beneath the checkout and an installed package uses the
per-user, per-channel default in the mutable-root row. The storage owner decides
the mode by where the package tree lives, never by the working directory.
`<name>` is `cadrumo` for the stable channel and `cadrumo-<channel>` for any
other, such as `cadrumo-preview`; the channel comes from the identity projection.

| Location | Windows x64 | Linux mapping, unimplemented | macOS mapping, deferred |
| --- | --- | --- | --- |
| Executables | `P/python.exe`; application images such as `P/cadrumo.exe` and `P/cadrumo-manager.exe`; console entrypoints such as `P/bin/cadrumo-runtime.exe` and components in `P/bin/` | Private prefix `P/bin/`; system command wrappers depend on packaging format | `Cadrumo.app/Contents/MacOS/` |
| Python | `P/python.zip`; dependencies in `P/cadrumo/site-packages/`; controlled `P/cadrumo/python.pth` | Private `P/lib/cadrumo/python.zip` and site-packages | `Contents/Resources/python.zip` and site-packages |
| Native modules/libraries | `P/bin/`, qualified extensions beneath `bin/packages/` | Private `P/lib/`; extension identities retained | `Contents/Frameworks/`, extension package subtrees |
| Immutable resources | `P/data/`, `P/docs/` | `P/share/cadrumo/` | `Contents/Resources/data/` and `docs/` |
| Mutable root | `%LOCALAPPDATA%\<name>`; checkout `var/storage`; delivered-artifact tests supply an explicit root | `$XDG_DATA_HOME/<name>` when `XDG_DATA_HOME` is absolute, else `$HOME/.local/share/<name>` | `$HOME/Library/Application Support/<name>` |
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
search files of each language, the language set and the `media_types` table of
files the documentation scheme serves. Each language must be one of
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

The desktop host serves only `files` members and derives the documentation
origin's CSP from `script_hashes`; [Desktop shell](#desktop-shell) describes the
handler. It reads the manifest once at startup and does not rehash a file per
request; the package checks below own the digests. The shell CSP does not govern
the documentation.

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

The host takes its package root from `CADRUMO_DESKTOP_PACKAGE_ROOT` when that is
set and otherwise from its own directory. It checks the package manifest's
platform and ABI against the generated contract and the interpreter against its
manifest digest. It then runs the fixed query `src-tauri/src/python/environment.py`
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

The webview profile directory is the absolute path the query resolves for the
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
`P/docs/user/`. It reads `manifest.json` once at startup and never walks or
rehashes the tree; the package checks above own the digests. Each request is
answered as follows:

- Methods other than GET and HEAD receive 405 with `Allow: GET, HEAD`.
- A host other than the scheme's own `localhost` receives 404. Wry hands every
  `http(s)://cadrumo-docs.*` host to the handler, so the handler checks it.
- A path with a backslash, a colon, an empty or dot segment, a control
  character, a Windows reserved name or character, or a percent escape of `/`,
  `\`, `.`, `%` or a control receives 400. A path ending in `/` names its
  `index.html`.
- A path absent from the manifest's `files`, a file name the media-type table
  does not type, a link or reparse point, and a file resolving outside the
  canonical root receive 404.
- A served file carries its media type, `Content-Length`, the documentation
  policy, `X-Content-Type-Options: nosniff` and `Cache-Control: no-cache`.
  Refusals carry the same policy and `nosniff` with an empty body.

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

`src-tauri/src/logs/` merges two sources, polled every 100 ms. `source` is an
open enumeration:

- `python`: the log file the query reports (`cadrumo.log` in the log directory)
  and its numbered rotations, which Python writes through its secret-scrubbing
  filter. The
  line format comes from the query, so the host holds no copy of it.
  Continuation lines such as tracebacks become the record's `detail`, up to
  64 KiB. A record completes after its file has been quiet for 250 ms. Python
  records carry the raw `asctime` with `timestampMs` and `process` null, because
  that time has no UTC offset.
- `host`: the host's diagnostics events, logged as `desktop`, with an RFC 3339
  UTC timestamp, a level and the process role and pid where the event has one.
  Captured child output is never requested, so terminal bytes cannot appear.

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

The desktop holds no runtime connection and no runtime authority. The TUI tab
runs the TUI process and shows only its output, including the reason the TUI
writes on standard error and its exit when no runtime admits it. Starting or
reaching a runtime manager and the sign-in host commands are not implemented:
the desktop starts, stops and authenticates nothing.

### Desktop build and test procedure

The desktop is a standalone CMake project. Configure `native/desktop` in its own
binary directory with `CADRUMO_NATIVE_CONTRACT` naming the generated
`contract.json` of a configured source build, and `CADRUMO_DESKTOP_PACKAGE_ROOT`
naming an assembled package such as `stage/<Config>/app/`. Set
`CADRUMO_DEV_PYTHON` when the checkout's development interpreter is not found.
The standalone project's host runs from its Cargo output and finds the package
through `CADRUMO_DESKTOP_PACKAGE_ROOT`. The source build configures this project
only when a desktop image is staged, which requires the documentation; a `bundle`
with the documentation then stages `cadrumo.exe` at the package root as an
[application image](#application-images). Without it, configuring the source build
needs neither Node.js nor npm.

| Target | Operation |
| --- | --- |
| `desktop-frontend-install` | `npm ci` in the frontend |
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
inventory, and that file must be the application image the payload manifest's
platform mapping marks `desktop`, such as `cadrumo.exe` on Windows. Only that image
receives desktop registration. macOS requires a root-level desktop executable. Its runtime backend and WebView containment validation
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
