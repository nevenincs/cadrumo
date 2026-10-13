---
tags:
  - '#plan'
  - '#live-agent-evaluation'
date: '2026-10-12'
tier: L1
related:
  - '[[2026-10-12-live-agent-evaluation-adr]]'
  - '[[2026-10-12-mcp-parity-agent-inside-the-signed-in-profile-adr]]'
  - '[[2026-07-02-agent-harness-refoundation-adr]]'
modified: '2026-10-13'
body_schema: body-v2
body_hash: 'sha256:5da728e58cc493182a3737b15c88e91f20393d4dafadca4b425cbc198f925813'
---

# `live-agent-evaluation` plan

Carry the 2026-10-12 live agent test into the project as a reproducible, opt-in lane that runs a haiku agent over MCP against a verified copy of the built package.

## Description

Approved 2026-10-12. Basis: the owner's first-hand "lgtm" on `2026-10-12-live-agent-evaluation-adr`, which also accepts its defaults (model `claude-haiku-5-5`, three runs with at least two reaching the end state), and the owner's standing instruction that agent work be finished and verified live.

This plan builds `dev/agent_eval/live/` and its two recipes as the governing ADR's Implementation section lays out. Decision coverage: `2026-10-12-live-agent-evaluation-adr` governs every Step (package copy, isolated root, scenarios, drivers, capture, oracle, access scenarios, recipes, floor). `2026-10-12-mcp-parity-agent-inside-the-signed-in-profile-adr` governs the access rules the lane holds from its own side in S03, S05, S06 and S08: the agent never authenticates, never holds a secret, and is refused without a live sign-in or a valid key. `2026-07-02-agent-harness-refoundation-adr` R7 is the substrate the lane drives (`LiveTrajectory`, `score_live_trajectory`). No new costly decision is involved; the evidence is `2026-10-12-live-agent-evaluation-reference`.

Scope bounds: the lane never edits `src/cadrumo_harness/mcp` or runtime code, which belong to the mcp-parity P10 work; it does not depend on the session, installation, authenticate or authorization tools that P10 removes. Person-side acts go through the packaged command line. A package built before P10 lands is expected to fail the no-secret-offered invariant. The live run (S11) waits for P10 and a rebuild, and needs an interactive logon whose credential store works; on an SSH logon the lane reports unavailable.

## Steps

- [x] `S01` - Correct the dev/agent_eval docstring to state what the package imports from the product; `dev/agent_eval/__init__.py`.
- [x] `S02` - Verify the staged bundle package against its manifest, copy it to the development build root, verify and re-verify the copy, and compare its first-party modules with the checkout, refusing a stale package unless asked, with positive controls for a changed byte and a stale module; `dev/agent_eval/live/package_copy.py`.
- [x] `S03` - Host the copied package on a fresh isolated storage root, running the installation record, profile creation, sign-in and teardown as package code through the copy's interpreter and command line, with the runtime launched unsupervised with the manager's arguments inside a kill-on-close scope and an allow-listed environment, and classify an unusable credential store as unavailable; `dev/agent_eval/live/isolated_host.py`.
- [x] `S04` - Declare the live scenario files, Modelo 130 on the DR 130 worked example first and then Modelo 303 for the same quarter, with their loader and required subsequences; `dev/agent_eval/live/scenarios`.
- [x] `S05` - Drive the agent through the Anthropic API with an MCP client loop or the authenticated claude CLI fallback, always claude-haiku-5-5, both producing one LiveTrajectory, with turn, token and spend limits; `dev/agent_eval/live/drivers.py`.
- [x] `S06` - Scrub the stream before anything is written and capture the scrubbed trajectory, receipt and score to .logs/agent-eval/ behind a fail-closed residual scan, with a positive control on a planted secret; `dev/agent_eval/live/capture.py`.
- [x] `S07` - Read the oracle through the packaged command line JSON envelopes and the product export parser under the copy's authority, and fail on any disagreement, with a positive control on a planted disagreement; `dev/agent_eval/live/oracle.py`.
- [x] `S08` - Drive the access scenarios from the person's side through the packaged command line: key issue, use in scope, refusal out of scope, revocation mid-run, locked, signed out and expired, each requiring the agent to send the person back to Cadrumo; `dev/agent_eval/live/access.py`.
- [x] `S09` - Add the opt-in recipes eval-agent-floor and eval-agent-live with a receipt, the three-run pass rule and distinct outcome classes and exit codes, kept out of every default lane; `justfile`.
- [x] `S10` - Run the scripted floor on this host and prove that a refused credential store is classified unavailable, never a pass; `dev/agent_eval/live/lane.py`.
- [ ] `S11` - Run the live lane, three runs per scenario, on the operator's interactive desktop logon after the mcp-parity P10 surface lands and the bundle is rebuilt, and record the receipt; `.logs/agent-eval`.

## Parallelization

Sequential. S02 and S03 precede every Step that runs the package. S04 to S08 can be written in any order once S03 exists, but share the run orchestration and land one at a time. S09 and S10 follow S08. S11 follows P10 of the mcp-parity plan and a bundle rebuild, on the operator's interactive logon.

## Verification

- `dev/agent_eval/tests` passes, including the positive controls: the scrubber fails on a planted secret, the copy check fails on a changed byte and on a stale module, the oracle fails on a planted disagreement, and the verdict rules classify an unusable credential store as unavailable.
- Ruff, ruff format and ty pass on touched files, and `just check-import-boundaries` passes.
- `just eval-agent-floor` and `just eval-agent-live` are declared only in the justfile, are reached by no default lane, and on this SSH host exit with the unavailable class and its reason.
- S11 closes only on a receipt from the operator's interactive logon showing three runs, every hard invariant held and at least two runs reaching the end state with the oracle in agreement.
