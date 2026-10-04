---
tags:
  - '#adr'
  - '#canonical-environment'
date: '2026-10-04'
modified: '2026-10-04'
body_schema: 'body-v2'
body_hash: 'sha256:0fc849e7f57dc0bfc4a6de8813c3973247857a60104c106ace775116c34de039'
related:
  - "[[2026-10-04-canonical-environment-reference]]"
  - "[[2026-08-03-canonical-storage-management-adr]]"
  - "[[2026-09-20-lud-authority-adr]]"
  - "[[2026-10-03-application-packaging-interpreter-foundation-adr]]"
  - "[[2026-07-13-data-output-standardization-adr]]"
  - "[[2026-07-03-claude-ecosystem-packaging-adr]]"
  - "[[2026-10-04-application-distribution-adr]]"
  - "[[2026-10-03-application-packaging-adr]]"
  - "[[2026-10-04-desktop-shell-adr]]"
  - "[[2026-10-04-runtime-manager-architecture-adr]]"
---

# `canonical-environment` adr: `Canonical location and environment contract` | (**status:** `accepted`)

## Problem Statement

Storage, log, cache, temporary and component locations are declared once in Python but resolved by several implementations: the core resolver, the Rust platform crate, the fixed Python query of the desktop host and ad hoc Python child launchers. In an installed build the default root follows the process working directory, so two children started in different directories can resolve different roots and different runtime endpoints. The user directed on 2026-10-04 that every location and its environment override come from one canonical, config-driven definition consumed programmatically by the Python product, the Rust host, platform and manager, the runtime and the frontend build, and that the delivered per-user default be settled. The runtime manager cannot ship without it. Grounding: `2026-10-04-canonical-environment-reference`.

## Considerations

- The typed taxonomy already declares every application-chosen location with override policy, scope and settings field; the root is its anchor, not a member (`2026-10-04-canonical-environment-reference`, Python owners).
- Two accepted records already require a platform user-data default for installed runs and `var/storage` for checkouts; current code resolves both against the project root, which is the cwd outside a checkout (`2026-07-03-claude-ecosystem-packaging-adr`, `2026-07-13-data-output-standardization-adr` R1, reference).
- `2026-10-03-application-packaging-interpreter-foundation-adr` superseded its own LocalAppData paragraph because the interpreter must not invent a storage policy; it directs the native host to consume the core storage owner. The owner has not yet declared an installed default.
- A per-channel identity exists only at build time (`dev/packaging/native/identity.py`); `PRODUCT_IDENTITY` has no channel. The runtime endpoint and `.runtime/` records are keyed by storage identity, so two channels on one root contend for one runtime (`2026-10-04-runtime-manager-architecture-adr`).
- The native host must set the root before CPython exists, and the pip or uvx distribution has no native host. Two resolver implementations are therefore unavoidable; drift between them is the risk to control.
- `2026-07-13-data-output-standardization-adr` rejected a platformdirs-style multi-root split; `2026-08-03-canonical-storage-management-adr` R3 moves no member path and R7 keeps relocation refuse-and-instruct. Rule 05 keeps private data in encrypted custody; rule 13 keeps profile selection out of the environment; rule 04 forbids services and scheduled tasks.
- Development tool caches (`TOOL_STORAGE_LOCATIONS`) are projected into the installed allowlist, and the desktop currently anchors its webview profile under the tool cache (reference, native consumers).

## Considered options

- **Keep the Python declaration, specify one resolution algorithm, and generate test vectors both resolvers must pass:** chosen. Extends the existing owners and generator; no second authority.
- **Rust platform becomes the sole resolver and Python only consumes pinned variables:** rejected. The pip and uvx distributions and the development loop have no native host, so Python would need a resolver anyway.
- **Python is the sole resolver and native hosts always ask it (the desktop fixed-query pattern):** rejected. The C host must set the root before CPython initializes; a query child would itself need a root; the runtime manager must not depend on launching Python to find its own records.
- **Per-user default as the OS application-data directory, one root for every category:** chosen. Matches the accepted single-root ruling and the proposed `U` sketch.
- **Home dot-directory `~/.cadrumo` on every OS:** rejected. Non-idiomatic on Windows and macOS, no gain over the OS directory.
- **Package-relative or cwd-relative root for installed builds:** rejected. The installed package is read-only and the cwd is arbitrary.
- **One shared root for stable and preview channels:** rejected. Two code versions over one encrypted store and one runtime endpoint; each manager treats the runtime of the other channel as foreign.

## Constraints

Binding commitments.

- **One declaration.** The storage taxonomy (`STORAGE_TAXONOMY`) plus one root declaration in `src/cadrumo/core/storage_environment.py` is the canonical definition of every location, variable name, default rule, override rule and reserved status. No other module, crate, script or document may spell a `CADRUMO_*` location variable name or a location subpath as a literal; they read the declaration or its generated projection. This includes `dev/packaging/native/generate.py`, `native/desktop/src-tauri/src/python/environment.py`, `src/cadrumo/core/_config_runtime.py`, `src/cadrumo/entrypoints/cli/main.py` and `src/cadrumo/adapters/persistence/storage/custody/_kdf_process.py`.
- **One generated projection.** `contract.json` written by `dev/packaging/native/generate.py` is the only artifact consumers read. `contract.rs` and `contract.h` derive from the same run. CMake, the Rust crates (`native/platform`, `native/application`, the desktop, `native/manager`) and the frontend build consume it; none keeps a copy of a name or default. The frontend build consumes locations only through generated JSON, and the shell receives resolved paths over IPC.
- **Resolution never reads the working directory.** Mode is decided by package or checkout evidence. The `Path.cwd()` fallback at `storage_environment.py:16` and the working-directory walk at `native/platform/src/lib.rs:31-33` are removed. A process that cannot determine its mode or its OS base directory refuses with an instructive error; it never silently chooses the cwd.
- **Resolve once, pin, inherit.** The outermost product process resolves the root once and pins it in the environment of every child under the Settings-owned root variable. A process that inherits the pin validates it and never re-resolves. No binary adds a storage, log or Settings variable to a child beyond the pinned set the contract declares. This generalizes the `2026-10-04-desktop-shell-adr` constraint to every binary.
- **Two resolver implementations, one oracle.** Python (`storage_environment.py`) and the Rust platform crate implement the same algorithm. The generator emits conformance vectors (inputs: platform, mode, environment, home or Known Folder, channel; output: root) that both implementations must pass in CI. Divergence fails the build.
- **Development tooling stays out of the product.** `TOOL_STORAGE_LOCATIONS` and `XDG_*` tool variables are development concerns. The installed host, the desktop and the manager neither set nor allowlist them. The product allowlist is the root variable plus the settings fields of operator-overridable taxonomy members.
- **Per-channel roots.** Each release channel has its own default root. The channel comes from the identity projection (`dev/packaging/native/identity.py`, `CADRUMO_ID_*`, `data/build.json`) and nowhere else. Python never derives a channel; a native package pins the root before Python runs.
- **No migration, no compatibility reader.** Existing `var/storage` trees created by installed builds under a launch directory are not discovered, read or moved. Relocation remains refuse-and-instruct (`2026-08-03-canonical-storage-management-adr` R7). The pre-release regime applies.
- **Prior rulings reused unchanged.** `2026-09-20-lud-authority-adr`: the configured root is application-owned and created idempotently even when selected explicitly; explicit member overrides must pre-exist. `2026-08-03-canonical-storage-management-adr` R1, R3, R5, R10: members are typed, no member path moves, `FIXED` members carry no variable. `2026-07-13-data-output-standardization-adr` R1 and `2026-07-03-claude-ecosystem-packaging-adr`: installed runs use a platform user-data root, checkouts use `var/storage`.
- **Scope exclusion.** No configuration file is introduced. The product reads the process environment only (`src/cadrumo/core/config.py:199-214`); the proposed `U/config/application.env` in `2026-10-03-application-packaging-adr` stays proposed and is a separate decision.

## Implementation

We will make the Python core storage owner the single declaration of every location and environment control, project it through the existing native contract generator into one versioned `contract.json`, and give installed builds a per-user, per-channel, cwd-independent default root that the native host resolves once and pins for every child. Items marked *hypothesis* may change within the Constraints.

**Declaration (storage owner: `src/cadrumo/core/storage_environment.py`, `storage_taxonomy_locations.py`).**

- A typed root declaration beside `STORAGE_ROOT_SETTINGS_FIELD` carries: the primary variable `CADRUMO_LOCAL_STORAGE_ROOT`; the development-shared variable `CADRUMO_STORAGE_ROOT` with lower precedence (retained; its retirement is a named follow-on, not made here); the development default `var/storage` relative to the checkout; the installed default rule below; the relative-override rule; and the refusal rule. *Hypothesis:* a frozen pydantic model `StorageRootDeclaration` in `storage_environment.py`, kept import-light.
- `project_root()` keeps its checkout test (module location beside `pyproject.toml`) and loses the cwd fallback. A module outside a checkout is in installed mode.
- `platform_user_data_root()` in `config_state_root.py` returns the real per-user base in installed mode and the checkout in development mode; `resolve_project_path` and relative member overrides keep anchoring to it, so the "never the process cwd" promise at `src/cadrumo/core/paths.py:194-200` becomes true in installed mode.
- `_config_runtime.py:38-40` and the env-source alias at `config.py:115-117` read precedence from the declaration (closes `2026-08-03-canonical-storage-management-adr` R19).
- `Settings.storage_env_var_names()` narrows to the product allowlist: the two root variables plus the settings field of every `OPERATOR_OVERRIDABLE` member. Development tool variables get their own accessor used only by `dev/` and the justfile. *Hypothesis:* `development_tool_env_var_names()` beside it.
- New taxonomy members: `DESKTOP_WEBVIEW` (`webview`, directory, root scope, `OPERATOR_OVERRIDABLE` with `cadrumo_webview_dir`, grouping `CACHE`, fingerprint `EXCLUDED`; lifecycle *hypothesis* `UNBOUNDED_BY_DESIGN` because the renderer owns its own eviction) replaces `environment.rs:114`. `.runtime/` and its `installation.json`, `boot.json` and `manager-*` records become `FIXED` members registered by the runtime manager decision; this ADR only requires that `installation.py:36` stop joining the literal. `RUNTIME_SOCKETS` (`runtime`) and `.runtime/` are distinct directories and both stay.

**Installed default root (per OS, per channel).** Let `name` be `PRODUCT_IDENTITY.python_package` (`cadrumo`) for the stable channel and `python_package` plus `-` plus channel for any other channel (`cadrumo-preview`), produced by the identity projection, never spelled by a consumer.

| Platform | Default root | Base lookup |
| --- | --- | --- |
| Windows | `%LOCALAPPDATA%\<name>` | `FOLDERID_LocalAppData` through `SHGetKnownFolderPath` in Rust; `LOCALAPPDATA` in Python with no fallback |
| Linux | `${XDG_DATA_HOME:-$HOME/.local/share}/<name>` | `XDG_DATA_HOME` when absolute, else `HOME` |
| macOS | `~/Library/Application Support/<name>` | `HOME` |

- Local, not roaming: the tree holds an encrypted store with its keystore, caches and browser profiles. Operator backup goes through explicit export, not through OS profile sync.
- Every taxonomy member keeps its current subpath under this root; the proposed `U/data/` regrouping in `2026-10-03-application-packaging-adr` is not adopted (`2026-08-03-canonical-storage-management-adr` R3).
- Creation: the first product process that needs the root creates it idempotently (`ensure_storage_tree`, `2026-09-20-lud-authority-adr`); the native host also creates it before CPython starts as today (`lib.rs:132-137`), refusing reparse points. POSIX mode `0o700` on the root, matching the existing temporary-directory hardening; Windows inherits the per-user ACL of `LocalAppData`. *Hypothesis:* the mode-bits test required by `2026-08-03-canonical-storage-management-adr` Constraints covers the new default.
- Channels: stable and preview resolve different default roots and therefore different runtime endpoints, `.runtime/` records and managers. An account may install both. Development builds carry no channel: a checkout resolves `var/storage` regardless of `CADRUMO_CHANNEL`. The pip and uvx distribution is stable only; a preview native package always pins the root through its host, so Python computes only the stable default.
- Overrides: an absolute `CADRUMO_LOCAL_STORAGE_ROOT` wins in every mode and channel, is operator-owned, and is unmanaged by the runtime manager; an operator who points two channels at one root accepts one shared runtime. A relative override anchors at the checkout in development mode and is refused in installed mode. Blank values are ignored as today. `CADRUMO_STORAGE_ROOT` keeps its lower-precedence development role and is not projected into installed packages.
- Reserved: `FIXED` members have no variable; `CADRUMO_ACTIVE_PROFILE` stays severed; `CADRUMO_AUTHORITY_ROOT` is pinned by the native host to the package authority and is not an operator override in installed mode (*hypothesis:* keep it allowlisted for development only).

**Mode detection.**

- Rust: installed when the executable directory, adjusted by `package_root_from_executable`, contains the package manifest named by `native/package-layout.json` (`data/package-manifest.json`); development when `pyproject.toml` is an ancestor of the executable directory; otherwise refuse. The `CADRUMO_DESKTOP_PACKAGE_ROOT` development selector keeps naming a package root explicitly.
- Python: development when `storage_environment.py` lives in a checkout beside `pyproject.toml`; otherwise installed. A native package never reaches the installed default because the host already pinned the root; the installed default serves pip and uvx installs.
- Neither reads the working directory, `sys.argv` or a Settings value to decide mode.

**Process environment.** The contract declares three classes and two profiles; every launcher builds a child environment from them.

- `cleared`: `PYTHON*`, `VIRTUAL_ENV`, `CONDA_PREFIX`, `CONDA_DEFAULT_ENV`, `__PYVENV_LAUNCHER__`, every `CADRUMO_*` name not in the product allowlist, every reserved Settings name not in the product allowlist (today `lib.rs:139-159`).
- `pinned`: the root variable set to the resolved absolute root; `TEMP`, `TMP`, `TMPDIR` set to the resolved `TEMPORARY_FILES` member; in a native package also `CADRUMO_AUTHORITY_ROOT` set to the package authority. Nothing else.
- `passed`: the product allowlist as received (operator profile only) and ambient OS variables not cleared.
- Profiles: `operator` (CLI passthrough, desktop terminals, profile workers) passes allowlisted overrides; `strict` (runtime manager, KDF child) passes none and pins only. The manager rule "no `CADRUMO_*` overrides" in `2026-10-04-runtime-manager-architecture-adr` is the `strict` profile.
- Pin, do not re-resolve: `environment.rs` keeps the S02 pin; its `storage_root_disagreement` check becomes a parity assertion between the inherited pin and Settings. `profile_worker.py:254-267` and `_kdf_process.py:121-128` build from the declaration instead of local rules. *Hypothesis:* one Python helper `child_environment(profile, root)` in `storage_environment.py`, and one Rust function in `native/platform` consumed by the desktop, the C host and the manager through `native/application`.

**Projection and drift control.**

- `contract.json` gains `"schema": 1`, a `root` object (variables, precedence, development default, installed default rule per platform, channel naming rule, relative and refusal rules), a `locations` array (every member: category, subpath, variable or null, override policy, scope, node kind, grouping, lifecycle), `environment` (`cleared` patterns, `pinned` names, `allowlist.product`, `allowlist.development`, profiles), `mode` (manifest path, checkout marker) and `vectors` (conformance cases). `contract.rs` is generated from the same data in the same run.
- Gates: the existing allowlist parity test extends to the new sections; a Rust test in `native/platform` and a pytest in `src/cadrumo/core/tests` both consume `vectors`; a structural test over `native/**`, `dev/packaging/native/**` and `src/cadrumo/**` refuses a `CADRUMO_` location variable or a taxonomy subpath spelled as a literal outside the declaration and generated files, in the shape of the existing join-provenance gate (`2026-08-03-canonical-storage-management-adr` R9). The CMake `settings_inputs` dependency keeps regeneration automatic; a stale `contract.json` is a build defect.

**Rollout and ownership.** Order is fixed; owners are the current file owners.

1. Storage owner (`src/cadrumo/core`): declaration, cwd removal, installed default, allowlist split, conformance vectors, Settings cache key and CLI and KDF literal removal, taxonomy member `DESKTOP_WEBVIEW`. Lands first; everything else consumes it.
2. Generator (`dev/packaging/native/generate.py`, `dev/packaging/tests`): schema 1 `contract.json` and vectors. Home: `2026-10-03-application-core-packaging-plan` S07, whose text already names `generate.py` and child-environment projections.
3. Rust platform (`native/platform/src/lib.rs`, Windows first): manifest-based mode, Known Folder default, no cwd walk, no `XDG_CACHE_HOME`, vector test. Same S07. Linux and macOS resolvers land with S04 and S05 of that plan.
4. Desktop (`native/desktop/src-tauri/src/environment.rs`, `python/environment.py`): webview member, parity assertion, no tool-cache field. Home: `2026-10-04-desktop-shell-plan` S04 (REPL cwd and child environment) and S07 (window-state and webview locations); S11 records the settled default in `native/CONTRACT.md`.
5. Runtime manager (`native/manager`, new): consumes the projection through `native/platform`; registers `.runtime/` and `manager-preferences.json` members in its own decision. The move of the desktop projection into `native/application` follows this ADR, as `2026-10-04-runtime-manager-architecture-adr` already states.
6. `native/CONTRACT.md` mutable-root rows and the allowlist sentence are rewritten by the owner of the Step that lands each change.

**Name clash check for the manager naming table** against `native/package-layout.json`, `native/platforms/windows-x64.json` and the CMake identity projection, read on 2026-10-04: `cadrumo-manager` collides with nothing, but it is a Rust executable, so it must enter the package through a desktop-style declaration in the platform mapping, not the `entrypoints` map, which `dev/packaging/native/layout.py` restricts to `[project.scripts]`. `{channel application_id}.manager` is consistent with the suffix rule in `identity.py:51-52`. `cadrumo-manager.log` beside `cadrumo.log` needs its own `LOG_FILE`-style member; the `LOGS` directory member already exists. `.runtime/boot.json` and `.runtime/manager-*` sit beside the literal `.runtime/installation.json` and must become members together. The pipe name `cadrumo-manager-{owner+session}` and the runtime endpoint `cadrumo-runtime-{storage_identity}` differ in key; with per-channel roots the storage identity differs per channel, so the contention the manager workstream describes does not arise on default roots.

**Amendments proposed with this record.** Apply only on approval; accepted bodies stay intact until then.

- `2026-10-03-application-packaging-interpreter-foundation-adr`, CMake amendment: "The interpreter does not establish a separate LocalAppData convention or migrate storage." becomes "The interpreter consumes the installed per-user default declared by the core storage owner in `2026-10-04-canonical-environment-adr` and migrates no storage." Consequences: "Later concurrent working-tree edits changed storage defaults and accepted overrides after the verified build. They have not been reconciled with this foundation contract." gains "Reconciled by `2026-10-04-canonical-environment-adr`."
- `2026-10-04-desktop-shell-adr` (proposed), Considerations: the bullet beginning "When no storage root is set in the environment, installed code resolves it against the" is replaced by "The storage root is pinned by the host from the canonical definition in `2026-10-04-canonical-environment-adr`; children inherit it whatever their working directory." Constraints: "The root that is pinned still depends on the launch directory until the storage owner settles a delivered per-user default. That question is open with the user." is deleted.
- `2026-10-04-runtime-manager-architecture-adr` (proposed), Considerations: "In an installed build the storage root falls back to the working directory." becomes "The installed default root is per user and per channel and is independent of the working directory (`2026-10-04-canonical-environment-adr`)." Prerequisites: "Its investigation and the delivered per-user default are owned by the desktop technical workstream." becomes "It is decided in `2026-10-04-canonical-environment-adr`." Its naming table adds the per-channel root rule above.
- `2026-10-03-application-packaging-adr` (proposed), Constraints: "One native-resolved user root, `U = <user-local-data>/cadrumo`, contains all CADRUMO-controlled mutable data. Windows resolves Local AppData through the platform API." becomes "One per-user, per-channel root `U`, declared by the core storage owner and resolved per `2026-10-04-canonical-environment-adr`, contains all CADRUMO-controlled mutable data." The User data tree and the sentence "The secure-state anchor is `U/data/`; all writable overrides and managed third-party paths must remain under U." are replaced by "The layout under `U` is the existing taxonomy; no member moves."
- `2026-08-03-canonical-storage-management-adr` R5, clarification: after "calls `Path.home()`, `expanduser`, or a platform-directory lookup to *derive* a location rather than to normalise a path it already holds;" add "The installed default of the root anchor in `storage_environment.py` is the one sanctioned platform-directory lookup; it is the anchor, not a member."
- `native/CONTRACT.md:67-69`, `:77`, `:141-143`, `:147-148`: replace "delivery default pending", "deferred" and "no LocalAppData policy is introduced" with the per-OS, per-channel default and the product allowlist; owned by the desktop-shell S11 and application-core S07 executors.

## Rationale

The knockout is ownership. Python already owns the typed taxonomy, the settings fields and the only generator; every other option either adds a second authority (a Rust resolver that Python does not define) or makes a binary that must run before Python depend on Python. Specifying the algorithm once and proving both implementations against generated vectors is the smallest change that makes drift a build failure instead of a review finding.

The per-user OS directory restores what `2026-07-03-claude-ecosystem-packaging-adr` and `2026-07-13-data-output-standardization-adr` already accepted and the interpreter foundation deferred to the storage owner. It keeps one root, so the rejected multi-root split stays rejected. Per-channel roots follow from the storage-identity keying of the runtime: one root per channel is the only arrangement in which two installed families neither share a store nor fight over a runtime, and the identity projection already carries the channel.

Pin-and-inherit is what S02 proved and what the manager needs: a single resolution site means the endpoint, the boot record and the cutover see one root.

## Consequences

**Benefits.** Every binary resolves the same root from any directory and any version. Installed data leaves the launch directory and the read-only package. The runtime manager prerequisite is met. Drift between Python, Rust, CMake and the frontend build fails CI.

**Accepted costs.** A second resolver in Rust remains, bounded by vectors. Installed builds that previously wrote under a launch directory start with an empty root; the old tree is neither read nor moved, and the operator may point `CADRUMO_LOCAL_STORAGE_ROOT` at it. The desktop webview profile moves to the `webview` member. Development tooling loses the installed allowlist and gains its own accessor. Linux and macOS resolvers in `native/platform` block the manager on those platforms until S04 and S05 of the application-core plan land.

**Reconsider if:** an OS base directory cannot be determined reliably on a supported platform; enterprise deployment needs a machine-wide or redirected root; channel coexistence is dropped from the product; or the pip and uvx distribution gains a preview channel.

Acceptance establishes the contract and the default; it does not claim any consumer implements it yet.
