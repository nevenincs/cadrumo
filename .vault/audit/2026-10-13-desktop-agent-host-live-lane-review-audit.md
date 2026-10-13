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

## Recommendations

Pending the remaining reviews; proposed revisions will be presented to the owner together.
