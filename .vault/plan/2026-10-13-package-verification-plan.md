---
tags:
  - '#plan'
  - '#package-verification'
date: '2026-10-13'
tier: L1
related:
  - '[[2026-10-13-package-verification-adr]]'
  - '[[2026-10-13-native-agent-adr]]'
  - '[[2026-10-12-live-agent-evaluation-adr]]'
  - '[[2026-10-13-desktop-agent-host-live-lane-adr]]'
  - '[[2026-10-13-canonical-environment-application-internals-adr]]'
modified: '2026-10-17'
body_schema: body-v2
body_hash: 'sha256:f72688b39aa97e70c8bafe6881f3d3defae22539b8fdef340a3f6570df38b646'
---

# `package-verification` plan

Hold application-level verification to the CMake package and retire the lanes and paths that diverge from it.

## Description

Approved 2026-10-13 on the owner's first-hand "approved, execute" for this plan.

Governing decision: `2026-10-13-package-verification-adr`, accepted 2026-10-13. Under it, application-level process proofs run only against `stage/<Config>/app`. Lanes that diverge are repointed or removed, and nothing is built for verification alone. The ADR's amendments are already applied to `2026-10-13-native-agent-adr` (S02), `2026-10-12-live-agent-evaluation-adr` (scope note only) and `2026-10-13-desktop-agent-host-live-lane-adr` (S04). No further costly decision is involved.

Step mapping:
- S01 is routine dead-code removal under the owner's cleanup direction. Each item is confirmed by grep and by the zero-target reachability and usage gates before it is deleted.
- S02 implements the native-agent amendment.
- S03 and S05 implement the ADR's constraint 3 and its `agent_live.py` outline.
- S04 implements the constraint against parallel paths and the live-lane revision.

S03 and S05 reshaped 2026-10-13 on the owner's first-hand approval ("approved!"). The split was agreed with CADRUMO-AGENT-CODE:
- cadrumo-agent's package runner is the only starter of the packaged gateway (`bin/cadrumo-agent`).
- The agent live lane supplies the Cadrumo person side and the independent oracle.
- The two exchange JSON receipts and command-line arguments, never each other's environment variables, because Cadrumo code defines no `CADRUMO_AGENT_*` value.
- The caller's storage root reaches the relay through the agent-gateway profile's `CADRUMO_LOCAL_STORAGE_ROOT` slot, which the gateway forwards to the relay only.
- S02 is covered by the canonical-environment plan's P04.S14 CTest launch probe, and closes when that lands.

Dependencies outside this plan:
- S02, S04 and S05 need a packaged host that passes the agent its environment. That is `2026-10-13-canonical-environment-application-internals-adr`, which is proposed and owned by tui-ee, with preference B forwarded to it.
- S05 also needs CADRUMO-AGENT-CODE to commit the untracked agent files, and to record the proof in `providers/lane_admission.py`.
- This plan makes no commit in cadrumo-agent.

## Steps

- [x] `S01` - Remove the dead dev tooling the sweep confirms: the uninvoked pytest shard plugin, per-file ignores for missing modules, references to the absent no-skip gate, and dev/audit screens no recipe runs, updating the recipe and lane policing tests in the same change; `dev/quality/shard.py`.
- [x] `S02` - Extend the bundle.agent CTest probe to launch the bundled agent the way the runtime does, wait for its ready line and stop it; `native/tests/agent_smoke.py`.
- [ ] `S03` - Reshape the agent live lane as the Cadrumo person side of the packaged proof: drop its checkout option and its own gateway start; on the staged package create the marked root, sign a synthetic profile in through bin/aeat on the secret channel and hold it, write the hand-off receipt for the cadrumo-agent package runner, attend its approvals, then read the runner's receipt and run the independent aeat oracle on the marked root; `dev/runtime_lifecycle/agent_live.py`.
- [x] `S04` - Remove the desktop direct-start feature and repoint the desktop agent live lane onto the runtime's hosted agent door with the catalog's provider and key names; `native/desktop/src-tauri/src/agent/direct.rs`.
- [ ] `S05` - Run the packaged proof runs with the cadrumo-agent package runner as the only gateway starter and the agent live lane as the person side: re-earn the completed-turn proof and earn the first hosted tool-access proof, each request inspected and approved per start, for the cadrumo-agent owner to record; `dev/runtime_lifecycle/agent_live.py`.

## Parallelization

S01 is independent and runs first.
- S02 and S03 can run in parallel once the canonical-environment fix lands in the package. They touch disjoint files.
- S04 follows S03, because it reuses the hosted-door launch S03 proves.
- S05 is last, and it runs with CADRUMO-AGENT-CODE.
- Native builds use a build directory not in use by another session. tui-ee owns `build/windows-x64` and `build/distribution-windows-x64` while its cold build runs.

## Verification

- S01:
  - `just check-style`, `just check-types` and `just check-import-boundaries` pass;
  - the module-reachability, symbol-usage and export-consumption gates stay at zero;
  - `dev/tests/test_dev_cli_justfile_wiring.py` and `dev/tests/test_lane_reachability.py` pass;
  - `dev/audit/tests/test_vulture_whitelist_is_not_stale` passes.
- S02: CTest `bundle.agent` passes on a fresh `Release` bundle. A planted launch failure (a module that does not exist) makes it fail.
- S03: `just verify-agent-live` passes against `stage/<Config>/app`, with no checkout path in its receipt.
- S04:
  - `agent-direct-start` and `direct.rs` are gone;
  - the desktop builds without the feature;
  - `just desktop-agent-live` reaches the agent through the runtime's door.
- S05: CADRUMO-AGENT-CODE records the tool-access proof. Afterwards, a hosted start from the package reaches `agent_ready`.
- Plan close: one integrated review against the ADR.
