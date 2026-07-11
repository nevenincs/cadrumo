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

Residual gate drift is NOT the censo surface (owner-distinguished per
`full-tree-gate-must-distinguish-owner`): `aeat.locales scaffold --check` reports
missing `cli.help.missing_parameter` / `cli.help.not_valid_integer` /
`cli.help.usage_prefix`, and `apidocs scaffold --check` reports
`aeat.domain.calculations.registry` / `aeat.domain.iva` /
`aeat.domain.transactions` drift. None reference censo; all trace to unrelated
concurrent peer campaigns (locale WIP and module churn) and are theirs to close.

## Notes

Two review findings on the P01 retirement surface, flagged for the owning
committer (not resolved here): (1) an advisory string reading "once the live AEAT
censo read is available…" contradicts the Option-4 ADR (no live read ships absent a
new ADR); (2) any surviving read-only afectacion projection that reads a
`CensoSnapshot` is a dormant surface now that the capture path is deleted — the
ADR's delete-not-stub stance wants it removed or re-seated on operator-entered
facts (P04.S11 already re-seats `bound_raw_afectacion_ratio` onto operator-declared
`vivienda_office` m2; confirm no snapshot-reading path survives).

Step `S10` is left UNCHECKED: this record satisfies the reconciliation half of the
step, but the full gate battery cannot be declared clean while the unrelated
peer-owned locale/apidocs drift is present, and the plan's `S03`/`S05`/`S07`
tracking is managed by the peer executing this plan. Formal step closure is left to
the plan owner once the peer drift clears; nothing here is marked done that is not.
