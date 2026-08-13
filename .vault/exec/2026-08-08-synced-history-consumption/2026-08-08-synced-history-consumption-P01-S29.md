---
tags:
  - '#exec'
  - '#synced-history-consumption'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:7c965c4c5e6d0239f2a08b6662903b7aa7896f037a4c40853b8c23e11cd3013b'
step_id: 'S29'
related:
  - "[[2026-08-08-synced-history-consumption-plan]]"
---

# Separate an absent observation from a malformed binding at the previous-filing raise site, closing the asymmetry S27 decided. _resolve_anchor_values raises RegistryValidationError for two different conditions - a structurally invalid binding and an observation that is simply not present - and absence is not a validation failure. Distinguish them at that site so the caller skips and reports the absent case while a malformed binding still refuses. Do NOT widen the application resolver except clause: that suppresses malformed-binding refusals along with absent observations, which is the opposite of what registry validation exists for. Five test modules assert the current refusal and all five must be amended in the same commit - two of them under adapters/outbound/aeat/sede/tests, which another executor held when this was opened, so confirm that surface is free before starting. Gate: the two-bucket differential is reused as the instrument, showing the same absent filing now produces the same behaviour whether or not an activity start is declared, a malformed binding is proved to still refuse, and a holder-confirmed out-of-repo mutation proves the new distinction bites rather than collapsing both conditions the other way

## Scope

- `src/cadrumo/domain/calculations/registry`
- `src/cadrumo/application/calculations`

## Description

- Add a module-private `_PreviousFilingObservationAbsentError`, deliberately
  NOT a `RegistryValidationError` subclass, so a broad
  `except RegistryValidationError` / `except CoreValidationError` elsewhere in
  the tree can never accidentally catch it.
- Raise it from `_resolve_anchor_values`'s two zero-match branches (the
  `per_grupo_member` "at least one" case and the singular "expected one"
  case) instead of `RegistryValidationError`. The `>1` ambiguous-match branch
  and `_observed_casilla_values`'s matched-but-missing-required-casilla
  branch keep raising `RegistryValidationError` unchanged — both are genuine
  structural defects, never absence.
- Catch the new signal in `_resolve_binding_values`'s per-anchor loop and
  return `None` immediately (the binding's existing "nothing to add,
  unsatisfied" shape) rather than letting it propagate. A malformed binding's
  `RegistryValidationError` still propagates through this same call site
  unchanged.
- Re-verify HEAD's blast radius rather than trusting the row's own (already
  eight-days-stale) five-module list: a fresh grep for the raise message
  found matches in `test_declarations_part3.py`, `test_modelo_180_registry.py`
  and `test_relation_closure.py` too, but all three call the SEPARATE
  relation-fold channel (`resolve_relation_values_from_observations` /
  `resolve_relation_values_from_filed_declarations`), which shares the exact
  message substring but is untouched by this row and out of its scope. The
  genuine blast radius, confirmed by tracing every call site: one test in
  `test_declarations_part2.py` (previous-filing, zero-match), and one CLI
  integration test in `test_app_quickfile.py` that the row's own grep missed
  entirely (a `--binding` override plus a declared `activity_start_date` —
  exactly the "raises" bucket S27 measured).
- Amend both: the declarations-adapter test now asserts the binding resolves
  to unsatisfied (absent from the result mapping) rather than raising; the
  quickfile test now asserts `calculate` succeeds (the operator's explicit
  override supplies the value) and the SAME missing Modelo 100 2024 source
  is instead caught at `verify` by the standing cross-period clean-state
  gate, which is where a missing-source finding belongs.
- Add a dedicated real-registry test module reusing S27's own two-bucket
  differential as the instrument, plus a real matched-but-incomplete-filing
  refusal, a hand-built ambiguous-multiple-match refusal, and an out-of-repo
  `monkeypatch` mutation collapsing the two exception types back into one to
  prove the malformed-still-refuses test is a real gate, not tautological.

## Outcome

An absent previous-filing observation now resolves its binding to
unsatisfied — reported through the existing `BindingPrefillReport.unsatisfied`
/ cross-period clean-state channel — identically whether or not the operator
declared an activity start, closing the asymmetry S27 decided. A malformed
binding or observation (an ambiguous multiple-match, or a found filing
missing a required source casilla) still refuses with
`RegistryValidationError` unchanged.

This also fixes a live-path defect beyond the row's own measured CLI
surface: `PreviousFilingSourceResolver.resolve()` (the calculation engine's
`previous_filing` source-mesh adapter) only ever caught storage-degradation
errors, so a genuinely absent prior filing with a declared
`activity_start_date` previously propagated an UNCAUGHT
`RegistryValidationError` out of a live `modelo work calculate` run. It now
resolves cleanly to an unsatisfied binding like every other absent source.

Verification: the new dedicated module (4 tests: the two-bucket
differential, a matched-but-incomplete refusal, an ambiguous-multiple-match
refusal, and the out-of-repo mutation proof) is green, alongside the
amended `test_declarations_part2.py` and `test_app_quickfile.py` tests and
every other previous-filing and relation test module read and re-run for
this row (`test_bindings_previous_filing.py`,
`test_cross_dependency_calculations.py`,
`test_formula_runtime_previous_filing.py`, `test_modelo_130_registry.py`,
`test_modelo_130_casilla_05_carry.py`, `test_declarations_part3.py`,
`test_modelo_180_registry.py`, `test_relation_closure.py`, the full
`test_app_quickfile.py` file, the full `entrypoints/cli/tests/test_modelo_local_observation_cli.py`
raise-adjacent test) — all green. `ruff check`, `ruff format --check`,
`ty check` are clean on every touched file; the project's wrapped
`ty + pyrefly + basedpyright` gate (`dev.quality.types`) is back to its
pre-existing 47-diagnostic baseline after fixing a real basedpyright
narrowing regression the exception split introduced (`matches[0]` after two
separate `len()` guards; fixed with `next(iter(matches))`).

The broader `application/calculations/tests/` (38 failures) and
`domain/calculations/registry/tests/` (159 failures) suites were run in
full for regression coverage; confirmed unrelated to this row by grepping
the complete logs for `_bindings_previous_filing` / `previous_filing` /
this row's own new test module name and finding zero occurrences in any
failure. The `domain/calculations/registry/tests/` count (159) is a small
drift from the 157 baseline P01.S13 recorded, consistent with ongoing
concurrent M303/registry peer commits in this shared tree over the
intervening session time, not a regression this row introduced.
`adapters/outbound/aeat/sede/tests/test_declarations_part2.py` carries six
pre-existing failures (`TestSubmittedFileObservation`, an "XML dictionary
boolean field 'LGC' contains invalid data" parse error on a redacted fixture)
confirmed unrelated by class and mechanism — a fixture/corpus parsing
concern, not previous-filing binding resolution, in a different test class
than the one this row touched.

## Notes

The row's own text ("Five test modules assert the current refusal and all
five must be amended") did not survive contact with HEAD: three of the five
named modules test the RELATION channel (a sibling mechanism sharing the
exact raise-message substring "expected one observed filing" by
coincidence, never touched by this row), and the fourth
(`test_modelo_local_observation_cli.py`) carries only a pre-existing
NEGATIVE assertion that the message is absent — already true, needing no
change. The row's count was right for the wrong reason: the real blast
radius is two modules, one of which (`test_app_quickfile.py`) the row's own
enumeration never named. Re-derived from tracing every call site rather
than trusting the message-substring grep a second time.

The "another executor held" note on `adapters/outbound/aeat/sede/tests`
(S27's stated reason this row could not land from there) was confirmed
free before starting: no uncommitted changes and no recent commits on
either declarations test module.
