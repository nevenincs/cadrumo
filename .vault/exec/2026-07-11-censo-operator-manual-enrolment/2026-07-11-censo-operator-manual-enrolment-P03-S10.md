---
tags:
  - '#exec'
  - '#censo-operator-manual-enrolment'
date: '2026-07-11'
modified: '2026-07-11'
step_id: 'S10'
related:
  - "[[2026-07-11-censo-operator-manual-enrolment-plan]]"
---

# gate battery + g313 supersession reconciliation

## Scope

Run the S10 gate battery over the censo Option-4 retirement surface and record the
honest reconciliation of the superseded `2026-07-10-censo-g313-launcher-fix` plan.
No completion is fabricated: the g313 live-scrape steps that were never executed
stay unchecked.

## Description

- Confirmed the retirement's own surface is green after the P01 deletions and the
  consumer sweep landed: full-tree `pytest --collect-only` is clean (12743
  collected, 0 errors) — no dangling imports of the deleted `_profile_censo`,
  `_censo_live`, or `_censo` modules.
- Verified `dev/docs/cli_reference.py` no longer references the retired
  `_profile_censo_payloads`, so the CLI-reference generator matches the deleted
  verb family.
- Ran the S10 conformance battery: documented-command conformance, rule-surface
  conformance, and CLI-reference conformance all pass (5 passed).

## Outcome

Censo-surface gates GREEN:

- `pytest --collect-only -q src/aeat`: 12743 collected, 0 errors.
- `test_documented_command_conformance.py` + `test_rule_surface_conformance.py` +
  `dev/docs/tests/test_cli_reference_conformance.py`: 5 passed. The retired
  `config profile censo pull/compare/apply/show` verbs no longer resolve, are no
  longer cited by any shipped rule/skill/how-to, and the generated CLI reference
  drops them cleanly.

g313 supersession reconciliation (honest, nothing fabricated):

- `2026-07-10-censo-g313-launcher-fix-plan` is superseded by the accepted ADR
  `2026-07-11-censo-operator-manual-enrolment`; its plan body already carries the
  `CLOSED BY SUPERSESSION 2026-07-11` block and its live-scrape steps `S02`-`S07`
  remain UNCHECKED — they were the Option-1 live-scrape approach the accepted
  ADR discards, so they are retired-not-implemented, never marked done. The old
  ADR carries its `superseded` banner.
- The Option-4 retirement itself lands under this feature's `P01`-`P04` (scrape
  chain deleted, verb family retired, locale subtree removed, agent skills and the
  `aeat-cli-pull-and-file-standard` rule re-authored onto the operator-manual
  path, calendar `enrolment_unverified` posture pinned by regression, the
  producerless censo snapshot substrate deleted).

Residual gate drift at the time of the first pass (2026-07-11) was NOT the censo
surface (owner-distinguished per `full-tree-gate-must-distinguish-owner`):
`aeat.locales scaffold --check` reported missing `cli.help.missing_parameter` /
`cli.help.not_valid_integer` / `cli.help.usage_prefix`, and `apidocs scaffold
--check` reported `aeat.domain.calculations.registry` / `aeat.domain.iva` /
`aeat.domain.transactions` drift. None referenced censo; both traced to
unrelated concurrent peer campaigns.

### Re-run (2026-07-14): full gate battery, censo-scoped closure

The Steps this record's first pass left open for a peer (`P02.S03`, `P02.S05`,
`P02.S07`) were re-verified and found already structurally complete at current
HEAD — no production edit was needed; each closes with its own exec record
(`P02-S03.md`, `P02-S05.md`, `P02-S07.md`). Re-ran the full gate battery against
current HEAD (with `CADRUMO_LOCAL_STORAGE_ROOT` redirected off a stale local
`var/aeat.db` former-product-state artefact, unrelated to censo):

- `pytest --collect-only -q src/cadrumo`: 12912/15669 collected (2757
  deselected), 0 collection errors.
- `test_documented_command_conformance.py` + `test_rule_surface_conformance.py`
  + `dev/docs/tests/test_cli_reference_conformance.py`: 5 passed.
- `python -m dev.docs.apidocs scaffold --check`: "Stub tree is conformant. No
  drift detected." — the prior peer-owned registry/iva/transactions drift has
  since cleared.
- `python -m cadrumo.locales scaffold --check`: fails on one extra key,
  `cli.app.modelo.work.verify_already_verified_refused`, across all four
  catalogues. This does not reference censo and traces to an unrelated peer
  campaign's locale churn — owner-distinguished, not fixed here.
- `vaultspec-core vault check features --feature censo-operator-manual-enrolment`:
  clean.

The two P01-surface review findings noted below were independently confirmed
resolved: no code path emits the "once the live AEAT censo read is available…"
advisory string, and no production module reads a `CensoSnapshot` outside test
fixtures (P04.S11's re-seating onto operator-declared `vivienda_office` m² and
substrate deletion fully closed both).

## Notes

The two review findings originally flagged here for the P01 retirement surface
are now confirmed CLOSED: (1) no surviving advisory string contradicts the
Option-4 ADR; (2) no surviving production reader of `CensoSnapshot` exists — the
substrate was deleted under `P04.S11`.

Step `S10` closes with one residual, explicitly non-blocking, non-censo gate
item: the `verify_already_verified_refused` locale-key drift, owned by an
unrelated concurrent peer campaign per `full-tree-gate-must-distinguish-owner`.
Every other named gate in the plan's Verification section is green.
