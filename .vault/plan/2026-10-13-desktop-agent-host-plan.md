---
tags:
  - '#plan'
  - '#desktop-agent-host'
date: '2026-10-13'
tier: L1
related:
  - '[[2026-10-13-desktop-agent-host-live-lane-adr]]'
  - '[[2026-10-12-desktop-agent-host-adr]]'
  - '[[2026-10-13-desktop-agent-host-live-lane-review-audit]]'
modified: '2026-10-13'
body_schema: body-v2
body_hash: 'sha256:f4939aad03aec04ca1b0362f59ee870e7224e39724d3ebf4ac57d5282d719893'
---

# `desktop-agent-host` plan

Build the live agent lane so the agent column runs against the real cadrumo-agent and Cadrumo, with a fast live test framework.

## Description

Approved 2026-10-13. Basis: the owner's first-hand directions of 2026-10-13: "I don't care about anything but that we test the agent ui against the real agent backend so we can debug and iterate fast", "ensure the agent testing framework is fast, and flexible and is capable of running against the application package", and "DO YOUR WORK THAT WAS BRIEFED TO YOU". The brief is the agent host end to end: the launcher, the gateway client, the stream and the live test framework. Governing record: `2026-10-13-desktop-agent-host-live-lane-adr` (revision 2), with the contracts it builds from `2026-10-12-desktop-agent-host-adr`. Review findings: `2026-10-13-desktop-agent-host-live-lane-review-audit`.

Launcher protocol, shared by S02 and S03:
- Command: `aeat app agent serve`, started by the desktop host with its projected environment. The owner's subsequent native-build brief requires the launcher to consume the CMake-installed agent in the canonical custom Python environment. No source path or alternate agent environment is admitted.
- Standard input: one JSON line `{"bearer": "<gateway bearer minted by the host>"}`. The host then holds the stream open. End of file means stop.
- Standard output carries JSON lines only. Diagnostics go to standard error, without content or secrets.
  - `{"event": "agent_ready", "gateway_port": <int>, "agent_version": "<str>", "lane": "development"}`
  - `{"event": "agent_refused", "code": "<code>"}`, where the code is one of `agent_signed_out`, `agent_runtime_unavailable`, `agent_service_absent`, `agent_service_incompatible`, `agent_provider_credential_missing`, `agent_root_unmarked` or `agent_service_failed`.
  - `{"event": "agent_stopped", "reason": "<code>"}`
- The provider key comes from the provider-settings resolver.
  - The launcher, which is now the runtime-hosted controller under `2026-10-13-provider-settings-adr` constraint 8, writes it to cadrumo-agent on a bounded standard-input frame only. It never goes in an environment block, file, command line, log, or off the machine.
  - Until cadrumo-agent reads that frame, no live run is possible.
- The launcher and its runtime door are built under `2026-10-13-provider-settings-plan` P04, not by this plan's S02. S02 closes on that delivery.
- The lane mark is `src/cadrumo/application/agent_host/lane_root.py`.
- The bearer reaches cadrumo-agent as `CADRUMO_AGENT_GATEWAY_TOKEN`.
- The launcher starts every agent process inside `WindowsProcessScope`.

Open dependencies outside this plan:
- The provider-settings resolver: until it lands, S02 refuses with `agent_provider_credential_missing`.
- cadrumo-agent's ordered turn records and offsets: until they land, S04 serves the turn fields it can derive and marks the rest unavailable, never fabricated.
- The review person door: until it is ruled, no host serves `cadrumo_review`.

## Steps

- [ ] `S01` - Gate every person act and admission door on one person-frontend predicate, add the agent-host frontend, and prove the door-by-frontend matrix; `src/cadrumo/application/operations/person_acts.py`.
- [ ] `S02` - Build the agent launcher that resumes the sign-in, guards the served root, and starts cadrumo-agent from its source tree inside a kill-on-close process scope on ephemeral ports; `src/cadrumo/entrypoints/cli/agent_host/`.
- [ ] `S03` - Supervise the launcher from the desktop host in a Job Object and stop it on every sign-in, profile and window trigger; `native/desktop/src-tauri/src/agent/`.
- [ ] `S04` - Serve the agent session to the webview through a gateway client, stream frames mapped onto session events over a Tauri channel, and the closed command list; `native/desktop/src-tauri/src/agent/`.
- [ ] `S05` - Drive the packaged desktop over WebView2 remote debugging with the shared agent specs, with no-survivor and key-pattern scans; `native/desktop/frontend/tests/live/`.
- [ ] `S06` - Add the desktop agent live recipe that builds the lane, creates and marks a fresh root, and runs the live specs; `justfile`.
- [ ] `S07` - Run stage 1 acceptance live and record its evidence; `native/desktop/frontend/tests/live/`.

## Parallelization

There are three workers with disjoint write scopes:
- S01 then S02, the Python backend under `src/cadrumo/`;
- S03 then S04, the Rust host under `native/desktop/src-tauri/src/agent/`, plus only its own registration lines in shared files;
- S05 then S06, the live test framework under `native/desktop/frontend/tests/live/` and the `justfile` recipe.

S02 and S03 meet at the launcher protocol above. S07 waits on all six. Each worker commits its own Steps through a private index and resyncs only its own paths.

## Verification

- S01: a door-by-frontend matrix test over the real registry and admission code. `mcp` and `agent-host` reach no person act; `cli` and `tui` keep theirs.
- S02: launcher tests against a real runtime on a disposable root:
  - refusal without a sign-in;
  - refusal on an unmarked or mismatched root;
  - `agent_ready` with an ephemeral port;
  - no process left after standard input closes or the launcher is killed.
- S03 and S04: Rust unit tests for frame decoding and event mapping on frames shaped by cadrumo-agent's `streaming/sse_frames.py`; host tests for the supervised runner's stop triggers. `cargo clippy` is clean.
- S05 and S06: the shared agent specs pass on the fixture host and attach to the packaged desktop. The recipe exits 3 when a prerequisite is absent.
- S07: the live-lane record's stage 1 acceptance, run live on the packaged build. The key-pattern scan and the no-survivor check must both be clean.
- Each Step runs its owning lint, format and type checks.
