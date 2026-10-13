---
tags:
  - '#audit'
  - '#desktop-agent-host'
date: '2026-10-13'
modified: '2026-10-13'
body_schema: 'body-v2'
body_hash: 'sha256:f4f29e15a376eb56bf1e0825cb270d45e325889a97d2bb48842da8d8d9426c11'
related:
  - "[[2026-10-13-desktop-agent-host-live-lane-adr]]"
  - "[[2026-10-12-desktop-agent-host-adr]]"
---



# `desktop-agent-host` audit: `Live lane design review`

## Scope

Review of the proposed `2026-10-13-desktop-agent-host-live-lane-adr` and the contracts of `2026-10-12-desktop-agent-host-adr` it builds. The owner directed on 2026-10-13 that the cadrumo-agent project and Cadrumo's engineering sessions review and verify the design before any ruling. Requests went on 2026-10-13 to CADRUMO-ARCHITECTURE, BUILD1, BUILD2 and tui-b3. main-7c declined, being on an unrelated project. No cadrumo-agent session is reachable, so its review is an Opus reviewer's reading of that project's code and accepted records, which stands in for the project and is labelled as such. Each finding names its reviewer. Verified means the reviewer read the locator. Inferred means it did not.

## Findings

### desktop-child-containment | critical | The desktop has no long-lived child owner and no process containment

BUILD2, verified. Every shell child runs to completion under a deadline (`native/desktop/src-tauri/src/shell/sign_in/process.rs:196-226`, `:476-530`). Stdin is a one-shot piped secret or null (`:326-330`). `stop()` reaps only those children (`:157-195`). The desktop uses no Job Object; only `native/manager/src/service_windows.rs:267-327` does. `ChildConfiguration` can build a long-lived child (`native/application/src/child.rs:89-96`), but nothing in the Rust host owns one. If the desktop crashes, stdin EOF at the launcher is the only stop signal. The records should require the launcher to start cadrumo-agent inside a kill-on-close Job, through the existing owner `WindowsProcessScope` (`src/cadrumo/adapters/local_runtime/windows_process.py:189-232`, used by `dev/runtime_lifecycle/harness.py` and `dev/agent_eval/live/isolated_host.py`). Then the gateway, its worker and `cadrumo-mcp` die with the launcher, even when it is terminated hard. "End and confirm the process tree" is not enough.

### fixed-agent-ports | critical | cadrumo-agent's ports 18000 and 18001 are fixed and collide

BUILD2, verified. A second desktop, a development display or a leftover gateway collides on these ports, and nothing in Cadrumo reserves them. The launcher should bind ephemeral ports and report them in `agent_ready`, or refuse when the ports are occupied.

### key-reaches-relay-grandchild | medium | The Anthropic key in the agent's environment may reach `cadrumo-mcp`

BUILD2, inferred. Under L3 the launcher sets `CADRUMO_AGENT_ANTHROPIC_API_KEY` after `child_environment` clears `CADRUMO_*`. cadrumo-agent's children inherit it, including the relay grandchild, unless the relay clears it. Add the scrub to the parent record's verification criterion 5.

### source-path-packaging | medium | A source-path cadrumo-agent breaks two packaging checks

BUILD2, verified; BUILD1 owns the final answer.
- `_registry_package` requires exactly one pypi.org registry package (`dev/packaging/runtime_wheel_selection.py:198-210`).
- The product cohort check requires the built wheels to equal `PRODUCT_IDENTITY.cohort_distributions` (`dev/packaging/native/product.py:101-105`).

A lane-only option needs an explicit second wheel source, not a weaker selector. The `user_docs` statement (`dev/packaging/native/assemble.py:295-299`; `native/application/src/package.rs`) is the right template for the agent statement. The reference's anthropic conflict is stale: the extra is now `>=1.13.0,<2` (`pyproject.toml:178-179`), and it is not bundled (`BUNDLED_EXTRAS = ("llm",)`, `dev/packaging/native/product.py:31`).

### no-desktop-driver | medium | Stage 1 acceptance needs a desktop driver that does not exist

BUILD2, verified. The live recipes `dev/runtime_lifecycle` and `dev/agent_eval/live` do not open Tauri. Their patterns, which the lane recipe should follow, are:
- a fresh root under `build/acceptance`;
- real package binaries;
- the password on stdin only;
- a Job;
- a check that no started process survives;
- exits 0, 1 and 3.

Stage 1's checks on the transcript, stop, reload and send refusal need a desktop driver. `eval-agent-live`'s doc string names a Claude model id, which conflicts with the ruling that model ids come from the Models API.

### storage-root-override-unproven-live | low | The storage-root override is honoured in code but not run live

BUILD2, verified in code. The projection pins the root for children (`native/desktop/src-tauri/src/environment.rs:187`, `:211-250`; `native/platform/src/storage.rs:648-700`). A non-default root hosts its own supervisor claim and endpoint (`native/desktop/src-tauri/src/manager.rs:370`, `:427-431`). Still unverified is whether a `stage/Release/app` package is detected as Installed or as Development (`manager.rs:735-760`). The lane's first run must prove it.

### launcher-ownership-consistent | low | The launcher is a runtime client and does not conflict with runtime ownership

BUILD2, verified. The manager and the GUI supervisor own only the runtime (`native/desktop/src-tauri/src/manager.rs:357-420`). The launcher is a client like `config sign-in-hold`. The desktop-shell amendment the parent record lists is still required.

### agent-host-person-authority | critical | A new `agent-host` frontend would gain the person's authority by default

tui-b3, spot-checked.
- Person acts are refused on MCP only (`src/cadrumo/application/operations/person_acts.py:79-81`; `src/cadrumo/application/user_profile/operation_access_policy.py:217`).
- Login and enrollment admission gate on "not a person's frontend" in three places (`src/cadrumo/entrypoints/runtime/profile_connection_admission.py:162`, `:277`; `src/cadrumo/application/ledger/invoice_evidence_extract_operation.py:282`).
- A new `agent-host` value in `OperationFrontendProjection` (`src/cadrumo/application/operations/registry.py:190-199`) would therefore get password sign-in, key administration, secret-bearing operations and consent acknowledgement.

The predicate should be inverted, so that person acts are allowed on `cli` and `tui` only, and each of these sites named as changing with the enum.

### agent-self-approved-review | critical | The model can apply its own reviewed mutation on the full surface

tui-b3, spot-checked. The full surface admits `review` and `respond` (`src/cadrumo/application/operations/mcp_surfaces.py:114-122`), and `respond` accepts `action: apply` (`src/cadrumo_harness/mcp/protocol_contract.py:337-350`). So "take reviews to the person" is not enforced. Stage 1 acceptance must show that the model cannot reach `respond apply`, and must say who can.

### relay-root-binding | critical | The relay's `cadrumo-mcp` can resolve the person's real storage root

tui-b3, spot-checked. The relay launches `cadrumo-mcp` by bare name with no root. With `CADRUMO_LOCAL_STORAGE_ROOT` unset, the child resolves the per-user default (`src/cadrumo/core/storage_environment.py:160-191`). A lane server could then be admitted into the person's real profile with write tools, and the mark check would never see it. The lane must require two things:
- the lane bundle's absolute `cadrumo-mcp` executable;
- an inherited, pinned root (`child_environment`, `storage_environment.py:653-690`).

Both belong in Stage 1 acceptance.

### l3-key-exposure-bounds | medium | L3 is bounded only by same-user trust

tui-b3. The key in an environment block contradicts the parent record, and a same-user process can read that block on Windows. The record should state three things:
- L3 rests on same-user trust;
- the stored key is a real secret even on a synthetic profile;
- discarding the root wipes it.

### admission-door-unnamed | low | The lane's admission door is not named

tui-b3, spot-checked. Attendance is refused to every non-MCP frontend (`src/cadrumo/entrypoints/runtime/profile_connection_attendance.py:81`), so an `agent-host` connection cannot be attended. Name receipt resume as the lane's door. tui-b3 is separately fixing the attended lease's expiry refusal.

### agent-review-reaches-person | high | No route exists for the person to answer a review the agent raised

tui-b3, spot-checked. The interaction bearer is process-local and bound to its actor (`src/cadrumo/application/operations/_projection_authority.py:86-113`), so no other process can answer the agent's pending review, the desktop included. The recommended shape:
- the agent reads `review` as data;
- Cadrumo words it and the host shows it;
- the `respond apply` call goes out on the agent's own connection, behind a host-held gate that only a deliberate person gesture releases, never a tool the model can call.

This needs a follow-on decision. INPUT and CHOICE stay unsupported.

### tui-parity-consent | low | The TUI should offer consent grant, withdraw and list; the credential act can wait

tui-b3, spot-checked. The TUI is a person frontend, and its modal already answers REVIEW (`src/cadrumo/entrypoints/tui/operations/interactions.py:49-66`). It has no off-host consent screen today. The credential act carries a secret the generic modal cannot take, so it waits for the protected input channel.

### review-door-for-agent-reviews | critical | No person door answers a review raised by an agent session

CADRUMO-ARCHITECTURE, spot-checked; agrees with tui-b3.
- `respond` acts as the agent's own session (`src/cadrumo_harness/mcp/admitted_operations.py:445-481`).
- The host lets only the submitting session answer, through a process-local capability (`src/cadrumo/entrypoints/runtime/operation_host.py:330-345`, `:592-624`).
- The TUI answers only reviews of operations it submitted (`src/cadrumo/entrypoints/tui/operations/interactions.py:3-7`).

The owner must rule between two options:
- (i) the conversational relay, stated as such, where the agent applies its own review;
- (ii) a person door that answers a review raised by an agent session in the profile, with `respond` apply withheld from agent frontends. This is new runtime authority and amends the mcp-parity agent-inside record.

### lane-mark-checks-wrong-root | critical | The mark check reads the launcher's root, not the root its runtime serves

CADRUMO-ARCHITECTURE, spot-checked. No mark mechanism exists (`dev/agent_eval/live/isolated_host.py:98-119`). A GUI attaches to an installed manager (rule 04), so a lane desktop started with an override could reach a runtime serving the person's real root. The guard must compare the root reported by the connected runtime, after canonical resolution (junctions, case folding, subst drives). The record must also say how a lane desktop gets a runtime on the marked root while an installed manager exists.

### provider-key-release-is-new | high | Releasing a stored provider key to a client process has no precedent

CADRUMO-ARCHITECTURE, spot-checked. No client receives a stored secret's plaintext today (`src/cadrumo/adapters/outbound/google/records.py:48-75`; `src/cadrumo/adapters/outbound/llm/client.py:955`). Cadrumo has no provider-credential namespace. The records to amend:
- application-sign-in, line 70;
- mcp-parity agent-inside, constraint 1;
- rule 05, for the namespace;
- the LLM settings and canonical-environment records, which need one precedence rule for the key source.

Key entry in the desktop passes through the webview and Tauri, like the password.

### agent-frontend-predicate | high | Person-act refusal is hard-coded as "is MCP" at many sites

CADRUMO-ARCHITECTURE, spot-checked; extends `agent-host-person-authority`. The sites:
- `person_acts.py:81-83`
- `operation_access_policy.py:213-219`
- `profile_connection_admission.py:161-163`, `:277`
- `profile_connection_sessions.py:229-231`
- `profile_connection_access.py:163-168`
- `profile_connection_person_acts.py:37-40`
- `invoice_evidence_extract_operation.py:282-284`

Recommended as a named stage 1 item: one "agent frontends" predicate, and a door-by-frontend matrix test.

### frontend-kind-unauthenticated | medium | The runtime does not authenticate the frontend kind

CADRUMO-ARCHITECTURE, spot-checked. The client sets the frontend kind (`src/cadrumo/entrypoints/cli/config/passphrase.py:77`), and admission does not check the image. So "the agent cannot grant consent" holds only while the agent cannot start processes. The direct-lane-only constraint protects consent integrity too; the Claude Code lane would break it. The application-sign-in record still carries wording its own amendment contradicts, at lines 255, 264 and 270.

### launcher-runner-and-grandchild-admission | low | A grandchild resumes, and a supervised runner is needed

CADRUMO-ARCHITECTURE, verified.
- Admission is bound to the logon session, not to the process chain (`src/cadrumo/adapters/local_runtime/windows_channel.py:47-68`; `windows_login.py:40-42`; `profile_login.py:104-130`), so `cadrumo-mcp` as a grandchild resumes. That is a pass.
- Consent through an `aeat` child passes today (`src/cadrumo/entrypoints/cli/runtime_profile_admission.py:118-141`; `session_authority_admission.py:383`).
- The shell's child runner is built for short calls (`native/desktop/src-tauri/src/shell/sign_in/process.rs:23-27`, `:408-416`, `:513-522`). The shell amendment must name a new supervised runner and the sign-in-expiry stop trigger.

### packaging-closure-and-lane-lock | critical | The agent's 39-package closure fails assembly; the lane needs its own lock

BUILD1, verified in scratch.
- Assembly requires the installed set to equal the cohort plus Cadrumo's lock export exactly (`dev/packaging/native/assemble.py:170-184`).
- The product build collects every wheel in its output directory (`dev/packaging/native/product.py:106-110`).

The recommended route:
- build the agent wheel with `uv build --wheel` into its own directory, installed with `--no-deps` and its digest recorded;
- a lane-only lock project inside Cadrumo, holding the agent's requirements constrained to Cadrumo's pins, with the selector given a lock-path parameter;
- assembly's allowed set widened by that lock, as one named exception.

hatch packages every file on disk, and the agent checkout carries about 250 uncommitted files, so its source must be snapshotted through a filesystem inclusion policy. The constraint changes 8 packages from the agent's tested lock, not 6. There are no missing wheels, and websockets does not conflict.

### lane-build-option-wording | high | No release configure preset exists to refuse the lane option

BUILD1, verified. Release is a configuration of a multi-config preset (`CMakePresets.json:95-112`; `native/cmake/Configurations.cmake:2-4`). The workable form:
- a dedicated lane configure preset;
- Release configurations and the release and installer targets refusing when the option is on;
- the option recorded in the contract and metadata, as `CADRUMO_CHANNEL` is (`Identity.cmake:31`);
- `artifact_verify` refusing a lane manifest (`artifact_verify.py:78-90`).

### agent-manifest-statement | low | The agent statement fits the manifest; it has three readers

BUILD1, verified. `PackageManifest` admits an optional field (`native/application/src/package.rs:20-37`). The readers are `package.rs:124-140`, `native/interpreter/bootstrap.py:67-80` and `dev/packaging/native/package_inventory.py:57-73`. Bundled must agree with `distributions`. Hosting-contract and store-format versions do not exist yet. BUILD1 recommends BUILD2 own the packaging Step.

### agent-relay-unmountable-in-bundle | critical | A bundled, non-hosted cadrumo-agent cannot mount the Cadrumo relay

cadrumo-agent review (stand-in reviewer). Without a root, the relay comes on only through the test-tree `hosted_parts` plugin (`agent:providers/lane_registry.py:212-237`; `agent:testing/lanes/hosted_parts.py:58`), and `testing/` is excluded from the wheel (`agent:pyproject.toml:172-200`). The uncommitted change deletes that route. The agent's records forbid mounting the relay outside hosted mode: relay-mount `:153` and write-gate `:101`.

### agent-proofs-unearnable-on-lane | critical | Tool proofs are recorded only by cadrumo-agent's own tests

cadrumo-agent review (stand-in reviewer).
- A proof is a hand edit naming a pytest node id in that repository (capability-proofs).
- Write proof needs refusal, exactly-once, worker-loss and repeat cases (`agent:providers/lane_admission.py:462-484`), and the settled-run fix must be built first.
- A Cadrumo lane run or the owner's use cannot record one.
- The uncommitted record edit requires production startup, which refuses without proofs, so nothing could ever be proven.

### non-hosted-writes-unsafe | critical | Non-hosted mode can repeat a Cadrumo write

cadrumo-agent review (stand-in reviewer). Non-hosted runs re-send accepted actions and retry turns (`agent:api/app.py:850-884`), and a settled run can still be writing. Deviation L2 breaches four records the parent does not name: relay-mount, write-gate, hosted-mode and capability-proofs. In non-hosted mode, state, `.env` reads and temporary files fall outside the lane root (`agent:control/settings_base.py:242-262`), and tracing is not refused.

### history-cannot-serve-session-contract | critical | cadrumo-agent's history cannot serve `agentSession.ts`

cadrumo-agent review (stand-in reviewer). Gaps against the contract:
- One reply is one message, with text joined across tool rounds (`agent:providers/anthropic_chat_model.py:651-671`).
- Messages and tool calls are unordered lists (`agent:thread/snapshots.py:313-337`).
- Tool calls are reported only when done.
- Frames carry no offset, and over-long chunks are cut without a mark.
- A turn in progress is absent from history.
- The person's turn id is not returned (`agent:api/schemas/gateway.py:229-243`, `:527-555`).
- Continued runs duplicate earlier turns under new ids (`agent:worker/graph_lifecycle.py:571-583`).

### bundle-strips-agent-environment | high | The packaged host strips cadrumo-agent's variables and ships no Python program

cadrumo-agent review (stand-in reviewer).
- The native host strips `CADRUMO_*` names outside the allowlist before Python runs (`native/platform/src/lib.rs:189-210`).
- The bundle ships only three entrypoints (`native/package-layout.json:42-46`).
- The worker re-executes as `sys.executable -m` (`agent:utils/runtime_exec.py:72-88`).
- `runs_settled` is always false in non-hosted mode (`agent:api/app.py:861`).

Also:
- The proof's one-minor SDK range collides with the latest-SDK-only ruling.
- The relay change's 12-tool entry matches Cadrumo, but the change should not be committed as is.

Nine more agent records are contradicted beyond the five the parent names.

### key-frame-absent | critical | cadrumo-agent has no way to take the key except the environment or settings

cadrumo-agent review (stand-in reviewer), against the owner's 2026-10-13 ruling.
- The key comes from the environment, or in non-hosted mode from settings files (`agent:providers/provider_readiness.py:136-154`; `agent:control/settings_base.py:106-129`).
- The worker inherits `os.environ.copy()` (`agent:control/worker_management.py:159`).

The fix:
- a process-local holder;
- a frame read in `agent:api/app.py` `main()` and at worker start;
- the frame written to the worker's pipe instead of `DEVNULL`.

The relay child is already scrubbed (`agent:workspace/environment.py:155-183`). Cadrumo's own LLM adapter also reads its key from the environment (`src/cadrumo/core/config_llm_fields.py:52-55`), which breaks the same ruling.

## Recommendations

Pending the remaining reviews; proposed revisions will be presented to the owner together.
