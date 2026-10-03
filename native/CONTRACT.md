# Native distribution contract

Status: Windows host and ABI compiled; artifact verification in progress. Linux and macOS are mappings to
prove, not supported native builds. The existing Python product owns application
behavior. Native code owns bootstrap before Python exists.

## Source and generated ownership

| Concern | Authored owner | Generated output |
| --- | --- | --- |
| C interpreter host and CPython initialization | `native/interpreter/` | `.artifacts/native/build/` |
| Shared Rust platform implementation and C ABI | `native/platform/` | `.artifacts/native/cargo/` |
| Package-only layout declarations | `native/package-layout.json` | `.artifacts/native/generated/` |
| Build-time contract projection | `dev/packaging/native/` | C header, Rust constants, JSON contract |
| Windows orchestration and package assembly | `dev/packaging/native/` | `.artifacts/native/package/` |
| Product identity | `src/cadrumo/core/product_identity.py` | Native product identity |
| Settings names and validation | `src/cadrumo/core/config.py` | Reserved environment names |
| Secure location names and semantics | `src/cadrumo/core/storage_taxonomy_locations.py` | Native taxonomy inventory |
| Exact Python version | `dev/packaging/release-python-version` | Build input |
| Third-party dependency closure | `pyproject.toml`, `uv.lock`, existing constraint exporter | Installed locked dependencies |
| Python release cohort | `dev/packaging/python_cohort.py` | Existing three-wheel cohort |

Generated files never become an alternative authored inventory. Development
generators do not ship. Each assembly starts in a fresh directory. Runtime paths
are resolved from the executable and Windows Known Folders, never compiled from
the build machine. Mutable state does not belong in any build or installed tree.

## Platform mappings

`P` means installed package root; `U` means the application user root.

| Location | Windows x64 proof target | Linux mapping, unimplemented | macOS mapping, deferred |
| --- | --- | --- | --- |
| Executables | `P/python.exe`, future `P/cadrumo.exe`; components in `P/bin/` | Private prefix `P/bin/`; system command wrappers depend on packaging format | `Cadrumo.app/Contents/MacOS/` |
| Python | `P/python/Lib/`, `site-packages/` beneath it | Private `P/lib/python3.13/` | `Contents/Resources/python/` |
| Native modules/libraries | `P/bin/python/`, package-relative subtrees retained | Private `P/lib/`; extension identities retained | `Contents/Frameworks/`, extension package subtrees |
| Immutable resources | `P/data/`, `P/docs/` | `P/share/cadrumo/` | `Contents/Resources/data/` and `docs/` |
| User root | Known Folder LocalAppData + `cadrumo` | Absolute XDG_DATA_HOME + `cadrumo`, otherwise `~/.local/share/cadrumo` | `~/Library/Application Support/cadrumo` |
| Secure state | `U/data/`, existing bucket/keystore taxonomy beneath it | `U/data/` | `U/data/` |
| Loader | Static bootstrap CRT; explicit absolute DLL load with restricted search, then registered bundle directories | Relative ELF RUNPATH for every transitive dependency; audit LD_* and libc floor | Relative install names and rpaths; signing and hardened-runtime validation |

Linux deb/rpm, relocatable archive and AppImage are unresolved alternatives.
No build target or placeholder implementation claims those formats work.
macOS needs a native toolchain, architecture selection, codesigning and dyld proof.
Windows relocation is final only after real package-qualified extensions and
their transitive DLLs pass the artifact tests.

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

The native bootstrap supplies the existing Settings storage-root field as
`U/data/`; Python continues to own bucket routing, encryption, authorization and
member defaults. Existing local storage is outside this foundation's scope. The
host neither inspects nor migrates it; rollout transition policy remains deferred.

Package-only anchors are declared once. Existing taxonomy members remain owned
by Python and are projected at build time. A package must clear inherited Settings
overrides before supplying its effective values, so an ambient database URL or
per-member path cannot silently escape the declared root. The initial non-secret
override allowlist can be empty; accepting new overrides needs explicit schema
enrollment. It must not copy the development environment template.

Temporary files belong under `U/tmp`, caches under `U/cache`. Managed browsers,
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

```powershell
.venv/Scripts/python.exe -m dev.packaging.native.provision .artifacts/native/fresh
& dev/packaging/native/build.ps1 -CPythonRoot .artifacts/native/fresh/cpython-nuget/tools -Output .artifacts/native/fresh
.venv/Scripts/python.exe -m dev.packaging.native.product --output .artifacts/native/fresh/product --python .artifacts/native/fresh/cpython-nuget/tools/python.exe --dependencies .artifacts/native/fresh/dependencies
.venv/Scripts/python.exe -m dev.packaging.native.assemble --python .artifacts/native/fresh/cpython-nuget/tools --dependencies .artifacts/native/fresh/dependencies --build .artifacts/native/fresh/build/Release --destination .artifacts/native/fresh/package
.venv/Scripts/python.exe -m dev.packaging.native.verify --package .artifacts/native/fresh/package --destination 'C:/cadrumo-proof/CADRUMO espacio á 漢字' --product
```

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
