---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:c1f08ed13a98fbeb9e3a3a0b75692ed2e30de7bb3941b9a5af05d953f474b29a'
step_id: 'S197'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Sol Medium rule whether the extracted harness distribution ships in the published release cohort and at which version, since three release lanes still install a retired extra and then probe for a launcher it no longer supplies, the cohort wheel enumeration does not name the harness at all, and the harness sits on its own version line while the other three are version-locked by a parity gate, so no rename can resolve it

## Scope

- `dev/packaging/_acquire_common.py and dev/packaging/acquire_pypi.py and dev/packaging/oracle_emit_cohort.py and dev/release/tests/test_readiness.py`

## Description

Adjudicate the harness cohort exclusion, sweep the owned cohort against the canonical custody door, and retain the documented exclusions whose subjects require distinct lifecycle control.

## Outcome

Ruled: the harness distribution ships in the published release (PyPI pin, MCPB embed) but is NOT a release-cohort member; its independent version line is the deliberate, three-place-encoded design, so enrolment (Option A) was rejected and the exclusion was completed (Option B). Swept: the plugin workspace's both launcher forms now pin `cadrumo-harness==<its own metadata version>`; the scoop generator drops the retired `[agent]` extra and the cadrumo-mcp wrapper (bin manifest and walkthrough updated); the scoop and homebrew acquisition probes for a launcher the formula never ships are gone; the distribution-evidence emitter carries the MCP leg as an optional absent record for the CLI-only formula; the plugin workspace, scoop-generator, installed-CLI and CI-workflow tests are re-founded on the excluded shape; the readiness suite gained the exclusion pin (the harness is in no cohort authority, no companion pin, and no cohort wheel enumeration).

## Notes

Follow-up fixed in the same campaign: the S194 descendiente action's target command key was an orphan (`config.profile.descendiente` — a group, not a leaf) and reded the operator-surface contract inside the harness identity projection; re-keyed to the live leaf `config.profile.descendiente.list` with the honesty test updated. Routed residual: five dev/packaging gate failures are the identity verifier's uncommitted-tree guard firing on concurrent peer WIP (registry/locales), not this row's sweep — they red until the peer campaigns commit.
