---
tags:
  - '#exec'
  - '#synced-history-consumption'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:5ee44bc179cbef436474d90d49a80b6572d008aec9f1bc7a24abccc6c51028eb'
step_id: 'S21'
related:
  - "[[2026-08-08-synced-history-consumption-plan]]"
  - "[[2026-08-08-synced-history-consumption-pulled-fact-consumption-census-reference]]"
---

# Make the present-or-zero carry silence loud

## Scope

- `src/cadrumo/application/calculations`
- `src/cadrumo/application/modelo/tests`

## Description

- Establish the detectable condition BEFORE writing any emission, since a
  diagnostic that guesses is worse than the silence it replaces.
- Read the existing exclusion and its written rationale rather than treating the
  silence as an oversight.
- Measure whether the rationale's own concern is already served by another
  mechanism.
- Emit for the bound-carry set, narrowed by two registry-declared axes.
- Amend every characterisation test the behaviour change touches, in the same
  commit.

## Outcome

The bound-carry silence is now an advisory, and the two narrowings that keep it
from becoming noise are both registry-declared rather than inferred.

FIRST, A CORRECTION TO MY OWN EARLIER RECORD. The Sociedades row described these
carries as resolving to zero. They do not. The relation resolves to `None`, the
resolver drops it, and the ENGINE threads the absent bound slot as a zero
downstream. The value is substituted, not produced, which matters because it
means the resolver holds the information at the exact moment it discards it.

THE EXCLUSION WAS DELIBERATE, not an oversight. The source carried a written
rationale: a non-formula relation whose target binding is declared "still
materialises an (absent/zero) slot the engine threads, which is the intended
cold-start behaviour for the cross-modelo carries (M200/M202/M100), so it is
deliberately NOT flagged here". Reversing that is a design change, and the
justification below is measured rather than argued.

THE RATIONALE'S CONCERN IS ALREADY SERVED ELSEWHERE. Cold start is handled
upstream by `_scoped_relation_source_requirements`, which removes source periods
before the operator-declared activity start. Measured directly against the loaded
Modelo 200 revision: with an activity start of 2025-01-01 the three self-carry
requirements do not survive scoping; with 2015-01-01 they do. So a genuine
first-ejercicio filer's carries never reach an advisory at all. What the blanket
silence additionally hid was the filer who DID have the obligation and whose
filing is simply absent — and there the zero reduces no liability and
over-declares.

THE TWO NARROWINGS. Membership in `requirements_by_relation`, which is built from
the SCOPED requirement set, is load-bearing rather than incidental: a scoped-out
relation still appears in `relation_values` unresolved, so testing `value is None`
alone would fire on every genuine first-ejercicio filer. And
`taxpayer_files_source` on the source modelo's dependency classification excludes
a carry the taxpayer does not file — a retención the payer files is unactionable
for this taxpayer, so advising on it would put a line they cannot act on in front
of every filer who simply had no such withholding.

Both axes are declared registry data. Neither is a heuristic, and the second one
is the same signal the clean-state gate already scopes on.

## Verification

    uv run --no-sync pytest <M200 live> <M202 sociedades live> <relation prefill mesh> -n0 -q
    20 passed in 24.99s

    uv run --no-sync pytest <seven diagnostics-sensitive modelo modules> -n0 -q
    24 passed in 86.73s

MUTATION A, suppress only the new emission. Leaves resolution, values and
provenance untouched:

    PYTHONPATH=<scratch> ... -p mutate_suppress_bound_carry -s
    MUTATION A APPLIED: holder confirmed, original=<function _absent_bound_carry_diagnostics ...>
    1 failed, 3 passed
    FAILED test_m200_self_carries_resolve_zero_with_no_prior_filing_on_live_calculate

MUTATION B, make activity-start scoping a no-op — the failure the first-ejercicio
control exists to catch:

    PYTHONPATH=<scratch> ... -p mutate_drop_activity_scoping -s
    MUTATION B APPLIED: holder confirmed, original=<function _scoped_relation_source_requirements ...>
    1 failed, 3 passed
    E   AssertionError: a first-ejercicio filer has no prior stock, so its self-carries must not be advised

The pair is orthogonal: each reds exactly one test and leaves the other passing,
so neither is carrying the other and the control is proven to bite rather than
assumed to. Both plugins resolve the holder before rebinding and re-check identity
after, so a no-op rebinding cannot print APPLIED and pass.

CALCULATIONS PACKAGE, failure-set diff against the earlier HEAD baseline:

    17 failed, 606 passed
    new versus baseline: test_unresolved_non_formula_relation_with_materialised_slot_is_not_flagged

Exactly one new failure, and it is the test that pinned the exclusion being
reversed. It was amended in the same commit rather than deleted. The other 16 are
the pre-existing `RegistryValidationError: missing binding fact` failures on
Modelo 303 and Modelo 131 surfaces.

    ruff format --check <four files>  ->  4 files already formatted
    ruff check <four files>           ->  All checks passed!
    dev.quality.types                 ->  zero occurrences of any of the four files

## Notes

CHARACTERISATION TESTS AMENDED, and each remains valid for the population it
named. `test_m200_self_carries_resolve_zero_with_no_prior_filing_on_live_calculate`
asserted an empty diagnostics tuple on the ground that a first-ejercicio filer has
no prior stock. That reasoning is still true; its persona simply declares no
activity start, so nothing can establish it IS such a filer. The zeros are
unchanged and only the silence moved. A sibling test now pins the first-ejercicio
case, where the advisory correctly does not fire. Nobody should read either
amendment as correcting an error.

The mesh test that pinned the exclusion was renamed to state what it now pins,
because its old name asserted the opposite of the behaviour and a name that lies
is worse than a deleted test. It keeps a real false-fire guard on the
`taxpayer_files_source` axis.

A PEER BROKE THE REGISTRY MID-RUN and I nearly recorded phantom findings. A
duplicate-key TOML error in the Modelo 303 export layout made an entire fallout
run fail for reasons unrelated to this change; the peer fixed it, and the re-run
showed three real failures rather than four. The first reading was discarded
rather than triaged. A tree read during a peer's mid-edit state is not evidence.

WHAT I DID NOT DO. I did not extend the advisory to carries whose source the
taxpayer does not file. Their absence still over-declares — a suffered retención
is a real credit — but the operator cannot act on the advisory this row emits, and
the honest remedy is an income-certificate value rather than a filing to capture.
That belongs to whichever row rules on reconciliation targets, not here.

I also did not measure the advisory's volume on a real populated bucket. The
narrowings are argued from registry semantics and pinned by personas; how many
lines a real multi-modelo filer would see is unmeasured, and the alert-fatigue
question is answered by construction rather than by observation.
