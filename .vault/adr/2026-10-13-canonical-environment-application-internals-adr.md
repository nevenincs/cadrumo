---
tags:
  - '#adr'
  - '#canonical-environment'
date: '2026-10-13'
modified: '2026-10-14'
body_schema: 'body-v2'
body_hash: 'sha256:7eefe689b5161ec914dd108454cb3fedaa2b70572e6007cb6da836ce0444fec6'
related:
  - "[[2026-10-04-canonical-environment-adr]]"
  - "[[2026-10-03-application-packaging-interpreter-foundation-adr]]"
  - "[[2026-10-03-application-packaging-adr]]"
  - "[[2026-10-04-application-distribution-adr]]"
  - "[[2026-10-04-runtime-manager-architecture-adr]]"
  - "[[2026-10-04-runtime-manager-architecture-supervisor-contract-adr]]"
  - "[[2026-10-13-native-agent-adr]]"
  - "[[2026-10-13-provider-settings-adr]]"
  - "[[2026-10-12-desktop-agent-host-adr]]"
  - "[[2026-10-13-desktop-agent-host-live-lane-adr]]"
  - "[[2026-10-08-canonical-environment-darwin-transport-adr]]"
  - '[[2026-10-04-canonical-environment-reference]]'
  - '[[2026-10-13-provider-settings-reference]]'
  - '[[2026-10-12-desktop-agent-host-reference]]'
  - '[[2026-10-13-package-verification-adr]]'
  - '[[2026-08-03-canonical-storage-management-adr]]'
---
# `canonical-environment` adr: `One packaged internals declaration from which every interpreter host defines its process environment` | (**status:** `accepted`)

## Problem Statement

The user directed on 2026-10-13: "the python interpreter should be customized to set and define the env variables based on a proper config. There should be a single config file that defines the actual application default internals." The user then ruled on ownership the same day:

- "Do not conflate an application with the elements that it is made up of. cadrumo is a cli and has NO responsibility for managing application packaging. A toml file in the cmake project setup is a much better choice."
- "the aeat-cli is part of the cadrumo application package but it is not responsible for application packaging layout and environment variables. Those are completely different domains. My principle is that the application package, what we're working on, stays above any lower level interpretation."

Today the direction is inverted. The packaging generator derives the package's environment contract from the CLI's Python declarations (`dev/packaging/native/generate.py:11-27`, `:127-150`, `:296-298`, `:379-381`). It reads:

- `product_env_var_names()` (`src/cadrumo/core/storage_environment.py:620`);
- `PROCESS_ENVIRONMENT` (`storage_environment.py:249-258`);
- the storage taxonomy's override fields;
- `Settings` field names, which become `RESERVED_ENV`.

The interpreter host then only filters. Both C hosts call `cadrumo_platform_prepare` on every launch except the supervised KDF child (`native/interpreter/windows/host.c:129`, `:136`; `native/interpreter/posix/host.c:90`, `:108`). It removes every `CADRUMO_*` name outside the product allowlist, the package allowlist (`native/package-layout.json:38-41`) and the host-inherited pins. It then pins the root, the temporary variables and the authority root, and replaces `PATH` (`native/platform/src/lib.rs:138-140`, `:189-210`; `native/platform/src/storage.rs:588-604`).

The consequence is a live defect at two launches.

- **The gateway.** The runtime starts the bundled agent as `sys.executable -m cadrumo_agent serve` (`src/cadrumo/adapters/local_runtime/agent_programs.py:101`). In a package, `sys.executable` is the package's `python.exe` (`native/interpreter/windows/host.c:61-75`, `native/interpreter/python.c:67-70`). The environment the runtime composes (`src/cadrumo/application/agent_host/launch_environment.py:86-123`) carries `CADRUMO_AGENT_HOSTED_ROOT`, `CADRUMO_AGENT_PORT`, `CADRUMO_AGENT_WORKER_PORT` and `CADRUMO_AGENT_HOSTED_RELAY_EXECUTABLE`, and the host strips all four.
- **The worker.** The gateway spawns its worker with the same interpreter, as `sys.executable -m cadrumo_agent.worker` (cadrumo-agent: `utils/runtime_exec.py:72-88`, `control/worker_management.py:277`). It configures the worker only through a copy of its own environment plus the agent's settings (`control/worker_management.py:257-270`). The host strips those too: the hosted root, the ports, the gateway URL and lifetime id, and, in a non-hosted run, the worker IPC token (`:268`; a hosted worker takes its token on standard input, `:123-131`). So a hosted start the host admitted would still break when the worker spawns.

`prepare` also overwrites the agent's filtered `PATH` with the package root, `bin` and `System32` (`native/platform/src/lib.rs:163-186`). That puts `python.exe`, `aeat`, `cmd` and `powershell` back on the path `launch_environment.py:1-13` removes.

`2026-10-13-package-verification-adr` (accepted) makes the first hosted tool-access proof run on the package's binaries. The staged interpreter runs the bundled agent with `CADRUMO_AGENT_DEVELOPMENT_TOOL_SERVER` set, and every later agent start goes through the runtime's hosted door. Both depend on resolving this defect. That record builds no workaround and defers the choice to this one.

## Considerations

- The application package is the CMake project with its authored inputs and its generator. It already owns:
  - the layout and package overrides: `native/package-layout.json`;
  - the toolchain: `native/toolchain.json`;
  - the platform mappings: `native/platforms/*.json`;
  - the contract step: `native/cmake/Contract.cmake:10-13`.

  Every native consumer reads the generated contract: the platform crate (`native/platform/src/lib.rs:11`), the manager (`native/manager/src/contract.rs:8`) and the desktop (`native/desktop/src-tauri/src/environment.rs:147`).
- Package facts the CLI currently declares, and which the generator reads from it:
  - host clearing classes and the authority pin (`PROCESS_ENVIRONMENT`);
  - the launch-boundary allowlist (`product_env_var_names()`, `Settings.storage_env_var_names()` at `src/cadrumo/core/config.py:991-1000`);
  - the reserved set (`Settings` field names);
  - the storage-root variable, installed default rule and conformance vectors (`STORAGE_ROOT`, `storage_environment.py:162`);
  - the locations of package components: the desktop webview, the console workspace and the manager records, as taxonomy members (`src/cadrumo/core/storage_taxonomy.py:224-225`, `:291-295`);
  - the desktop defaults, taken from `Settings` field defaults (`generate.py:342-353`).

  Regeneration follows the CLI's sources (`native/cmake/Contract.cmake:24-26`).
- Lower components also interpret package facts at run time:
  - the runtime finds the relay from the package manifest (`agent_programs.py:73-87`; `runtime_package_directory`, `src/cadrumo/adapters/local_runtime/boot_record.py:139`);
  - the runtime assumes its own interpreter runs the agent (`agent_programs.py:101`);
  - the CLI hard-codes child-environment literals (`launch_environment.py:26-29`, `:56-82`; `src/cadrumo/adapters/local_runtime/worker_environment.py:14`; `src/cadrumo/adapters/local_runtime/profile_worker.py:274`);
  - the C host recognises a CLI invocation: the KDF exemption (`host.c:131-136`).
- In a package every non-location `Settings` name is cleared, so values such as `CADRUMO_LOG_LEVEL` or `CADRUMO_OUTPUT_LANGUAGE` are fixed at the CLI's defaults.
- Accepted records place the declaration in the CLI:
  - `2026-10-04-canonical-environment-adr`;
  - `2026-10-03-application-packaging-interpreter-foundation-adr`;
  - `2026-08-03-canonical-storage-management-adr` R1.

  The user's 2026-10-13 rulings invert their ownership premise for package facts. `2026-10-03-application-packaging-adr` (proposed) sketches a user-writable `U/config/application.env`, a separate, unadopted operator-override proposal.
- cadrumo-agent's configuration surface, verified in its source:
  - It reads settings only from the process environment, or from a file that the variable `CADRUMO_AGENT_ENV_FILE` names (`control/settings_base.py:15-30`).
  - Beside a hosted root, naming such a file is refused.
  - `serve` takes no options.
  - Every child-environment write takes its name from `setting_env` (`control/config.py:567-573`).
  - The gateway itself refuses `development_tool_server` beside a hosted root or under the `enforce` proof policy (`control/infra_config.py:978-995`).
- The cadrumo-agent owner (CADRUMO-AGENT-CODE), forwarded with the operator's approval on 2026-10-13, prefers the following and rejects a `serve` flag or a frame field carrying settings, as a second configuration surface that does not reach the worker:
  - the environment stays the agent's one settings carrier;
  - the packaged host admits the `CADRUMO_AGENT_*` names for the gateway's launch and its worker's launch, and nothing else;
  - the host does not re-implement the hosted versus non-hosted policy.
- The agent's hosting contract, `2026-10-11-cadrumo-integration-hosting-contract-adr` in cadrumo-agent's vault (read-only here):
  - Its names: `CADRUMO_AGENT_HOSTED_ROOT`, `CADRUMO_AGENT_PORT`, `CADRUMO_AGENT_WORKER_PORT`, `CADRUMO_AGENT_HOSTED_CLI_EXECUTABLE` and `CADRUMO_AGENT_HOSTED_PYTHON_EXECUTABLE`, "and no other value under the `CADRUMO_AGENT_` prefix".
  - Credentials travel only in a standard-input frame.
  - Cadrumo must "admit those names to the gateway it starts and to nothing else; never define a `CADRUMO_AGENT_` value for its own use".
  - `2026-10-13-package-verification-adr` proposes to the agent owner that the contract name `CADRUMO_AGENT_HOSTED_RELAY_EXECUTABLE`, which the runtime already sends, and retire the two program-path names.
- Other drift:
  - The CMake source selector is `CADRUMO_AGENT_SOURCE_DIR` (`2026-10-13-native-agent-adr`).
  - The development direct start reads `CADRUMO_AGENT_ANTHROPIC_API_KEY` from its own process and puts the key and bearer in the agent's environment (`native/desktop/src-tauri/src/agent/direct.rs:27-29`, `:148-158`). `2026-10-13-package-verification-adr` removes that path.
- Secrets already have a channel: stdin frames and secret descriptors (`2026-10-13-provider-settings-adr` constraint 8, `2026-10-12-desktop-agent-host-adr`). Rule 13 keeps profile selection out of the environment. Rule 00 forbids Git in product code, tests and build definitions.

## Considered options

- **Add the agent names to `package-layout.json` `overrides`.** Rejected. It admits them to every image, which the hosting contract forbids, and does not fix the overwritten `PATH`.
- **Launch the agent through a non-preparing path (the KDF-style exemption).** Rejected. It drops isolation and pinning for the agent's whole tree.
- **Carry agent settings in a `serve` flag, a frame field or a per-launch file.** Rejected by the hosting contract and by the agent owner: it is a second configuration surface, and it does not reach the worker.
- **Select the agent profile on the generic `python.exe` by an environment marker.** Rejected. Any same-account process could set the marker and receive the agent's environment from the generic interpreter.
- **Declaration owned by the CLI, or the generator keeps deriving the contract from CLI declarations.** Rejected by the user's rulings.
- **A user-writable `U/config/application.env`.** Not chosen; it answers operator overrides.
- **Proposed: one TOML file owned by the CMake project under `native/`, authoritative for the environment of every image.** It includes a dedicated agent image whose profile admits the agent's environment for exactly its gateway and worker invocations.

## Constraints

Binding if accepted.

1. **The package is authoritative.** The application package (the CMake project, `native/application-environment.toml` and the `dev/packaging/native` generator) is the single authority for package layout and the environment of every image it builds. Lower components (the `aeat` CLI and the Cadrumo Python application, the runtime, the agent and the interpreter host itself) do not define or interpret those facts; they receive them.
2. **One file.** `native/application-environment.toml` is authored beside `native/package-layout.json` and `native/toolchain.json` and carries a `schema` integer. It declares:
   - the environment names the package uses and their kinds and validation;
   - the storage-root variable, the installed default-root rule per platform and channel, and its conformance vectors;
   - the package-owned overrides now in `package-layout.json` `overrides`;
   - each image's operator-overridable names (constraint 6);
   - the locations of package components and their defaults;
   - one launch profile per image.
3. **Direction reversed.** The generator reads the file and the package's own inputs only. It no longer imports `product_env_var_names()`, `PROCESS_ENVIRONMENT`, `STORAGE_ROOT`, the storage taxonomy as an environment source, or `Settings` field names or defaults. `RESERVED_ENV` and `PACKAGE_ENV_ALLOWLIST` are retired: a host that defines a closed environment needs no list of names to clear. Where the CLI's Python owns these declarations today, they move to the file, and the CLI stops being their source.
4. **Validation and compilation.** The generator validates the file with the standard-library TOML reader against its schema and compiles it into `contract.json`, `contract.rs` and `contract.h`. A violation fails generation. The file is a declared input of the contract step in `native/cmake/Contract.cmake`, and the CLI's sources stop being environment inputs of that step.
5. **Launch profiles.** Each image or child the package builds has one profile. Images include `python`, `cadrumo-runtime`, `aeat`, `cadrumo-tui`, `cadrumo-mcp`, the profile worker, the KDF child, the relay, and the `cadrumo-agent` image's six invocations: gateway, worker and the four store and version invocations of constraint 21. (Amended 2026-10-14 under operator approval; before that this read: "Images include ... the relay, and the `cadrumo-agent` image's two invocations, gateway and worker.") A profile declares:
   - its base: the declared OS names taken from ambient, or nothing;
   - its operator-overridable names;
   - its fixed values and pins;
   - its `PATH` policy;
   - its pass-through names and launch-parameter slots: name, kind, whether required, and the supplying parent.
6. **Meaningful operator overrides (user decision, 2026-10-13).** Each image passes from the caller's real environment exactly the operator settings its profile declares; everything else is defined by the package.
   - **Criterion.** A name is overridable when it is an operator setting with no custody, location, authority or secret effect.
   - **Never overridable.** Location, authority and secret-bearing names, unless an existing accepted record already allows them.
   - **Allowed by existing records:**
     - the root `CADRUMO_LOCAL_STORAGE_ROOT` and the operator-overridable member locations (`2026-10-04-canonical-environment-adr`, `2026-10-12-runtime-manager-architecture-caller-owned-root-adr`);
     - `CADRUMO_EXTERNAL_BIN_DIRS` and `CADRUMO_CLI_REVEAL_IDENTIFIERS` (`2026-10-03-application-packaging-interpreter-foundation-adr`, `native/CONTRACT.md`).

     These keep their current images.
   - **Initial non-location set**, for the operator-facing images `aeat`, `cadrumo-tui`, `cadrumo-mcp` and `python`:
     - `CADRUMO_LOG_LEVEL`, `CADRUMO_LOG_STDERR_LEVEL`, `CADRUMO_LOG_FILE_LEVEL` and `CADRUMO_LOG_ROOT_LEVEL`;
     - `CADRUMO_OUTPUT_LANGUAGE` and `CADRUMO_FALLBACK_LANGUAGES`;
     - `NO_COLOR`, `CADRUMO_FORCE_COLOR` and `CADRUMO_TUI_APPEARANCE`;
     - `CADRUMO_DEADLINE_DUE_SOON_DAYS`, `CADRUMO_INBOX_ALERT_LEAD_DAYS`, `CADRUMO_CERT_WARN_DAYS` and `CADRUMO_CERT_CRITICAL_DAYS`, which are presentation thresholds only.
   - **Runtime images.** The runtime and its workers stay strict, and the KDF child keeps its parent-defined environment (constraint 18), as `2026-10-04-runtime-manager-architecture-adr` binds ("no `CADRUMO_*` overrides"). The runtime's own presentation names reach it only as package fixed values.
   - **Kept out**, each needing its own ruling to enter:
     - secret fields (`SecretStr`: provider keys, Cl@ve credentials, passphrases, proxy password);
     - authority and endpoint names (`CADRUMO_AUTHORITY_ROOT`, the `AEAT_*` URLs and paths, `SITE_HEALTH_PROBE_URL`, the LLM provider, model and endpoint names, `CADRUMO_AUTH_PROVIDER`, `CADRUMO_STORAGE_PROVIDER_KIND`);
     - security and consent switches (`CADRUMO_STRICT_SECURITY`, `CADRUMO_EVIDENCE_CLOUD_UPLOAD_PERMITTED`, `CADRUMO_EVIDENCE_GESTOR_MODE`);
     - session and lock policy (`CADRUMO_BUCKET_DEFAULT_*`, the lock timings);
     - retention and size limits, which govern custody lifecycle;
     - calculation semantics (`FINANCIAL_BASE_CURRENCY`, `CADRUMO_DRAFT_FAIL_ON_WARNING`);
     - network routing (`CADRUMO_PROXY_*`);
     - development and test names (`CADRUMO_DEV_*`, `CADRUMO_LIVE_TESTS_*`, `CADRUMO_LLM_CONTENTION_CHECK_OVERRIDE`, `CADRUMO_PROFILE_KDF_MEASURE_CALIBRATION`);
     - the severed `CADRUMO_ACTIVE_PROFILE` (rule 13).
   - **Remote-interaction set (user decision, 2026-10-13: "yes include browser and network settings as overrides"),** for the same images. These are timing and display settings only:
     - authentication: `CADRUMO_AUTH_TIMEOUT_MS`, `CADRUMO_CLAVE_MOVIL_TIMEOUT_MS`, `CADRUMO_CLAVE_PERMANENTE_TIMEOUT_MS`;
     - browser: `CADRUMO_BROWSER_HEADLESS`, `CADRUMO_BROWSER_VIEWPORT_WIDTH`, `CADRUMO_BROWSER_VIEWPORT_HEIGHT`, `CADRUMO_BROWSER_NAVIGATION_TIMEOUT_MS`, `CADRUMO_BROWSER_FORM_INTERACTION_TIMEOUT_MS`, `CADRUMO_BROWSER_SELECTOR_PROBE_TIMEOUT_MS`, `CADRUMO_BROWSER_VER_CLICK_TIMEOUT_MS`, `CADRUMO_BROWSER_BUSCAR_SETTLE_MS`, `CADRUMO_BROWSER_CLOSE_TIMEOUT_MS`;
     - live reads: `CADRUMO_LIVE_FILED_REGISTER_WALK_TIMEOUT_MS`, `CADRUMO_LIVE_IVA_SURFACE_TIMEOUT_MS`, `CADRUMO_LIVE_IVA_DECLARATION_CAPTURE_TIMEOUT_MS`, `CADRUMO_LIVE_IVA_CANCELLATION_DRAIN_MS`;
     - network pacing: `CADRUMO_RATE_LIMIT_DELAY_SECONDS`, `SITE_HEALTH_RATE_LIMIT_RETRY_AFTER_DEFAULT`, `CADRUMO_FX_RATE_LOOKUP_TIMEOUT_S`, `CADRUMO_MANUALS_HTTP_TIMEOUT_S`, `CADRUMO_CALC_SHEETS_RECALC_DELAY_S`;
     - model requests: `CADRUMO_LLM_DEFAULT_TIMEOUT_S`, `CADRUMO_LLM_VISION_READ_TIMEOUT_S`.
   - **Excluded although near this set:**
     - `CADRUMO_BROWSER_LOCALE` and `CADRUMO_BROWSER_TIMEZONE`, which change how captured pages are rendered, parsed and dated;
     - `CADRUMO_CLAVE_PREFER_NON_QR`, an authentication-flow choice;
     - `CADRUMO_AUTH_CERTIFICATE_LOCK_TTL_S` and `CADRUMO_AUTH_CLAVE_MOVIL_LOCK_BUFFER_S`, which are lock policy;
     - `CADRUMO_FILING_HISTORY_CACHE_TTL_S`, which governs evidence freshness;
     - `CADRUMO_LLM_MAX_RETRIES`, since a retry re-sends content;
     - every endpoint, proxy and credential name.
   - **Reach.** These names reach work done in the operator-facing image's own process. Work the runtime performs keeps the runtime's strict rule above and uses package fixed values.
   - Each overridable name keeps the kind and validation the file declares, and the host passes it unchanged; the CLI validates the value as it does today.
7. **Fixed values versus launch parameters.** Fixed values are package facts: declared in the file, set by the host, and replaceable by no parent or operator. Launch parameters are values known only at launch time, supplied by the launching parent within slots the package declares by name, kind and validation, never by value.
8. **The host defines; it does not interpret.** The C host and `native/platform` apply the profile compiled into the image:
   - they start from the declared base;
   - they pass the declared operator names and pass-through names;
   - they resolve and pin the root by the package's rule;
   - they set fixed values;
   - they admit declared parameters after validating their kind;
   - they apply the `PATH` policy.

   An undeclared name does not survive. A missing or malformed required parameter is refused before Python starts, with a closed code. The host does not judge how a lower component uses an admitted value. Image identity is compiled into each image; no environment value or file selects a profile at run time.
9. **The CLI consumes.** The CLI and runtime read the values they are given the way any CLI reads its environment. They keep their own `Settings` and defaults for runs outside a package (checkout, pip, uvx), where no host exists and the file is not read. In a packaged image a pinned value is never re-resolved. The CLI reads no packaging file, manifest or contract, and holds no package policy or package-component location. A package fact the runtime needs, such as the relay or agent-image path, reaches it as a fixed value in the runtime image's profile.
10. **Drift control without making the CLI the authority.** A package-side conformance check, owned by `dev/packaging/native` and run against the assembled package, compares two things: the names and kinds the package sets, passes or lets operators override, and the names the installed CLI and the bundled agent read (their published environment references and the agent's `setting_env` declarations). It fails on any disagreement. The package's declaration is the reference.
11. **Agent: a compiled image, the environment as its one carrier (user decision, 2026-10-13).**
    - **One agent image.** The package declares and compiles one dedicated `cadrumo-agent` entrypoint image from the same C host, with its own launch profiles, and uses it for both the agent gateway and the agent worker. That is how the host tells an agent launch from any other Python child. The generic `python` image and every other profile clear the `CADRUMO_AGENT_` prefix.
    - **Layout.** The package layout admits this image although it is not one of Cadrumo's `[project.scripts]`. The restriction at `dev/packaging/native/layout.py:66-69` widens to entrypoint images that the package declares for a bundled distribution.
    - **Six invocations.** The image keeps itself as `sys.executable` and admits exactly six invocations, each with its compiled profile: the gateway (the agent's declared CLI module with `serve`), the worker (`-m cadrumo_agent.worker`), and the agent's declared CLI module with `stores-state`, with `setup`, with `migrate` and its two optional revision assertions (`--expect-from REV`, `--expect-head REV`), and with `version --json`. The four store and version invocations run in the gateway's environment, take no port and no credential, and start no gateway. Any other module, verb, `-c` or script is refused before Python starts. (Amended 2026-10-14 under operator approval; before that this read: "**Two invocations.** The image keeps itself as `sys.executable` and admits exactly two invocations, each with its compiled profile: the gateway (the agent's declared CLI module with `serve`) and the worker (`-m cadrumo_agent.worker`). Any other module, `-c` or script is refused before Python starts.")
    - **Gateway.** The runtime supplies values only within the gateway's declared slots (hosted root, ports, relay path) and never reads them from its own environment (hosting contract).
    - **Worker.** The gateway passes its settings to its worker as it does today, and the host admits them for the worker profile.
    - **Hosted policy stays with the agent.** The host does not decide hosted versus non-hosted: it admits the declared names, including `CADRUMO_AGENT_DEVELOPMENT_TOOL_SERVER` and `CADRUMO_AGENT_PROVIDER_PROOF_POLICY`, and the gateway's own refusals apply (`control/infra_config.py:978-995`). `CADRUMO_AGENT_ENV_FILE` is never admitted.
    - **Tagging and parity.** The agent names are tagged with the agent's hosting-contract version. The package-side check also verifies that the runtime's composer writes exactly the gateway's slots.
12. **No secrets.** The file declares no secret value and no credential name. Credentials, bearers, passwords and keys travel only on the stdin frames and secret channels of `2026-10-13-provider-settings-adr`, `2026-10-12-desktop-agent-host-adr` and the hosting contract. The hosted worker's IPC token stays on its standard input. The non-hosted worker token set at `control/worker_management.py:268` is an agent-internal secret in an environment. The package admits it only for the agent worker profile, and only until the agent moves it to standard input (agent-owner item A3).
13. **Precedence in a packaged image**, from lowest to highest:
    - the component's own default;
    - an operator override, only for names the profile declares overridable;
    - host resolution and pins;
    - package fixed values;
    - validated launch parameters, only in declared slots.

    Development-only names are never declared for an installed profile.
14. **Tooling.** Generation, validation and checks never invoke Git or read checkout history (rule 00). The file names no development tool, compiler or SDK location.
15. **Accepted rulings this inverts.** Exact amendments are proposed under Implementation; accepted bodies stay intact until approved.
16. **One per-user data folder inside and outside the package (user decision, 2026-10-13).** `aeat` run outside the package (pip, uvx) uses the same per-user data folder as the packaged application.
    - `aeat` keeps its own built-in default.
    - The package passes the same location explicitly, as a declared fixed value of each image's root pin.
    - A package-side test asserts that the CLI's built-in default and the package's declared value agree for each platform and channel. The package never reads the location from the CLI, and the CLI never reads the package.
17. **`PATH` is package-declared (user decision, 2026-10-13).** The package declares each image's `PATH`, composed from the layout's binary directories rather than a hand-written list. It includes every binary directory the package ships (the runtime, the manager, `python`, `aeat`, the `cadrumo-agent` image, `cadrumo-mcp`, the desktop and the other declared images) and the Python distribution's own binary and scripts directories inside the package. The host sets it; no parent supplies it. The agent image follows the same rule (user decision, 2026-10-13: "agent needs those tools, they're allowed, mcp, cli aeat"): its gateway and worker `PATH` include every packaged binary, `aeat`, `cadrumo-mcp`, `python` and the rest. This supersedes the confinement in `src/cadrumo/application/agent_host/launch_environment.py:8-13` and its search-path stripping (`:47-53`, `:122-146`). It aligns with the agent's accepted `2026-10-10-cadrumo-integration-terminal-access-adr`: "In a hosted run the assistant can run two programs, Cadrumo's command line and Cadrumo's bundled Python". Shells such as `cmd` and `powershell` are not packaged binaries: the package rule neither adds nor strips them, and whatever ambient system directory the profile's declared base carries is unchanged by it.
18. **Invocation admission, one mechanism.** Each image's profile table in the file may declare invocation-selected profiles. An invocation is the exact fixed argument pattern that selects a profile. The host matches the argument vector against the compiled table before Python starts. An image with an invocation table refuses any invocation it does not declare.
    - **Agent image.** It declares six invocations: gateway, worker, `stores-state`, `setup`, `migrate` and `version --json` (constraints 11 and 21). `migrate` is the one invocation with optional typed argument positions, its two revision assertions. (Amended 2026-10-14 under operator approval; before that this read: "**Agent image.** It declares two invocations, gateway and worker (constraint 11).")
    - **Generic `python` image.** It declares its default profile and one `kdf-child` invocation: the exact fixed supervised KDF invocation the host now recognises in code (`native/interpreter/windows/host.c:131-136`, `supervised_kdf_invocation`).
    - **The `kdf-child` profile** declares the policy the code applies today: the parent-defined neutral environment passes unchanged, with no projection, pin or override, and isolated paths and package verification still apply. The hand-written `supervised_kdf_invocation` is replaced by the generated table, so the host no longer recognises a CLI invocation in its own code.
19. **Refusals and exit status.** A launch-profile violation is a native-host startup refusal under the existing exit-code convention.
    - `RESERVED_RUNTIME_EXIT_CODES` reserves 120-124 for "the native interpreter host's startup refusals" (`src/cadrumo/application/runtime/contracts.py:108-120`), and `dev/packaging/native/runtime_exit_reasons.py:16-37` projects that table into the contract. Every code in that range is in use (`native/interpreter/python.c:38`, `:98`, `:103`; `native/interpreter/windows/host.c:69`, `:95`).
    - The range widens to 120-125, and 125 means `launch_profile_refused`.
    - Before Python starts, the host writes one machine-readable line as its last standard-error line: `{"native_refusal": "<code>", "subject": "<variable name or invocation>"}`. The code is one of `launch_value_missing`, `launch_value_malformed` or `invocation_undeclared`. The value itself is never written.
    - As a package fact, the native-host range is declared in the file. The runtime's reserved table must agree, by the package-side check of constraint 10; the generator stops importing it.
    - A supervisor reads 125 as a launch failure, never as a runtime exit reason (runtime exit reasons stay in 64-73).
    - When the agent gateway or worker exits 125 before its ready line, the runtime ends the launch with the existing closed launcher code `agent_service_failed` (`src/cadrumo/application/agent_host/launcher_protocol.py:40-49`, through `launcher_refusal_for` at `:65`). It records the native code and subject in its redacted diagnostics. The desktop's closed refusal set does not change.
20. **No Cadrumo-defined `CADRUMO_AGENT_` value.**
    - The CMake selector `CADRUMO_AGENT_SOURCE_DIR` (`native/cmake/Agent.cmake:2-9`) becomes the cache-only CMake variable `CADRUMO_PACKAGE_AGENT_SOURCE_DIR`, set with `-D` or a CMake user preset. Its environment fallback is removed, so no process environment carries it, and `2026-10-13-native-agent-adr`'s selector is renamed accordingly.
    - The development direct start that read `CADRUMO_AGENT_ANTHROPIC_API_KEY` is removed by `2026-10-13-package-verification-adr`.
    - A structural gate refuses any `CADRUMO_AGENT_` spelling in Cadrumo outside the package file, the runtime's launch composer and the generated contract.

21. **The runtime owns the agent's store lifecycle (added 2026-10-14 under operator approval).** The agent's own accepted hosting-contract and shipping-and-versioning records give the host the lifecycle of the agent's two stores. A hosted `serve` only checks them, and refuses `hosted_stores_mismatch` when they do not match its build, a fresh root included. Before every `serve` of a hosted root the runtime therefore runs this sequence through the same launch composer, image and environment as `serve`:
    - `version --json`. An `api_version` other than `v1` is refused as an incompatible agent.
    - `stores-state`, which is read-only. Its `state` selects the step. `absent` runs `setup`. `older` copies the stores aside and then runs `migrate --expect-from <primary found> --expect-head <primary expected>`. `current` runs nothing. `newer` is a downgrade: it is refused and nothing starts. An unreadable primary store reports `newer` and is refused the same way.
    - `stores-state` again. Anything other than `current` is refused. Only then does `serve` start.
    - **Output.** Each invocation writes one JSON object on standard output. The runtime parses the whole of it strictly: unknown keys are refused, and a number where text is expected is refused. Revisions are opaque text, never numbers. Standard error is diagnostic only and is not parsed. The agent's `detail`, `error_class` and `app_home` values never reach a log.
    - **Bounds.** Each invocation has a hard time bound. On expiry the runtime ends the invocation's whole process tree. A timed-out `setup` or `migrate` is an unknown outcome: the start is refused, and the runtime does not retry within it. A later start re-reads `stores-state`. `setup` may run again on an `absent` root, because the agent declares it idempotent.
    - **Quiescence.** `migrate` runs only while the runtime holds the profile's one agent reservation and no tree of that profile is starting, running or being reaped, including a tree whose containment was not confirmed. The agent's own `migrate` also refuses live or locked stores.
    - **Copy aside.** Before `migrate`, the runtime copies the agent's store directory to `stores-aside` directly under the same hosted root. The store directory is `home/state` under the hosted root: both stores with their write-ahead-log files. The runtime writes the copy first to `stores-aside.partial` and renames it once complete, so a partial copy is never taken for a complete one. A `stores-aside.partial` left by an interrupted start is removed, because no `migrate` ran after it.
      - *Placement.* The copy stays inside the profile's opaque agent root under the storage root's `agent` directory. It therefore has the same exact-profile scope and file permissions as the stores it copies, and it leaves the profile's tree by no path. It lies outside the agent's state home `home`, outside every workspace under `home/workspaces`, and outside `tmp` and `scratch`, which the agent empties at start. The agent's layout names no `stores-aside` entry; the name is reserved to the host.
      - *Custody (rule 05).* The copy adds no custody class and no destination. It holds the same bytes as the stores the agent already keeps at that root, and it is not logged, sent or exported. Whether the agent's stores belong in encrypted custody is outside this amendment.
      - *Lifetime.* At most one copy exists per hosted root. The runtime removes it as soon as `stores-state` reports `current`, either at the re-check after `migrate` or at a later start. A failed, timed-out or unconfirmed `migrate` keeps the copy as the agent's rollback snapshot. While a kept copy exists and the stores are not `current`, every start of that root is refused, so no second `migrate` runs over an unsettled root. Restoring from the copy is an operator recovery; the runtime does not restore automatically. In every case the copy lives no longer than the profile's agent root.
    - **Refusals.** A `newer` state and an `api_version` other than `v1` map to the launcher code `agent_service_incompatible`. These map to `agent_service_failed`: a failed `setup` or `migrate`, a timeout, malformed output, a re-check that is not `current`, and a kept copy over unsettled stores. The runtime's diagnostics record a closed step and outcome, never a path or the agent's text. The desktop's closed refusal set does not change. A `migrate` lengthens a start, and the frontend's existing start bound still applies.

## Implementation

We will add `native/application-environment.toml` to the CMake project as the authority for every image's environment. We will compile it in `dev/packaging/native` into the native contract without importing CLI declarations. The interpreter hosts and `native/platform` will define each image's environment from its compiled launch profile. The CLI, runtime and agent will consume what they are given. Items marked *hypothesis* may change within the Constraints.

- **Native.** Each profile becomes constants in `contract.rs` and `contract.h`; no TOML parser enters the C host or the platform crate (*hypothesis*). `native/platform` gains one `define_environment(profile, ambient)` function that replaces `cleared`, `pinned` and the `prepare` filter. The C hosts use it through the C ABI, and the manager and desktop through the crate. `PACKAGE_ENV_ALLOWLIST`, `RESERVED_ENV` and `layout["overrides"]` are removed with their consumers (rule 00).
- **Storage root.** The file carries the root variable, the installed per-platform and per-channel default rule, and the vectors the Rust resolver replays. A packaged image's root is resolved by the host and pinned. The CLI keeps its own built-in default for runs outside a package. The two agree by constraint 16's package-side test, not by either reading the other.
- **`PATH`.** The generator composes each image's `PATH` from the layout's declared binary directories and the packaged Python distribution's binary and scripts directories (constraint 17), and the host sets it, replacing `executable_search_path` (`native/platform/src/lib.rs:163-186`). Whether `CADRUMO_EXTERNAL_BIN_DIRS` still extends it stays as the existing package override allows.
- **Agent image** (decided by the user, 2026-10-13; constraint 11): one dedicated compiled image, `bin/cadrumo-agent`, built from the same C host with the agent's profiles compiled in, and declared in the package layout.
  - **How the worker lands on it.** The gateway spawns its worker with `module_command("cadrumo_agent.worker")`. That function returns `[sys.executable, "-m", module]`, or the binary's own `run-module` verb when `sys.frozen` is set (cadrumo-agent: `utils/runtime_exec.py:54-56`, `:72-88`; `control/worker_management.py:277`). Unlike the Cadrumo entrypoint hosts, which hand `sys.executable` back to `python.exe` (`host.c:61-75`), the agent image keeps itself as `sys.executable` and leaves `sys.frozen` unset. The worker therefore re-executes the agent image, with no agent change and no package-declared worker path.
  - **Agent-owner confirmation:** item A4.
  - **Exactly six invocations.** The image admits only the gateway invocation (the agent's declared CLI module with `serve`), the worker invocation (`-m cadrumo_agent.worker`), and the agent's declared CLI module with `stores-state`, `setup`, `migrate` (with its two optional revision assertions) or `version --json` (constraint 21). Each selects its own compiled profile, and every other module, verb, `-c` or script argument is refused before Python starts. The image cannot serve as a general interpreter carrying the agent's environment. (Amended 2026-10-14 under operator approval; before that this read: "**Exactly two invocations.** The image admits only the gateway invocation (the agent's declared CLI module with `serve`) and the worker invocation (`-m cadrumo_agent.worker`). Each selects its own compiled profile, and every other module, `-c` or script argument is refused before Python starts. The image cannot serve as a general interpreter carrying the agent's environment.")
  - **Why the host can tell.** It knows a launch is the agent's because the image is the agent's, and it knows gateway from worker by the declared invocation.
  - **Runtime start.** The runtime starts this image, at the path its own profile fixes, instead of `python.exe -m cadrumo_agent serve`. Before `serve` it runs the store sequence of constraint 21 on the same image, in the same environment. (Amended 2026-10-14 under operator approval; before that this bullet ended at the previous sentence.)
  - **Gateway checks.** The host checks the slot kinds: the hosted root is an existing absolute directory; each port is an integer in 0..65535; the relay names an existing file that is not a batch file. The gateway's and worker's `PATH` follow constraint 17.
- **Runtime launch values.** `launch_environment.py` keeps composing the per-launch values (hosted root, ports, relay path) and stops reading the package manifest. Its `FORBIDDEN_PROGRAM_STEMS`, `agent_search_path` and the confinement in its module docstring are retired with their consumers and tests, because the package now defines the agent's `PATH` (constraint 17).
- **Moves out of the CLI:**
  - `PROCESS_ENVIRONMENT`'s host classes and the authority pin;
  - `product_env_var_names()` and `Settings.storage_env_var_names()` as an allowlist;
  - the taxonomy's role as an environment source;
  - the desktop, console and manager taxonomy members;
  - the package-inventory reads in `agent_programs.py` and `boot_record.py`;
  - the generator's `desktop_defaults`.
- **Verification.**
  - Generator tests: schema validation, refusal of malformed files, and parity from file to `contract.json` to `contract.rs`.
  - A static test that the generator imports no `cadrumo` module for the environment contract.
  - Per-profile vectors run in `native/platform`, including the agent image's refusal of undeclared invocations.
  - The package-side conformance check of constraint 9.
  - A CTest launch probe on the assembled package. It asserts:
    - through the runtime's real composer and the real host, the bundled gateway and its worker both receive their declared environment;
    - `cadrumo-agent stores-state` answers for a synthetic hosted root, and the image's own `setup` brings that root to `current`;
    - a hosted `serve` reaches `agent_ready`, or a refusal that is not a missing-root, missing-program or worker-configuration refusal (agent-owner item A2);
    - the generic `python` image clears every `CADRUMO_AGENT_` name;
    - each image's `PATH`, the agent's included, equals the composition constraint 17 declares;
    - the CLI's built-in default root agrees with the package's declared value (constraint 16).
  - The same image runs the one-time proof of `2026-10-13-package-verification-adr` constraint 3, with `CADRUMO_AGENT_DEVELOPMENT_TOOL_SERVER` admitted as a declared gateway name and no hosted root.

**Proposed amendments to accepted records** (apply only on approval):

- `2026-10-04-canonical-environment-adr`:
  - **One declaration.** "The storage taxonomy (`STORAGE_TAXONOMY`) plus one root declaration in `src/cadrumo/core/storage_environment.py` is the canonical definition of every location, variable name, default rule, override rule and reserved status." becomes "`native/application-environment.toml` is the canonical definition of every packaged image's environment: the variable names the package sets or passes, the root's default and override rules, and the package's own locations. The storage taxonomy remains the CLI's declaration of the locations it creates under a root it is given."
  - **One generated projection.** Add after its first sentence: "`generate.py` reads it from `native/application-environment.toml` and imports no CLI declaration for it."
  - **Two resolver implementations, one oracle.** "Python (`storage_environment.py`) and the Rust platform crate implement the same algorithm. The generator emits conformance vectors" becomes "The package's root rule and vectors are declared in `native/application-environment.toml` and implemented by the Rust platform crate for packaged images. The CLI never re-resolves a pinned root; its own resolver serves only runs outside a package."
  - **Development tooling stays out of the product.** "The product allowlist is the root variable plus the settings fields of operator-overridable taxonomy members." becomes "Each image's passed names are declared in its launch profile in `native/application-environment.toml`."
  - **Scope exclusion.** "No configuration file is introduced." becomes "No operator configuration file is introduced. The package-owned `native/application-environment.toml` (`2026-10-13-canonical-environment-application-internals-adr`) declares image environments."
  - **Process environment.** "Nothing else." becomes "Nothing else, except the package fixed values, pass-through names and validated launch parameters the image's launch profile declares."
- `2026-10-03-application-packaging-interpreter-foundation-adr`:
  - Constraints: "Native bootstrap supplies the packaged Settings environment before Python starts" becomes "Native bootstrap defines each packaged image's process environment from its launch profile in `native/application-environment.toml` before Python starts".
  - Implementation: "The generator projects Settings names, identity and storage declarations" becomes "The generator projects the package environment declaration and identity".
  - CMake amendment: "Native generation projects `Settings.storage_env_var_names()` and storage taxonomy values." becomes "Native generation projects `native/application-environment.toml`; it does not derive the environment contract from the CLI."
- `2026-08-03-canonical-storage-management-adr` R1: after "One `STORAGE_TAXONOMY` mapping keyed by the enum is the single declaration." add: "It declares the CLI's own locations. It is not the source of any package environment contract; `native/application-environment.toml` declares which variables a packaged image passes, and the package's own component locations are declared there, not as taxonomy members."
- `2026-10-13-package-verification-adr`, Consequences, the bullet beginning "The packaged interpreter host strips every `CADRUMO_AGENT_*` variable": add "`2026-10-13-canonical-environment-application-internals-adr` adopts the agent owner's preference through the agent gateway and worker launch profiles of a dedicated agent image."
- In cadrumo-agent's vault, the hosting contract's names (the relay variable and the retired program paths) need the agent owner's amendment and a coordinated release; these need CADRUMO-AGENT-CODE (agent-owner item A1).
- `2026-10-13-native-agent-adr`, Considered options: "CMake accepts a configurable local project folder through `CADRUMO_AGENT_SOURCE_DIR`" becomes "CMake accepts a configurable local project folder through the cache-only variable `CADRUMO_PACKAGE_AGENT_SOURCE_DIR`".
- `2026-10-13-package-verification-adr`, Affected records, the bullet beginning "cadrumo-agent records, proposed to their owner": "and records the retirement of the two program-path variables it still names" becomes "and leaves to the agent owner whether the two program-path variables stay, now that the agent may run Cadrumo's command line and Python (`2026-10-13-canonical-environment-application-internals-adr` constraint 17)".
- In cadrumo-agent's vault, needing CADRUMO-AGENT-CODE: `2026-10-10-cadrumo-integration-terminal-access-adr` needs no change, since constraint 17 matches it. The hosting contract's sentence "Required of Cadrumo, for its own records: admit those names to the gateway it starts and to nothing else" gains "; Cadrumo's package admits them for the gateway and its worker, which the gateway configures through the same environment".

## Rationale

The knockout is the user's layering principle: the application package stays above any lower-level interpretation. A package-owned file compiled into each image makes the package the only definer of what each process receives. The CLI, runtime, agent and host receive those facts and do not interpret them. Per-image profiles also meet the hosting contract's "to nothing else" admission and the agent owner's request to keep the environment as the agent's one carrier, reaching both gateway and worker. A shared allowlist or a run-time selector cannot do that. A dedicated agent image that re-executes itself for the worker answers "is this the agent?" by construction rather than by inspecting a forgeable value. It also leaves the hosted policy where it lives, in the agent's own refusals.

## Consequences

- One package file states what each built image receives. The agent's gateway and worker can start from the package, which unblocks the proof run and hosted door of `2026-10-13-package-verification-adr`. `package-layout.json` loses its environment role, and the generator stops depending on CLI declarations.
- Operators keep meaningful overrides (logging, language, colour, appearance, presentation thresholds) in packaged runs. Packaged and unpackaged `aeat` share one data folder.
- Accepted costs:
  - several CLI declarations and their consumers move or narrow;
  - five accepted Cadrumo records need amendment (canonical-environment, interpreter foundation, canonical-storage-management R1, native-agent, package-verification), and two agent records need their owner;
  - a dedicated agent image with an invocation check;
  - a widened layout rule for bundled-distribution images;
  - a coordinated hosting-contract change in another repository;
  - the default root is stated twice, by the CLI and the package, held together by a package-side test;
  - the agent names are spelled on the package and agent sides, held together by the package-side check.
- Not claimed: environment definition is not a process sandbox (`2026-10-03-application-packaging-interpreter-foundation-adr`). Acceptance would not show any consumer implements it.
- Reconsider if a native consumer must read the file at run time, if the agent stops configuring its worker through the environment or starts running frozen, or if an operator configuration file is adopted.

Accepted 2026-10-13 by the operator in conversation ("accept. lgtm, proceed"). Amended 2026-10-14 under operator approval, on the agent owner's basis that the host owns the agent's store lifecycle: constraints 5, 11 and 18 and the Implementation's agent-image bullets admit six agent invocations instead of two, and constraint 21 is added. Acceptance records the decision; it is not evidence that any of it is built. The amendments proposed under Implementation were applied to the accepted Cadrumo records the same day; the cadrumo-agent amendments go to their owner.

### Cadrumo-side questions

None remain open. The user's 2026-10-13 rulings and constraints 6, 16, 17, 18, 19 and 20 settle them.

### Requires agent owner (CADRUMO-AGENT-CODE)

- **A1, hosting-contract names and version.** Decide whether `CADRUMO_AGENT_HOSTED_CLI_EXECUTABLE` and `CADRUMO_AGENT_HOSTED_PYTHON_EXECUTABLE` stay, now that Cadrumo's package puts its command line and Python on the agent's `PATH` and your terminal-access record permits both. Decide whether the contract adds `CADRUMO_AGENT_HOSTED_RELAY_EXECUTABLE`, which Cadrumo's runtime already sends. State the hosting-contract version that carries the result. Also amend the hosting contract's "admit those names to the gateway it starts and to nothing else" so that it covers the gateway's worker, which the gateway configures through the same environment.
- **A2, ready with an empty frame.** Confirm whether a hosted `serve` given an empty or synthetic credential frame reaches `agent_ready`, or name the refusal it writes. Cadrumo's CTest launch probe needs a credential-free ready path, or a stated refusal to assert instead.
- **A3, non-hosted worker token.** Move the worker IPC token of a non-hosted run (`control/worker_management.py:268`) from the worker's environment to its standard input, as a hosted worker already receives it (`:123-131`). Until then Cadrumo's package admits it to the agent worker profile only.
- **A4, worker re-exec.** Confirm that `module_command` (`utils/runtime_exec.py:72-88`) keeps resolving to `sys.executable` for a non-frozen process, and that `cadrumo_agent.worker` stays the only worker module the gateway starts. Cadrumo's agent image keeps itself as `sys.executable` and admits exactly the gateway and `-m cadrumo_agent.worker` invocations.
