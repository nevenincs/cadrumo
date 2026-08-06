---
tags:
  - '#exec'
  - '#conformance-cli'
date: '2026-07-28'
modified: '2026-07-28'
body_hash: 'sha256:cd1491c3a96ebaf171e9c9ec42080a2be93992d697fba1adc1f6f05be66c60b6'
step_id: 'S60'
related:
  - "[[2026-07-27-conformance-cli-plan]]"
---

# widen or retire the single-filing-year M303 regression that pinned only the newer revision, which is what let the older revision keep returning a zero prorrata percentage undetected

## Scope

- `src/cadrumo/domain/calculations/registry/tests`

## Description

- Located the regression and confirmed its scope really is one revision, from
  the filing year it builds its snapshot at.
- Enumerated every axis on which it differs from the gate that would replace
  it, rather than assuming the difference was only the revision.
- Disproved one of those axes by reading the two snapshot builders it appeared
  to distinguish.
- Measured the retire-versus-widen question by mutating the guarded branch on
  each revision separately and recording which gate reds.
- Carried the one surviving distinct axis into the replacement gate BEFORE
  removing anything.
- Removed the regression, leaving the reasoning at the site it vacated.
- Re-ran the mutation afterwards to confirm the replacement catches the defect
  the removed test guarded.

## Outcome

The reported scope defect is real and was confirmed at the source rather than
inherited. The regression builds its snapshot at filing year 2025 in the first
quarter, and 2025 sits inside the newer revision's window, so the earlier
revision was never exercised by it. That is exactly the shape the Step names.

The ruling is to RETIRE, and it was made on measurement rather than on the
assumption that the newer gate covers it. Reinstating the defect on the newer
revision, by returning the no-volume branch to zero, reds both the old
regression and the two-revision gate. Reinstating the same defect on the
earlier revision leaves the old regression GREEN and reds the gate on three
assertions. So the gate catches everything the old test caught and also the
case the old test structurally could not see. Widening would therefore have
left two authorities asserting one legal claim, which is the condition an
earlier Step of this campaign closed for the prorrata rounding precisely
because it is what let a defect hide.

The axes the old test uniquely carried were enumerated rather than waved away,
and one of the two turned out not to exist. It appeared to exercise a different
snapshot construction path, building through the direct builder while the gate
goes through the registry authority. Reading both showed they delegate to the
same validated snapshot builder and differ only in caching and
modelo-validation bookkeeping, so the snapshot the assertion reads is produced
by identical code and that axis was illusory.

The second axis was real and was preserved before anything was removed. The old
test probed a mid-year quarter while the gate probed only the settlement
period, and Modelo 303 genuinely does behave differently at settlement, since
the annual regularisation is due once a year there. Concluding that the
prorrata percentage cannot move between periods by reading the formula
expression would have been reasoning where a measurement was available, so the
gate now takes the period as a parameter and carries a mid-year probe on both
revisions, asserting both that the percentage is the full-deduction default and
that it equals the settlement-period answer. Only after that assertion was
green were the old test's lines removed.

The retirement was verified after the fact, not only before it. With the old
test gone, reinstating the defect on the newer revision reds four assertions on
the surviving gate, including the mid-year probe that inherited the retired
test's distinct axis. That is the direct evidence that nothing the removed test
guarded is now unguarded.

The removal left its reasoning behind. A comment stands where the test was,
recording that the regression existed, why its single-revision scope was the
defect, that it was retired rather than widened, the mutation evidence for
that, and that its mid-year axis was carried across first. A later reader
finding the gap in the file's history is answered at the place they will look.

Nothing was orphaned by the removal. The prorrata percentage casilla constant
the test used is still consumed by the regularisation source-casilla tuple, and
the imports it shared are still used by neighbouring tests; lint confirms no
dead symbol was left behind.

Verification run. Registry tree verification reports verified true over 73
modelos, 90 revisions, 15774 casillas, 1256 formulas and 568 legal references.
The replacement gate is 12 passed and the module the regression was removed
from is 30 passed, 42 together. The whole registry test tree is 3158 passed
with workers disabled. Format and lint are clean on both changed files.

## Notes

Semantic discovery was waived for this campaign by operator directive: the
vaultspec-rag index is broken and the service is stopped, so it was neither
started, restarted, reindexed nor probed. Grounding was done with ripgrep plus
whole-file reads.

Peer working state was checked before the first edit on both files and both
were clean. The index was empty at commit time and the commit named its two
paths explicitly.

One gate failure was triaged rather than absorbed or ignored, because it was
not a regression. A first serial run of the whole registry tree reported one
failure, in the loader cache-isolation module, on the assertion that the
bundled-tree disk pickle survives between two separately spawned real pytest
sessions. It passes in isolation, it sorts alphabetically ahead of both files
this Step touched so nothing changed here runs before it, and its own docstring
documents this precise failure mode: its exclusive-state assertions, that
exactly one cache file exists and that its modification time is unchanged, can
fail when a sibling session concurrently touches the shared pickle. Four peer
commits landed inside that run's window on a machine running several agents'
suites. A clean re-run of the same command reports 3158 passed with no
failures, so the red was a shared-resource transient and not an owner-surface
defect. It is recorded here rather than silently dropped, because a
one-off green re-run is weaker evidence than a reproducible failure would have
been and a later reader should know the observation existed.
