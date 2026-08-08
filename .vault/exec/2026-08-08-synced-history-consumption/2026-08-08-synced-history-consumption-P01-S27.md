---
tags:
  - '#exec'
  - '#synced-history-consumption'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:9e833fb89f3a19d0e701e28d3250d9e1fdd6c89416b9e29cb757e3da3df18f22'
step_id: 'S27'
related:
  - "[[2026-08-08-synced-history-consumption-plan]]"
  - "[[2026-08-08-synced-history-consumption-pulled-fact-consumption-census-reference]]"
---

# Decide whether an unsatisfied previous-filing carry should refuse or advise

## Scope

- `src/cadrumo/domain/calculations/registry`
- `src/cadrumo/application/calculations`

## Description

- Read the raise site and establish exactly which condition triggers it, rather
  than treating the asymmetry as an error-handling accident.
- Establish which of the two behaviours is correct before changing either.
- Measure the blast radius of the change before making it.
- Record the decision and open the implementing row where the change cannot land
  from here.

## Outcome

DECISION: ADVISE is correct. The refusal is over-broad and the advisory path is not
under-strict.

WHAT ACTUALLY TRIGGERS THE RAISE, measured at the site rather than inferred.
`_resolve_binding_values` walks the selector's required period anchors. An anchor
strictly before the declared activity start is scoped out; if EVERY anchor is
scoped out the function returns zeros and nothing raises. An anchor in scope goes
to `_resolve_anchor_values`, which raises `RegistryValidationError` when no
matching observation exists.

So the raise fires precisely when the taxpayer HAD the obligation and the filing is
absent. It is not firing on a legitimate no-obligation absence — that case is
already handled. The condition is a genuine gap.

WHY ADVISE IS NEVERTHELESS CORRECT, and the argument is consistency rather than
leniency. The RELATION channel faces the identical condition — obligation existed,
source filing absent — and advises: it resolves the slot to nothing, the engine
threads a zero, and a diagnostic names the gap. The `previous_filing` channel
raises. Same condition, two contracts, on two mechanisms the taxonomy requires to
agree. One-mechanism-per-calculation-type is violated by the divergence itself,
and the relation channel's behaviour is the shipped, tested and
taxonomy-consistent one.

Three further reasons, none of which is "advising is easier to reach":

The taxpayer is legally obliged to present a declaration even with an incomplete
history, so a hard stop makes a required filing impossible through the
application. That is the same ground on which refusal was rejected as the remedy
for a ledger-derived casilla.

The value is recoverable by hand through a binding override, so refusal denies a
filing the operator could complete.

And the error the absence produces is an OVER-declaration, which harms the
taxpayer rather than the treasury. Refusing on over-declaration risk would be
stricter than anything else in the tree, where the entire apparatus watches the
under-declaration direction.

WHERE THE FIX BELONGS, and it is not the resolver's catch. Widening
`PreviousFilingSourceResolver` to catch `RegistryValidationError` would convert
every registry validation failure into an advisory, including malformed selectors
that must still refuse. The defect is upstream: `_resolve_anchor_values` raises ONE
error type for TWO conditions — a structurally invalid binding and an observation
that is simply not present. Absence is not a validation failure, and the fix is to
distinguish them at that site so the caller can skip-and-report the absent case
while a malformed binding still raises.

## Verification

    rg -n "expected one observed filing" -B 12 src/cadrumo/domain/calculations/registry/_bindings_previous_filing.py
    sed -n '225,260p' <same file>

The trigger condition is read off the anchor loop and the two return paths
(`_zero_values_for_scoped_out_binding` versus falling through to the raising
resolver), so "fires only when the obligation existed" is a property of the code
rather than an inference from the message text.

BLAST RADIUS, measured before deciding to implement:

    rg -ln "expected one observed filing" src/cadrumo --glob '*test*.py'
    adapters/outbound/aeat/sede/tests/test_declarations_part2.py
    adapters/outbound/aeat/sede/tests/test_declarations_part3.py
    entrypoints/cli/tests/test_modelo_local_observation_cli.py
    domain/calculations/registry/tests/test_modelo_180_registry.py
    domain/calculations/registry/tests/test_relation_closure.py

Five modules assert the refusal, so the change cannot land without amending all
five in the same commit.

No production file was changed by this row.

## Notes

THE IMPLEMENTATION CANNOT LAND FROM HERE, and the reason is a surface boundary
rather than difficulty. Two of the five dependent modules are
`adapters/outbound/aeat/sede/tests`, which another executor holds and which I am
directed to stay out of. Amending them is a precondition of the change, so the
implementation is opened as `P01.S29` with the conflict named rather than started
and abandoned half-done, or worse, landed by editing a surface someone else is
mid-edit in.

What the standing goal still asks that this row excludes: the asymmetry is
DECIDED but not CLOSED. Until the implementing row lands, the same absent filing
still produces a refusal or an advisory according to whether an unrelated profile
fact is present, and my earlier claim that the previous-filing channel reports
remains true only on the branch where the application layer short-circuits before
the domain resolver is reached.

THE TWO-BUCKET DIFFERENTIAL IS THE INSTRUMENT the implementing row must reuse. It
is what found this — two buckets identical but for `censo.activity_start_date`,
producing three diagnostics on one and a `RegistryValidationError` on the other —
and a fix asserted without it can show the behaviours agree without showing the
asymmetry closed rather than merely relocated.

I did NOT pick the behaviour that was easier to reach. Widening the application
resolver's `except` clause would have made the two paths agree in an afternoon and
would have been wrong: it suppresses malformed-binding refusals along with absent
observations, which is the opposite of what the registry validation exists for.
