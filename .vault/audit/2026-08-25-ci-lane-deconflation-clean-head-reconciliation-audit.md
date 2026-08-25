---
tags:
  - '#audit'
  - '#ci-lane-deconflation'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:437f7277322d550e3ca1158dc30c1b3d193da825498ea71e17b532ad41851ef8'
related:
  - '[[2026-08-05-ci-lane-deconflation-plan]]'
  - '[[2026-07-21-ci-discipline-adr]]'
---

# `ci-lane-deconflation` audit: `Reconcile the tooling gate against clean HEAD`

## Scope

The only remaining implementation row was remeasured from an isolated detached worktree rather than the shared dirty tree. Semantic discovery and history were used before each repair so deleted authorities were not restored. The exact `test-dev-tooling` selection was run sequentially with fail-fast enabled to expose one committed-HEAD defect at a time.

## Findings

### retired-runner-observation | medium | a one-time serial build observation was stranded as permanent implementation work

`P02.S10` no longer described a capability this plan could implement. Immutable packaging-cohort construction and its integration/serial verification are already owned by the packaging and release surfaces. The old row instead required observing a particular runner execution after unrelated gates happened to clear. It was retired rather than checked; no execution record existed to archive.

### relocated-command-policy-consumers | high | three agent-eval goldens still imported deliberately deleted authorities

Commit `005b1c2fdce` retired the application operator-surface risk table onto the harness `CommandPolicyProjection`, but two goldens still imported `command_classification` and a third still imported the deleted mutable `declared_live_write` test seam. The consumers now read the public descriptor projection used by the live pre-tool policy. The direct hypothetical live-write-to-block proof remains single-homed in the harness policy tests. A second stale test-session import was repointed to the canonical helper relocated by `5d04d0d4df`.

### module-size-debt | high | the tooling lane now reaches five genuine oversized CLI authorities

After collection repaired, the first behavioral failure is the hard 1,250-line production-module ceiling. The offenders are `_app_ledger_command_specs.py` at 7,337 lines, `_modelo_nonwork_command_specs.py` at 3,147, `_app_live_command_specs.py` at 1,875, `_common.py` at 1,707, and `_app_live_payloads.py` at 1,329. These are authored production authorities, not generated artifacts.

The absence of baseline entries is intentional. Normal regeneration does not admit a newly oversized subject; `--accept-growth` would launder the finding. No carveout or raised ceiling is justified. The ledger and live command-spec authorities can be split independently. Modelo specs overlap the active TUI lane, live payloads overlap the DEHu lane, and `_common.py` overlaps secure-storage work, so those three must be serialized with their owners.

### closure-verdict | high | the workflow flag must remain non-blocking for now

`P02.S41` remains open. Removing `continue-on-error` before the complete tooling selection reaches zero would create a permanently red blocking lane. The plan may route the discovered decomposition work, but it may not count that routing as closure.

## Recommendations

- Split the clean ledger and live command-spec authorities first, preserving their import-light tuple composers.
- Coordinate the remaining three splits with their active owners rather than editing overlapping lanes.
- Regenerate the size baseline normally only after every offender is at or below 1,250 lines.
- Rerun the complete tooling selection and remove only the dev-tooling step's `continue-on-error` flag when it is green.
