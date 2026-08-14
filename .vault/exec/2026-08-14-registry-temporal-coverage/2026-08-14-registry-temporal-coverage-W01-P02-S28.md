---
tags:
  - '#exec'
  - '#registry-temporal-coverage'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:f7f3becca483c17ddabf9d19e2c63f619446ae484ccb67514f6172948e1da640'
step_id: 'S28'
related:
  - "[[2026-08-14-registry-temporal-coverage-plan]]"
---

# Replace the path-keyed unbounded authority cache backing read_parameter with fingerprint-bounded resolution through the sanctioned authority path

## Scope

- `src/cadrumo/domain/calculations/registry/_formula_runtime_ops.py`
- `src/cadrumo/domain/calculations/registry/tests/`

## Description

- Delete the path-keyed memo that resolved the default registry root's
  authority, and route both the default and the explicit root through the
  sanctioned load entry point.
- Drop the memo's now-unused imports.
- Add the regression module: the behavioural gate on the default branch under a
  verdict-certified warm regime, the branch-collapse gate, and a derived gate
  refusing any memo in the parameter-read module.
- Measure the cost the removal transfers to every parameter read, against the
  real bundled tree and across the affected test surface.

## Outcome

The defect reproduces and the fix closes it. The construction redirects only
the bundled registry root to a real copy of the shipped tree, so the default
branch — the one production takes — is the branch measured, with the real
corpus behind it. Both arms settle with one read before measuring, so the
numbers describe a settled warm caching state rather than a partially cold
first load. Each arm then edits a Modelo 100 parameter value on disk and waits
past the bundled fingerprint window, so a stale answer can only come from a
cache that never re-consults the tree at all.

Before the fix the second read returned the superseded value. After it, the
second read returns the edited value. The memo was keyed on its two path
arguments, and no argument of a registry read changes when the registry
changes, so the first call in a process pinned the compiled authority for that
process's whole life. The sanctioned load entry point re-collects the complete
registry, treaty, supplementary-orden and source-evidence fingerprints on every
call and keys its own cache on them, so an unchanged tree still resolves to the
same compiled authority while an edited tree resolves to a new one. No second
bounding mechanism was introduced; the two branches collapsed into one.

Three gates cover it. The behavioural gate reads a parameter through the
default root, edits the tree, and requires the next read to see the edit. The
branch-collapse gate requires the default root and an explicit root to report
the same value after an edit, which is precisely what diverged before. The
third is derived rather than enumerated: no callable in the parameter-read
module may carry a memo, because every argument such a memo could key on is an
argument of a registry read and none of them moves when the registry does. All
three fail against the superseded implementation, reinstated from outside the
repository.

The warm regime is constructed rather than assumed. A real green validation
verdict is persisted through the real verdict store for each tree state before
it is read, which is what puts the load in the verdict-certified regime the
defect lived in and keeps the subject of the test cache invalidation rather
than registry validation. Everything else is real: the loader, the authority,
the fingerprint collectors, the filesystem.

The removal transfers a real cost, and it is large enough to record precisely
rather than note in passing. A warm parameter read against the real bundled
tree moved from effectively free to 488 milliseconds, because every read now
performs the full fingerprint collection the sanctioned load does. Roughly 194
milliseconds of that is a source-evidence walk of 2,323 files that is not
cached at all, and most of the remainder is hashing a fingerprint tuple of
about nineteen and a half thousand entries into the authority cache key. The
affected test surface went from 43.9 to 150.8 seconds for the same 105 tests.
The reduccion-tier resolver makes up to five parameter reads per rented
property and the amortisation ledger one more, so a filing projects to about 3
seconds for one property, 23 for eight and 146 for fifty, where it was
previously bounded by the single first load.

That cost is not an argument against this change. The behaviour it replaces was
a regulated calculation reading rates from a registry compile that could be
arbitrarily old, silently, for the life of the process — the failure this
campaign exists to remove. But the cost belongs to the sanctioned path itself,
not to this row: every one of the twelve production callers of that path
already pays it once, and the two levers that would remove it — bounding the
source-evidence fingerprint the way the tree fingerprint is bounded, and keying
the authority cache on a digest of the fingerprint tuples rather than on the
tuples themselves — live outside this row's scope and would benefit every
caller. It is reported upward for enrolment rather than absorbed here.

The delta over the affected surface is zero regressions. The pre-change arm was
reconstructed on the identical working tree by reinstating the superseded
implementation at runtime from outside the repository, so the comparison
isolates this change from the peer edits landing concurrently. One failure is
common to both arms, a legal reference carrying an agent review status where
filing-grade authority requires an operator one, which is neither cache-related
nor this row's to fix. Three failures appear only in the pre-change arm, and
those are this step's own gates.

One correction was necessary during that measurement and is recorded because it
changes what an earlier reading of the evidence meant. The first version of the
reinstated implementation simplified the not-found error handling, and eight
tests that assert refusals for an unregistered year failed against it. Those
were artefacts of the reconstruction, not effects of the change. The
reinstatement was corrected to reproduce the superseded body exactly and both
arms re-run; the delta above is from the corrected run.

This step consumes no entry from the plan's deletion inventory. It replaces a
caching strategy rather than removing a surface. The path-keyed memo is gone
outright, with no fallback, alias or compatibility path retained, and the
public reading function keeps its signature and its behaviour for every caller.

## Notes

The behavioural gates reach the default branch by redirecting where the bundled
registry root points, for the duration of the test only. That is the sole way
to exercise the branch that carried the defect without editing the shipped
registry tree, which is both shared with concurrent executors and partly owned
by another campaign. The redirection moves a resource location; it does not
stand in for any part of the code under test.

Certifying a verdict for a synthetic tree that would not pass full registry
validation is deliberate and is what makes the regime warm. It is worth being
explicit that this means the gates do not assert anything about validation, only
about invalidation.

The cost finding is the one thing in this row that a reader should not take as
settled. It is measured, it is large, and the remedy is outside this row.
