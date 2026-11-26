# Build loop: the cheapest build that proves a change

A native build is the most expensive thing a developer can start, so pick the smallest target that shows what you need. This reference is the procedure; the build references describe the systems themselves ([CMake and packaging](build-cmake-and-packaging.md), [Rust crates](build-rust-native-crates.md), [desktop shell](build-tauri-desktop-shell.md), [frontend](build-desktop-frontend.md), [Python packaging](build-python-packaging-and-release.md)).

## Which loop for which change

| Change | Fastest proof | Needs a native build |
|---|---|---|
| Python backend | focused pytest, then the owning lane ([testing](dev-testing-lanes-and-gate.md)) | no |
| Frontend component or page | `just dev` or Storybook, then `just check-frontend` | configured preset only |
| Frontend behaviour under test | `just test-frontend` | configured preset only |
| Rust crate logic | `just test-native`, or one crate target | partial |
| Desktop host (Tauri) logic | target `desktop-host-unit-test` | partial |
| Environment contract or package layout | target `native_contract`, then the conformance CTests | partial, then bundle |
| Anything about the assembled application | `just build-native Debug` and run it | yes |
| Installers, ZIP, release artefacts | `just test-native-package`, `just test-native-release` | yes, Release |
| Python wheels and sdists | `just build-distributions`, `just test-packaging-preflight` | no |

## From a fresh checkout to a bundle

1. `just setup` (or `just init`): Python environment, `env/.env`, published authority, frontend packages, fixture projections.
2. `just configure-native-agent <agent folder>`: configures the host preset with `CADRUMO_PACKAGE_AGENT_SOURCE_DIR` naming a local cadrumo-agent project folder. Configure fails without it; the value is kept in the CMake cache and is never read from the environment ([recipe](../../../../justfile#L823), [agent module](../../../../native/cmake/Agent.cmake#L4)).
3. `just build-native Debug` (default configuration is Release, default target `bundle`). The staged application is under `build/<preset>/stage/<Configuration>/app`. The first build downloads the pinned CPython SDK and the local model server ([recipe](../../../../justfile#L762)).

Every binary directory is `build/<preset>`; other names are refused, and no build output may be written under `native/` or any source folder.

## Narrower targets

`just build-native <Configuration> <TARGET>` builds one target. Useful ones:

- `native_contract`: regenerates the contract files from the environment declaration.
- `rust_application`, `rust_manager`: one Rust crate.
- `python_product`: the product wheels.
- `app-native`: the native images into an existing stage, without touching the Python payload.
- `app-agent`: the bundled agent only.
- `app-payload`: full assembly.
- `user_docs`: the packaged documentation.
- `desktop-frontend-build`, `desktop-host-build`: the frontend bundle and the desktop host.

Desktop targets can also be built directly once configured: `cmake --build --preset debug --target <name>`, for example `desktop-host-unit-test`, `desktop-host-test`, `desktop-host-clippy`, `desktop-frontend-test` and `desktop-run`.

## What invalidates what

- Build steps are fingerprinted by content hash with receipts; an unchanged input set is reused.
- **Any edit under `src` stales the product wheels and the packaged documentation**, because both fingerprint the whole `src` tree (the documentation also covers `docs` and `dev/docs`). There is no Python-only incremental target for a built bundle: a backend change means `python_product` and reassembly through `just build-native` or `app-payload` ([package inputs](../../../../native/cmake/PackageInputs.cmake#L18), [docs inputs](../../../../native/cmake/Docs.cmake#L30)).
- **The documentation build is the slow part of a bundle.** `bundle` requires `user_docs` while the cache option `CADRUMO_PACKAGE_USER_DOCS` is on. Configuring with `-DCADRUMO_PACKAGE_USER_DOCS=OFF` skips it for behaviour work; such a bundle has no documentation and is not a release candidate. `CADRUMO_DOCS_SHARED_CACHE` (on by default) reuses a documentation build for an identical source graph ([docs module](../../../../native/cmake/Docs.cmake#L20), [bundle dependency](../../../../native/cmake/Packaging.cmake#L47)).
- **The agent is packed from the named agent folder as it is on disk.** Editing that folder during a build breaks or contaminates the build.
- `desktop-host-test` needs the frontend build, the documentation and `app-payload`; `desktop-host-unit-test` needs none of them.
- Do not run two builds of one preset at once.

## Frontend loop

- `just dev` publishes the authority when stale, installs frontend packages, seeds fixture projections and serves the frontend with a simulated host on fixed ports. It compiles no Rust, but it needs the host preset configured (so the agent folder set) because it builds generated frontend inputs through CMake. It is a resident process: run it in the background and stop it by its own process id.
- Storybook: `npm run storybook` in `native/desktop/frontend`.
- `just check-frontend` runs the type check, lint, contract `--check` scripts and unit guards; `just test-frontend` runs the check and the Playwright specs. Run from the frontend folder, `npm run check` and `npm test` need `CADRUMO_CMAKE_BINARY_DIR` set, which the recipes do for you.
- The frontend shows what the host serves. When a frontend check fails on a contract file, the backend model changed: regenerate the contract ([generated artefacts](dev-generated-artefacts.md)), do not edit the TypeScript.

## Rust loop

- `just test-native` builds the contract, metadata and application crate and runs the Rust unit tests (CTest cases ending in `.rust`).
- `just check-rust` builds the contract and metadata and runs the `rust_quality` CTest label (rustfmt, clippy, cargo-deny). It needs network for advisories.
- Crates include generated contract sources, so a bare `cargo` command does not compile them; go through CMake.

## Python distributions

`just build-distributions` (also `just build-release`) builds the root project and the companion data packages with `uv build` into `build/distributions` and refuses any file over the index size cap. It consumes the published authority as it is, so publish first. `just test-packaging-preflight` checks dependency surface, shipped data and packaging contracts without CMake.

## Verification targets

| Recipe | Does |
|---|---|
| `just test-native-bundle` | Builds the bundle and runs CTest, excluding tests that need external tools |
| `just build-native-package` | Builds the bundle and the ZIP, no verification |
| `just test-native-package` | Builds the ZIP, extracts it to a path with spaces and non-ASCII characters and probes it |
| `just test-native-release` | One graph: ZIP, CTest, extracted-artefact verification and documentation verification |

## Constraints on where things run

- **Interactive desktop session only:** `desktop-run`, packaged-window tests, `just test-os-keychain`, `just test-runtime-auth`, `just test-native-live`.
- **Network:** the first native build, `just check-rust`, `just check-native-code`, `just check-dependency-vulnerabilities`, `just test-installed-oracles`, `just setup-desktop-browser`, `just setup-locale-spelling`.
- **Disk:** native builds and their caches are large; check free space on the build drive and the system drive before a Release build.
- **Cleaning:** `just clean` only reports. `just clean-apply` deletes irreversibly, including outside the worktree. Never delete under another session's `build/` tree.

## Working notes

- Build in the background and read the log when it ends; a quiet build is usually the documentation step, not a hang.
- State what a build carries: which head, which configuration, documentation on or off. A local build, package or export is a file on disk, not a release and not an installed, working product.
- Prove backend behaviour with tests before building. A build is for what only the assembled application can show.
