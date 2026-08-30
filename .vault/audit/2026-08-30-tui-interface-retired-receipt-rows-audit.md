---
tags:
  - '#audit'
  - '#tui-interface'
date: '2026-08-30'
modified: '2026-08-30'
body_schema: 'body-v2'
body_hash: 'sha256:7e62ac303b43979859f371abe1859f650289b7cd228b55acfe011697e7d73eed'
related:
  - "[[2026-08-11-tui-interface-plan]]"
---

# `tui-interface` audit: `Open rows whose deliverables an accepted decision retired`

## Scope

## Findings

## Recommendations

Three rows of the tui-interface plan sit open while carrying execution records
that cite artefacts no longer in the tree. Reading the plan alone cannot tell
them apart from unstarted work, and reading the records alone asserts
deliverables that were later removed on purpose.

### The C1 receipt rows describe a mechanism an accepted decision retired

**Pathway:** plan rows `W01.P01.S01` and `W05.P10.S38`, tui-interface plan.

Both rows record a "C1 governance fact" as a receipt, and both execution
records list an added `.vault/reference/` receipt artefact. Neither artefact
exists. Commit `51023bdad2` (2026-08-30 10:00), `refactor(quality): retire the
modelo workspace exit receipt family`, states the position plainly: the
accepted interface decision "retired the C1-C5 exit receipt schemas, their five
validators and the shared discriminated proof type outright -- not renamed, not
relocated", and `dev/quality/modelo_workspace_receipts.py` together with its
test was deleted. Only a stale `__pycache__/modelo_workspace_receipts.pyc`
remains, which is why an import of that module still looks plausible from a
directory listing.

What is lost is the distinction between three states that wear the same open
checkbox: work not started, work done and unmarked, and work whose SUBJECT a
later decision retired. These two rows are the third kind. Closing them would
assert a receipt exists; leaving them silent invites a future agent to rebuild
a mechanism the decision removed, and the retirement commit names exactly that
hazard -- its test suite "passed even when the rest of the tree could not
import, because the module depended on nothing in the product".

**Remediation.** Adjudicate both rows as superseded by the accepted interface
decision, citing `51023bdad2`, rather than completing or deleting them. A
superseded row records that the question was answered elsewhere; a deleted row
records nothing and a completed row lies.

### The action-denominator row's subject survives and is green

**Pathway:** plan row `W01.P01.S37`, tui-interface plan.

This row is NOT of the same kind and must not be swept with the other two. The
same retirement commit states "the action denominator survives untouched: it
asserts implementation shape, which the same decision explicitly retained".
Measured at HEAD: `dev/quality/modelo_workspace_action_denominator.py` exists,
`build_modelo_workspace_action_denominator()` and
`validate_modelo_workspace_action_denominator()` both resolve, the validator
returns zero violations, and `dev/tests/test_modelo_workspace_action_denominator.py`
holds it as a standing gate at 9 passing tests. The row's substance -- keep the
denominator as a standing conformance gate -- is satisfied.

Its execution record cites a deleted 1,132-line reference document, and that
deletion is defensible on inspection: the artefact was a SNAPSHOT of generated
data, reproducible by calling the builder, so removing it destroyed no
information the gate does not regenerate.

**Remediation.** Close the row on the standing gate, and correct its execution
record so it does not assert a file that is gone.

### A commit subject announced additive work and removed six artefacts

**Pathway:** commit `280ec80a67` (2026-08-28 12:45),
`vault(semantic-consolidation): open the research, decision and plan`.

The subject describes opening research, a decision and a plan for the
semantic-consolidation feature. The commit also deleted six `.vault/reference/`
documents belonging to three OTHER features -- tui-interface, tui-architecture
and tui-registry-api-gate -- totalling roughly 2,500 lines, and amended four
TUI ADRs by roughly 241 lines in total.

The substance is defensible: the amendments carry the decisions forward and the
largest deleted artefact was regenerable. What is lost is discoverability. A
reader auditing why a tui-interface artefact vanished has no reason to open a
commit whose subject names a different feature and announces only additive
work, and the deletions preceded the receipt-family retirement by two days, so
the obvious later explanation does not actually cover them.

**Remediation.** None on the tree; the outcome is sound. Recorded because the
cost is paid at read time by whoever next asks where these artefacts went, and
because a subject that omits cross-feature deletions is the same class as a
reformat commit carrying a semantic change.
