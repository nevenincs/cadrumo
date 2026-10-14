---
tags:
  - '#adr'
  - '#package-verification'
date: '2026-10-13'
modified: '2026-10-14'
body_schema: 'body-v2'
body_hash: 'sha256:73a5eaf696c0c26e2f0c54accfb9bf557e754bf1b2abe87b616575ab0e8ea8f7'
related:
  - "[[2026-10-13-native-agent-adr]]"
  - "[[2026-10-12-live-agent-evaluation-adr]]"
  - "[[2026-10-13-desktop-agent-host-live-lane-adr]]"
  - "[[2026-10-13-native-agent-audit]]"
  - "[[2026-08-05-packaging-smoke-architecture-adr]]"
  - "[[2026-08-14-test-harness-sanity-successor-adr]]"
  - '[[2026-10-13-canonical-environment-application-internals-adr]]'
---
# `package-verification` adr: `Application-level verification runs only against the CMake package` | (**status:** `accepted`)

## Problem Statement

The CMake `bundle` target builds the application Cadrumo ships: `build/<preset>/stage/<Config>/app`. It holds the interpreter, the locked dependencies, the cadrumo-agent wheel, `bin/aeat`, `bin/cadrumo-mcp`, `bin/cadrumo-runtime`, `bin/cadrumo-agent-service`, the manager and the authority. Some development lanes still test the application some other way. They start cadrumo-agent from a source checkout, or start the desktop agent through a build feature that no shipped desktop has. Their passes then say nothing about the package, and the extra paths cost upkeep without shipping. The first hosted tool-access proof is also still unrecorded, and every packaged agent start is refused until it exists.

The owner, 2026-10-13: "we're working on ensuring that nothing in the codebase is divergent from the testing against the package binaries", "CLI and TUI work should remain - they predate application", "tui image review is valuable since the work depends on the cli and tui being lower level then the app so they need their own tests", and "I don't want extra of non prod convergence work. everything must be real and functional ... we should not build things we should not use."

## Considerations

Historical pre-service grounding follows; current Constraints/Implementation use the dedicated service.

- `2026-10-13-native-agent-adr` already rules that only CMake builds the agent wheel and that test runners never import an external checkout. Its CTest probe imports `cadrumo_agent.cli.main` and nothing more (`native/tests/agent_smoke.py`). So the runtime's launch of `-m cadrumo_agent`, a module with no `__main__.py`, went undetected.
- `2026-10-12-live-agent-evaluation-adr` already runs its lane against a verified copy of the package. It drives `cadrumo-mcp` with an agent client and does not exercise cadrumo-agent.
- `dev/runtime_lifecycle/caller_owned_root.py`, `live_sign_in.py` and `reviewed_operation.py` already require `--package` and resolve the package's own entry points (`caller_owned_root.py:74-77`, `:440`).
- `dev/runtime_lifecycle/agent_live.py` uses the package's `cadrumo-mcp` as the relay, but starts the gateway from a cadrumo-agent checkout (`agent_live.py:246`, `--agent-checkout`).
- The desktop's `agent-direct-start` Cargo feature (`native/desktop/src-tauri/Cargo.toml:12-17`, `native/desktop/src-tauri/src/agent/direct.rs`) starts the agent from `CADRUMO_AGENT_SOURCE_DIR`. `dev/desktop_agent_live` depends on it, and so does the proposed `2026-10-13-desktop-agent-host-live-lane-adr` through its deviation L2.
- The proof-table bootstrap is designed in cadrumo-agent, not missing. A hosted start refuses `hosted_tool_server_unproven` while `PROVEN_TOOL_ACCESS_LANES` is empty (`cadrumo-agent: src/cadrumo_agent/api/app.py:161-209`, `providers/lane_admission.py:478-483`). The runtime's agent door always sets the hosted root (`src/cadrumo/application/agent_host/launch_environment.py:113`). The agent's `development_tool_server` setting mounts the `cadrumo` relay entry on a non-hosted service under the `warn` policy, "so a live turn can ... earn the tool-server proofs a hosted service needs". It refuses to start beside a hosted root or under `enforce` (`cadrumo-agent: control/infra_config.py:331-341`, `:978-995`; `providers/hosted_mode.py:12-16`).
- The CLI and TUI sit below the application and run without it. Their tests, including the `dev/tui` visual review and the headless Pilot harness, test that layer directly. The PyPI, Homebrew and Scoop wheel channels are separate shipped products with their own accepted proof (`2026-08-05-packaging-smoke-architecture-adr`, `release.yml` with `dev/smoke`).

## Considered options

Scope of the rule:
- **Application-level process proofs only.** Chosen. These are proofs of the desktop, the runtime manager, the runtime as the application's host, the agent host and the cadrumo-agent integration. Unit and integration tests of library, CLI, TUI and MCP code keep running from source, where they are fast and isolated.
- **Every test against the package.** Rejected by the owner's ruling that the CLI and TUI keep their own tests. It would also need test tooling inside the shipped interpreter.

Earning the first hosted tool-access proof:
- **The agent's existing `development_tool_server` setting, run with the package's binaries.** Chosen. The staged interpreter runs the bundled agent, and the staged `cadrumo-mcp` serves the relay. The run uses a marked, non-hosted root, a synthetic profile signed in by the person's own door, and the real provider. It needs no new code in either repository, and the proof binds to what ships.
- **The same setting run from a cadrumo-agent checkout `.venv`.** Rejected. It certifies a build no person runs.
- **A new hosted-door mode that admits one unproven run.** Rejected. It builds a path used only once, and it weakens a refusal the agent's records keep on purpose.

Divergent lanes:
- **Repoint the existing lanes onto the package, and delete the paths only they used.** Chosen.
- **Keep the checkout paths as a fast development loop beside the package.** Rejected. The owner ruled out non-production convergence work. A rebuild is the cost of measuring what ships, and the incremental CMake build bounds it (`2026-10-07-cmake-incremental-build-plan`).

## Constraints

Binding:

1. **The boundary.** A test or lane whose claim concerns application behaviour as a process runs against `stage/<Config>/app`, unmodified, using the package's own interpreter, entry points and bundled cadrumo-agent. Application behaviour as a process means: the desktop, the manager, the runtime's lifecycle as the application's host, the dedicated agent service, the agent column, or cadrumo-agent serving Cadrumo. It never imports a source checkout, a development `.venv`, or a build feature absent from shipped configurations.
2. **What stays outside the boundary, from source or a wheel install:**
   - the unit and integration suites of `src` and `dev`;
   - the CLI and TUI tests, including `dev/tui` and `dev/tui/harness`;
   - `dev/acceptance`, `dev/smoke`, the `dev/packaging` wheel campaign and its oracles, and `test-channel-artifacts`, as the wheel channels' proof;
   - `dev/ingest_harness`, as domain measurement;
   - cadrumo-agent's own unit, component, service and acceptance tests, as agent-library proof.

   None of these may claim application coverage.
3. **The first tool-access proof.** It is earned once, by a live turn on the package's binaries:
   - the staged interpreter runs `-m cadrumo_agent.cli.main serve`, with `development_tool_server` set and no hosted root;
   - the relay is the staged `bin/cadrumo-mcp`;
   - the root is marked and disposable;
   - the profile is synthetic and signed in through `bin/aeat` on the protected secret channel;
   - the provider is the real one.

   The turn must meet cadrumo-agent's own recording rule: a tool of the `cadrumo` entry was called, served by the program the entry launches, with a person's session behind it, finishing real work with what the tool returned. Every later agent start goes through the dedicated agent service's hosted start. The setting is used for nothing else.
4. **Ownership of the proof record.** The cadrumo-agent owner records the proof in `providers/lane_admission.py` and makes the agent-side commits. Cadrumo supplies the package and the driver, and makes no commit in that repository.
5. **No new parallel paths.** No new harness, bootstrap mode or launch route is built for verification alone. A lane that diverges is repointed or removed. A code path whose only consumer was such a lane is removed with it.

Affected records, with proposed wording for owner approval:
- `2026-10-13-native-agent-adr`, Implementation, after "CTest runs the installed agent import, version, dependency and checksum probe through the application's own interpreter": add "It also exercises the assembled dedicated service and agent launch contracts, `-m cadrumo_agent.cli.main serve` on ephemeral ports, waits for the ready line, and stops it."
- `2026-10-12-live-agent-evaluation-adr`, Consequences, under "Where it stops": add "It does not exercise cadrumo-agent. The agent integration is proved by `dev/runtime_lifecycle/agent_live.py` against the same package, under `2026-10-13-package-verification-adr`."
- `2026-10-13-desktop-agent-host-live-lane-adr` (proposed): replace deviation L2 and the Implementation's "cadrumo-agent from its source tree". New text: "The lane starts cadrumo-agent only through the dedicated agent service's hosted start, from the package's bundled agent. It waits on the first recorded tool-access proof. The `agent-direct-start` feature is removed." Remove the corresponding sentence in Rationale.
- `2026-08-05-packaging-smoke-architecture-adr` and `2026-08-14-test-harness-sanity-successor-adr`: no change.
- cadrumo-agent records, proposed to their owner: `2026-10-10-cadrumo-integration-capability-proofs-adr` and `2026-10-11-cadrumo-integration-entry-network-proof-adr` state that a Cadrumo-facing proof is earned on the agent as Cadrumo's package ships it. `2026-10-11-cadrumo-integration-hosting-contract-adr` names `CADRUMO_AGENT_HOSTED_RELAY_EXECUTABLE`, which was part of the former launch proposal; current service composition advertises the tool server/program/material variables governed by canonical-environment, and leaves to the agent owner whether the two program-path variables stay, now that the agent may run Cadrumo's command line and Python (`2026-10-13-canonical-environment-application-internals-adr` constraint 17) (amended 2026-10-13 under `2026-10-13-canonical-environment-application-internals-adr`; before that this read: "and records the retirement of the two program-path variables it still names").

## Implementation

We will hold application-level verification to the package and retire what diverges. The outline below holds hypotheses that may change within the constraints:
- **Service launch.** The dedicated agent service launches `-m cadrumo_agent.cli.main serve`, and CTest environment-launch composition consumes the service-owned launch composer; `bundle.agent` remains the package-integrity probe.
- **`agent_live.py`.** The deterministic person-side driver carries package identity/held authority to the external agent-product runner; that runner consumes the bundled agent and staged `cadrumo-mcp`, never an agent checkout. It serves two purposes: the one-time proof run under `development_tool_server`, and afterwards the hosted door. The proof run works as follows:
  - The cited proof test is cadrumo-agent's capability tier. It runs as a client against the gateway the staged interpreter started (`CADRUMO_AGENT_CAPABILITY_GATEWAY_URL` and the related settings).
  - It asserts the served identity against the package's `data/package-manifest.json`: the interpreter, the agent wheel version and the relay executable.
  - The cadrumo-agent owner decides whether the relay path is bound into the proof.
- **Direct start.** `agent-direct-start`, `direct.rs` and the `webview2-remote-debugging` dependency on it are removed. `dev/desktop_agent_live` drives the packaged desktop, which launches the agent through the dedicated service.
- **cadrumo-agent side, proposed to its owner:**
  - `dev/cadrumo_testbed.py` reads `data/package-manifest.json` instead of hard-coding entry points;
  - the owner decides on `desktop-serve`, `desktop_tests` and `_live_desktop_gateway.py`, which no Cadrumo path uses.

The actual hosting owner is `src/cadrumo_agent_service`; neither tax `src/cadrumo` nor dedicated `src/cadrumo_runtime` has an agent launch door. Separate client contracts live in `src/cadrumo_client` and MCP in `src/cadrumo_harness`. Native-to-service ready/admin metadata is separate from inner hosting v1; inner credentials are mandatory even empty, optional bearer, ready port/version/contract only. CTest composition and opt-in live drivers use actual assembled service/agent/relay binaries and service-owned store preflight, without an AEAT agent/provider verb. The one-time agent-owner proof route remains its expressly scoped existing development setting; no new bootstrap path is authorized. Current user override runs no tests/build/proof gates, only coordinated importlint.

## Rationale

A proof of the application is worth having only if it measures what a person installs. The native-agent and live-agent-evaluation rulings already commit to that for the build and for MCP. This record extends it to every application-level lane and to the proof that admits the agent. The rest of the boundary follows layering: the CLI and TUI are lower layers with their own tests, and the wheel channels are separate products.

Using the agent's existing development setting with the package's binaries is the only option that is real end to end and builds nothing new. The checkout route certifies an artefact that does not ship. A hosted-door bootstrap mode adds code that runs once and loosens a deliberate refusal.

## Consequences

- An application-level lane needs a current `stage/<Config>/app`, so an agent or desktop change is tested after an incremental CMake build. That is slower than a checkout loop, and it is accepted.
- In practice the application lanes run only on Windows hosts until the other platforms' packages run. That is the package's real reach, not a test gap to paper over.
- No packaged agent starts until the cadrumo-agent owner records the first proof. The untracked cadrumo-agent files that `bundle.agent` imports must be committed by that owner before any package-based proof is reproducible.
- The packaged interpreter host strips every `CADRUMO_AGENT_*` variable before the agent's Python runs. Both the proof run and the hosted door depend on resolving that defect, which the accepted `2026-10-13-canonical-environment-application-internals-adr` resolves by declared agent invocation profiles; the stripping description here is historical defect grounding.
  - The strip runs in `cadrumo_platform_prepare` on every launch of the packaged interpreter except the supervised KDF child (`native/platform/src/lib.rs:189-210`, `native/interpreter/windows/host.c:129`, `:136`). The gateway's worker, which it spawns with the same interpreter and configures through the environment, is therefore stripped too.
  - cadrumo-agent reads `development_tool_server` only from the environment or from a settings file named by an environment variable (`cadrumo-agent: control/settings_base.py:15-30`), so there is no other carrier today.
  - The cadrumo-agent owner prefers to keep the environment as the one carrier, and to have the host admit the agent's names for the agent's launch and its worker. The gateway already refuses the development setting beside a hosted root or under `enforce`. That choice belongs to the canonical-environment record.

  This record builds no workaround for the stripping. `2026-10-13-canonical-environment-application-internals-adr` adopts the agent owner's preference through the agent gateway and worker launch profiles of a dedicated agent image (added 2026-10-13 under `2026-10-13-canonical-environment-application-internals-adr`).
- Removing `agent-direct-start` drops the desktop lane's fast loop until the hosted door admits the agent.
- Reconsider if a shipped platform cannot run its package in development, or if cadrumo-agent changes how a proof is recorded.
- Accepted 2026-10-13 on the owner's first-hand approval ("approved"), together with the proposed wording for the affected records above. Acceptance records the decision. It is not evidence that any of it is built.

## Boundary amendment 2026-10-14

Authorized by the user's explicit service/harness/native migration instruction. Original acceptance/proposal status, dated rulings and quotations remain unchanged. This amendment sets ownership obligations; it is not evidence of packaged or live acceptance. The current migration runs no tests and only the coordinated import-linter gate.

### Former implementation and ownership (historical)

> ## Constraints
> 
> Binding:
> 
> 1. **The boundary.** A test or lane whose claim concerns application behaviour as a process runs against `stage/<Config>/app`, unmodified, using the package's own interpreter, entry points and bundled cadrumo-agent. Application behaviour as a process means: the desktop, the manager, the runtime's lifecycle as the application's host, the agent door, the agent column, or cadrumo-agent serving Cadrumo. It never imports a source checkout, a development `.venv`, or a build feature absent from shipped configurations.
> 2. **What stays outside the boundary, from source or a wheel install:**
>    - the unit and integration suites of `src` and `dev`;
>    - the CLI and TUI tests, including `dev/tui` and `dev/tui/harness`;
>    - `dev/acceptance`, `dev/smoke`, the `dev/packaging` wheel campaign and its oracles, and `test-channel-artifacts`, as the wheel channels' proof;
>    - `dev/ingest_harness`, as domain measurement;
>    - cadrumo-agent's own unit, component, service and acceptance tests, as agent-library proof.
> 
>    None of these may claim application coverage.
> 3. **The first tool-access proof.** It is earned once, by a live turn on the package's binaries:
>    - the staged interpreter runs `-m cadrumo_agent.cli.main serve`, with `development_tool_server` set and no hosted root;
>    - the relay is the staged `bin/cadrumo-mcp`;
>    - the root is marked and disposable;
>    - the profile is synthetic and signed in through `bin/aeat` on the protected secret channel;
>    - the provider is the real one.
> 
>    The turn must meet cadrumo-agent's own recording rule: a tool of the `cadrumo` entry was called, served by the program the entry launches, with a person's session behind it, finishing real work with what the tool returned. Every later agent start goes through the runtime's hosted door. The setting is used for nothing else.
> 4. **Ownership of the proof record.** The cadrumo-agent owner records the proof in `providers/lane_admission.py` and makes the agent-side commits. Cadrumo supplies the package and the driver, and makes no commit in that repository.
> 5. **No new parallel paths.** No new harness, bootstrap mode or launch route is built for verification alone. A lane that diverges is repointed or removed. A code path whose only consumer was such a lane is removed with it.
> 
> Affected records, with proposed wording for owner approval:
> - `2026-10-13-native-agent-adr`, Implementation, after "CTest runs the installed agent import, version, dependency and checksum probe through the application's own interpreter": add "It also launches the agent the way the runtime does, `-m cadrumo_agent.cli.main serve` on ephemeral ports, waits for the ready line, and stops it."
> - `2026-10-12-live-agent-evaluation-adr`, Consequences, under "Where it stops": add "It does not exercise cadrumo-agent. The agent integration is proved by `dev/runtime_lifecycle/agent_live.py` against the same package, under `2026-10-13-package-verification-adr`."
> - `2026-10-13-desktop-agent-host-live-lane-adr` (proposed): replace deviation L2 and the Implementation's "cadrumo-agent from its source tree". New text: "The lane starts cadrumo-agent only through the runtime's hosted door, from the package's bundled agent. It waits on the first recorded tool-access proof. The `agent-direct-start` feature is removed." Remove the corresponding sentence in Rationale.
> - `2026-08-05-packaging-smoke-architecture-adr` and `2026-08-14-test-harness-sanity-successor-adr`: no change.
> - cadrumo-agent records, proposed to their owner: `2026-10-10-cadrumo-integration-capability-proofs-adr` and `2026-10-11-cadrumo-integration-entry-network-proof-adr` state that a Cadrumo-facing proof is earned on the agent as Cadrumo's package ships it. `2026-10-11-cadrumo-integration-hosting-contract-adr` names `CADRUMO_AGENT_HOSTED_RELAY_EXECUTABLE`, which the code already uses, and leaves to the agent owner whether the two program-path variables stay, now that the agent may run Cadrumo's command line and Python (`2026-10-13-canonical-environment-application-internals-adr` constraint 17) (amended 2026-10-13 under `2026-10-13-canonical-environment-application-internals-adr`; before that this read: "and records the retirement of the two program-path variables it still names").
> 
> ## Implementation
> 
> We will hold application-level verification to the package and retire what diverges. The outline below holds hypotheses that may change within the constraints:
> - **Runtime launch.** The runtime's agent door launches `-m cadrumo_agent.cli.main serve`, and CTest `bundle.agent` gains the launch and ready-line probe.
> - **`agent_live.py`.** It drops `--agent-checkout` and runs the staged interpreter's bundled agent with the staged `cadrumo-mcp`. It serves two purposes: the one-time proof run under `development_tool_server`, and afterwards the hosted door. The proof run works as follows:
>   - The cited proof test is cadrumo-agent's capability tier. It runs as a client against the gateway the staged interpreter started (`CADRUMO_AGENT_CAPABILITY_GATEWAY_URL` and the related settings).
>   - It asserts the served identity against the package's `data/package-manifest.json`: the interpreter, the agent wheel version and the relay executable.
>   - The cadrumo-agent owner decides whether the relay path is bound into the proof.
> - **Direct start.** `agent-direct-start`, `direct.rs` and the `webview2-remote-debugging` dependency on it are removed. `dev/desktop_agent_live` drives the packaged desktop, which launches the agent through the runtime's door.
> - **cadrumo-agent side, proposed to its owner:**
>   - `dev/cadrumo_testbed.py` reads `data/package-manifest.json` instead of hard-coding entry points;
>   - the owner decides on `desktop-serve`, `desktop_tests` and `_live_desktop_gateway.py`, which no Cadrumo path uses.
> 
