---
tags:
  - '#exec'
  - '#synced-history-consumption'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:2816843a2cfd0869547105b75876b667f71d9c198d0f224e0fe98dcd4ad97f07'
step_id: 'S10'
related:
  - "[[2026-08-08-synced-history-consumption-plan]]"
  - "[[2026-08-08-synced-history-consumption-pulled-fact-consumption-census-reference]]"
---

# Give the previous-filing channel a diagnostic

## Scope

- `src/cadrumo/application/calculations`
- `src/cadrumo/application/calculations/tests`

## Description

- Search by meaning for an existing idiom before inventing one, and adopt the
  `withholding` resolver's shape: materialise the value, then name the gap.
- Add a typed `UnsatisfiedBinding` carrier to the prefill report, derived from the
  revision's own declared bindings rather than from the requirement index, so a
  binding whose requirement produced no row at all is reported rather than being
  invisible for the same reason it failed.
- Report on BOTH return paths, including the empty-store early return that used to
  return in silence and is the consequential one.
- Project the unsatisfied set onto the resolver's diagnostics channel and its
  unresolved-binding-ids channel.
- Gate on the property with a positive control, and prove both halves bite with
  two orthogonal out-of-repo mutations.

## Outcome

The previous-filing channel now reports. `PreviousFilingSourceResolver` emits one
`unresolved_binding` diagnostic per declared `previous_filing` binding the local
store could not satisfy, naming the binding, the source modelo, the source filing
year and the source periods, and it populates `unresolved_binding_ids` so the
merge propagates the gap rather than dropping it.

The message states the direction, because that is the part an operator cannot
infer: every previous-filing carry reduces the amount owed, so an absent one
over-declares. Bindings another authority owns stay out of it —
`excluded_binding_ids`, the IVA wallet's compensación slot being the standing
case — because reporting those would be this resolver claiming a gap it does not
own.

The shape is not invented. The `withholding` resolver already materialises an
explicit zero and emits a `source_issue` naming its source when its store is
empty. This is that established pattern applied to a family that never adopted it.

The empty-store path is the one that mattered. `resolve_bindings_from_local_store`
returned an empty report immediately when no observations existed, which is
precisely the freshly-onboarded profile this campaign is about, and it is now the
path that reports every declared carry.

That the 17 bindings with no diagnostic were the same 17 the registry declares no
dependency treatment for is not a coincidence: undeclared treatment and
undetectable failure are one hole with two faces, which is why this fixes the
channel rather than patching a symptom.

## Verification

    uv run --no-sync pytest src/cadrumo/application/calculations/tests/test_previous_filing_unsatisfied_diagnostic.py -n0 -q
    2 passed in 58.31s

The emission gate asserts the PROPERTY — every declared previous-filing binding on
the loaded revision is named by some diagnostic — with the declared set read off
the revision rather than hardcoded, so a registry rename cannot make it pass
vacuously and no count is pinned.

MUTATION ONE, suppression. It leaves resolution, binding values and provenance
untouched and empties only the reporting channel, restoring the exact pre-fix
behaviour rather than breaking the resolver:

    PYTHONPATH=<scratch> uv run --no-sync pytest <this module> -n0 -q -p mutate_suppress_carry_diagnostic -s
    MUTATION APPLIED: holder confirmed on cadrumo.application.calculations._multi_year.PreviousFilingSourceResolver.resolve
    1 failed, 1 passed
    E   AssertionError: every declared previous-filing binding must be named when unsatisfiable; missing frozenset({'modelo-130-pagos-fraccionados-anteriores', 'irpf.previous_year_economic_activity_net_income', 'modelo-130-resultados-negativos-anteriores'})

MUTATION TWO, emit-always. It names every declared binding whether satisfied or
not, which is the failure the positive control exists to catch:

    PYTHONPATH=<scratch> uv run --no-sync pytest <this module> -n0 -q -p mutate_emit_always -s
    MUTATION APPLIED (emit-always): holder confirmed on PreviousFilingSourceResolver.resolve
    1 failed, 1 passed
    E   AssertionError: a satisfied carry must NOT be named; the resolver would otherwise be reporting unconditionally

The two are orthogonal: each reds exactly one test and leaves the other passing.
Suppression cannot red the control and emit-always cannot red the emission gate,
so neither test is carrying the other. Both plugins read the function out of the
class `__dict__` and raise if it is absent, then re-read the attribute after
rebinding and raise if it still resolves to the original, so a no-op rebinding
cannot print APPLIED and pass.

WHOLE-PACKAGE OWNERSHIP TRIAGE. The calculations package is red on peer surfaces,
so the failure sets were diffed rather than eyeballed. With HEAD production bytes
in place: 17 failed, 606 passed. With this change: 16 failed, 607 passed. The set
difference in each direction:

    fixed by this change:  test_every_unsatisfiable_previous_filing_binding_is_named
    broken by this change: (empty)

So this change breaks nothing, and the only delta is its own gate — red against
HEAD, green with the fix, which is the before-and-after property demonstrated by
measurement rather than asserted by commit ordering. The 16 pre-existing failures
are `RegistryValidationError: missing binding fact` on Modelo 303 and Modelo 131
surfaces and are untouched by this row.

The six tests across the tree that assert `source_diagnostics == ()` were run
explicitly, since a new diagnostic is exactly what would break them: 21 passed.

    uv run --no-sync ruff format --check <three files>   ->  3 files already formatted
    uv run --no-sync ruff check <three files>            ->  All checks passed!
    uv run --no-sync python -m dev.quality.types         ->  zero occurrences of any of the three files

## Notes

MECHANISM TWO IS NOT DONE, and this row does not fully satisfy its own gate. The
gate was written to cover both silent mechanisms. This implements the
previous-filing one: an unsatisfiable binding that resolved to nothing. It does
NOT implement the second one the Sociedades row uncovered — a `relation_prefill`
slot that binds a casilla directly and takes present-or-zero semantics, which
resolves to a real zero and is silent for a different reason. Three Modelo 200
carries behave that way.

What the standing goal still asks that this excludes: an operator calculating a
Modelo 200 with no prior filing still receives a zero opening BIN stock, no
diagnostic, and no way to distinguish a genuine first-ejercicio company from one
whose prior return exists at AEAT and cannot be fetched. That is opened as its own
row rather than left inside this one as `P01.S21`, because it is a different change — it must
distinguish "zero because absent" from "zero because declared zero", and it must
amend `test_m200_self_carries_resolve_zero_with_no_prior_filing_on_live_calculate`
in the same commit, since that test asserts the silent zero and will red the
moment it becomes loud.

I OPENED A REVERT WINDOW, and should disclose it. Establishing ownership of the
16 failures required running the package against HEAD, so the two production files
were copied aside and HEAD bytes written in their place for roughly three minutes
while the baseline ran. That is the sanctioned comparison technique, and in this
tree it is also an exposure: a peer's bare whole-index commit landing inside that
window would have captured the reverted files and silently undone the change. It
did not — HEAD carries the implementation — but the window was real and the
technique should be understood to carry it.

SWEPT, seventh occurrence. All three files were taken into HEAD by
`fa7c440e9f`, subject "feat(cadrumo): land the in-flight source work", before they
could be committed under their own subject. HEAD content was verified to carry the
implementation, and one follow-up commit landed the formatting the sweep captured
mid-edit. This record is the attribution.
