---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-30'
modified: '2026-08-30'
body_schema: 'body-v2'
body_hash: 'sha256:c7cb29613bafeea9d59e1405087f9cd9c5d33f003cbd73f422ec72b4653db14f'
step_id: 'S333'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Enumerate the modelo family in the registered-executor conformance matrix, which claims to cover EVERY production executor and does not: the matrix assertion compares the composed registry's definitions against its own hardcoded item list and reports the modelo edit-apply, export, verify, file, amend, discard and rename definitions as extra -- so the test whose name asserts every production registered executor runs through the shared supervisor matrix has never covered the modelo family at all. THE TELL that this is a coverage hole rather than a mismatch: no modelo parametrisation appears among the failures; every failing case is a NON-modelo param complaining the modelo ids are extra, which means the matrix holds no modelo case to run. HOW IT STAYED HIDDEN, and why the age is unknown: while production composition raised, this assertion was UNREACHABLE -- the test errored at construction and never reached its comparison, so a gate erroring looked exactly like a gate that was merely broken. Repairing composition made the assertion reachable and it immediately reported the gap. Its age is unknown but bounded below by whenever the modelo lifecycle operations were first composed into the production registry. Closing it means real request payloads for seven definitions, which is the work -- do not close it by narrowing the matrix's claim, by excluding the family from the comparison, or by adding bare entries to make the count reconcile, all of which turn a gap into a lie

## Scope

- `the registered-executor conformance matrix`
- `its item list`
- `and real request payloads for the seven modelo definitions`

## Changes

- `M` `src/cadrumo/entrypoints/tests/test_registered_executor_conformance.py`
- `verify:` `pytest -m integration -n0` -> `8 failed / 18 passed, was 13 failed / 5 passed`

## Notes

PARTIAL: the census half only.

The hardcoded `_MATRIX` tuple and its `set(definitions) == {...}` tally were
replaced by `_EXPECTATIONS`, a mapping keyed by definition id, with subjects
derived from the live production registry via `_registered_definition_ids()`.
Coverage is asserted as membership in BOTH directions -- registered
definitions with no scenario, and scenarios naming nothing registered.

THE TALLY WAS SUPPRESSING WORKING COVERAGE. Thirteen genuine conformance
proofs were failing only because a bookkeeping assertion compared a 13-item
hand list against a 20-item registry. They now run and pass. The hardcoded
census was not merely useless; it was hiding coverage that already worked.

SEVEN DEFINITIONS REMAIN HONESTLY RED, each naming itself:
`modelo.edit.apply`, `modelo.export`, `modelo.work.amend`,
`modelo.work.discard`, `modelo.work.file`, `modelo.work.rename`,
`modelo.work.verify`. Do NOT narrow the matrix to green them.

THE PAYLOADS ARE BLOCKED THREE DEEP, not one: they need (1) a filing-ready
profile baseline, (2) a work unit, and for five of the seven (3) a
calculated revision. `rename` and `discard` need two prerequisites; the
other five need three. The row implied one.

(1) is itself blocked: the readiness fixture `_READY_PROFILE_FACTS` is
package-private and duplicated in 19 files, with one cross-package import of
a private name out of another package's test module. A shared contract with
no sanctioned home, resolved 19 times by copying and once by reaching.

The gate carries `pytest.mark.integration`, so the default `-m unit` lane
reports "no tests collected (18 deselected)". The marker is ACCURATE -- 26
real supervisor executions against real encrypted storage in 135s -- so it
was deliberately left alone. The defect is that the integration lane is not
run, which is the same root cause as the dead visual-verification suite.
