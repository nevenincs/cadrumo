---
tags:
  - '#exec'
  - '#conformance-cli'
date: '2026-07-27'
modified: '2026-07-27'
body_hash: 'sha256:4d01260ae1b18430644a91be4fc558ad2576af6b8d38cd5b3a167d996cf76531'
step_id: 'S11'
related:
  - "[[2026-07-27-conformance-cli-plan]]"
---

# add structure-and-wiring tests for the classification-coherence checker grounded in the live registry tree

## Scope

- `src/cadrumo/domain/calculations/registry/tests/test_classification_coherence.py`

## Description

- Add 15 tests over the classification-coherence fold, marked unit and
  hex_domain so the default lane collects them.
- Assert live-tree invariants that hold whatever the tree says: every loaded
  modelo yields exactly one row, the fold classifies more than one modelo
  (anti-vacuity), the bundled read stamps itself unvalidated, and a divergence
  finding exists for a row if and only if that row's two axes disagree.
- Cross-check the census denominators against an independent traversal of the
  same loaded definitions, so a wrong population fails rather than passing.
- Cross-check the blocker derivation against ground truth external to the fold:
  a modelo already declaring the informative class cannot carry a blocker,
  because registry build enforces that invariant and the tree loaded.
- Prove detection power on injected definitions for all four finding kinds,
  each paired with a coherent case proving the absence of a false positive.
- Prove the forced-versus-unexplained discrimination by injecting a modelo
  whose bound casilla makes the informative class unavailable, and asserting
  its finding text differs from the unexplained case.
- Prove the axis census reads the tree in both directions: unused for a tree
  omitting the axis, exercised for one declaring it.
- Assert the fold returns findings instead of raising on a modelo carrying
  every contradiction at once.

## Outcome

Tests pass and were confirmed to actually run under the default marker
selector, which was the specific trap to avoid: this repo's default addopts
select `unit and not external_tool and not os_keychain`, and an
integration-marked module collects nothing and exits green. Collection reports
15 tests collected, and the run reports `15 passed in 2.47s`.

No test pins the tree's current census. The live-tree assertions are
if-and-only-if invariants and independently derived denominators, so a
registry edit that reconciles an axis pair or first declares a dead axis passes
rather than reddening. The detection floors live on injected definitions where
the input is controlled.

Failure power was verified by mutation rather than assumed. Four mutations were
applied to the committed fold, each run, and each reverted by restoring the
committed bytes:

- suppressing every divergence finding: 5 failed, 10 passed.
- reporting a divergence for every modelo: 2 failed, 8 passed, 5 errored.
- hardcoding the summary-axis declaration count to zero: 1 failed, 14 passed,
  killed precisely by the exercised-direction census test.
- neutering the invariant-blocker derivation to return empty: 1 failed, 14
  passed, killed by the forced-divergence discrimination test.

The third mutation is the one that matters most, because a census that always
answered "unused" would match today's registry perfectly and be worthless. The
module was then restored and confirmed byte-identical to its commit with an
empty diff, and green at 15 passed.

Surrounding gates: `ruff format` and `ruff check` clean, `ty check` all checks
passed, `pyright` 0 errors 0 warnings, and the relative-imports gate silent.
The registry test suite runs 3036 passed, 1 failed.

A sixteenth test was added after a self-review read of the fold found it would
RAISE rather than report on a divergence carrying many invariant blockers. The
test injects a modelo with 40 bound casillas, asserts the finding's detail
stays inside its bound, asserts the unrendered blockers are still counted in
the prose, and asserts the row retains every blocker. Reverting the fix fails
it, so it is a real regression gate rather than a restatement. Final run: `16
passed`.

## Notes

Two failures encountered are peer-owned, not this step's, and are recorded here
rather than absorbed or hidden.

The registry-suite failure is
`test_loader_cache_isolation.py::test_bundled_root_disk_cache_survives_across_separate_real_pytest_sessions`,
a disk-cache path collision under an xdist worker. Re-run sequentially it
passes 11 of 11 in 37 seconds. This is the documented loader-cache race class,
not a regression.

The import-hygiene gate fails two cases,
`test_test_only_underscore_reaches_do_not_exceed_test_debt_count` and
`test_test_only_underscore_reaches_are_exactly_the_named_test_debt_set`, on a
single extra worklist item: the sanitizer residual-identity test importing
`SRC_CADRUMO` from the test inventory. That import is committed at HEAD in a
peer's sanitizer commit dated the same day, the file is clean in this working
tree, and the new test module contributes nothing to the worklist. The owner
needs to update the test-debt baseline alongside that import.

An earlier `ty` diagnostic on the modelo fixture helper was fixed rather than
suppressed: the `calculation_class` parameter is now typed as the schema's
closed `CalculationClass` alias instead of bare `str`.
