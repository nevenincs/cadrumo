---
tags:
  - '#exec'
  - '#registry-edition-authoring'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:7d3c540bfb6d8688fdf3b503eb7ae788ad7e8416cb45fb2dcb1ea5c9f6b4c980'
step_id: 'S03'
related:
  - "[[2026-09-09-registry-edition-authoring-plan]]"
---

# [L | opus-medium] REPLACE, never delete. Each flagged line is the anti-vacuity guard for the assertion below it; removing it leaves that assertion passing vacuously on an empty finding set forever, which manufactures more of the defect this campaign removes. The population is TWELVE GUARDS IN TEN FILES, eight of the ten owned by the export lane. Triage each: a guard on a CORPUS DEFECT we intend to repair is converted to a planted-defect fixture asserting the same invariant; a guard on a PROPERTY OF THE PUBLISHED DOCUMENT stays untouched, because nothing here repairs what AEAT wrote. The triage splits five to convert, in four files, and seven to leave, in six of the export lane's files whose populations are read from AEAT's own record-design transcriptions. The owning lane signs off BOTH kinds of decision on its files — the replacement where one is made, and the decision to leave a guard where one is not — since leaving a guard is as much a ruling on their file as replacing it. A guard of the same class found outside the twelve is converted when the owning lane asks, not silently. Proof: each replacement fixture FAILS when the planted defect is removed from it — the collected count cannot detect this class and is not sufficient evidence — and every proof names the HEAD it was measured on, because a directed removal of git operations from the dev tooling will move the baseline.

## Scope

- `dev/registry/tests`

## Changes

- `M` `dev/registry/tests/test_capability_continuity.py`
- `M` `dev/registry/tests/test_continuity_integrity.py`
- `M` `dev/registry/tests/test_casilla_id_grammar.py`
- `M` `dev/registry/tests/test_monetary_scale.py`
- `verify:` `just test-dev-tooling` isolated at `4e7e1113`, old files vs new -> `139 failed` vs `138 failed`, `3696` collected, no new failure
- `verify:` `just dev-ci` at `878b49d7` vs `21074665` -> `33 failed` both, `1199` collected

## Notes

Seven of the twelve guards were left untouched by ruling, not by omission: their populations are read
from AEAT's own record-design transcriptions, which no repair here can empty. The owning lane
confirmed all seven. Three guards beyond the twelve were also converted: capability_continuity line 99
at the owning lane's request, casilla_id_grammar line 83 as a disclosed sibling in the same test, and
monetary_scale line 126, whose non-empty guard was removed while its `<= 6` ceiling was kept and shown
to fire on seven planted modelos. dev-ci cannot reach `dev/registry` and so cannot observe this step.
The live test-dev-tooling pair is not a valid comparison because another session changed the tree
during it; the isolated same-state pair is the acceptance evidence.
