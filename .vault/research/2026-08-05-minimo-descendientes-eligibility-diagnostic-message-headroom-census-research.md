---
tags:
  - '#research'
  - '#minimo-descendientes-eligibility'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:d9e4d030689165c6877260b85438542fcb44ce771b3823551fa71eee2622c78b'
related: []
---

## Why this exists

Commit `4277ecc160` made `CalculationSourceDiagnostic.message` truncate at 512
characters rather than raise, killing a class of failure in which a NON-blocking
advisory became a blocking one and stopped a filing at exactly the moment the
advisory had something to say.

That closed the correctness half. This census exists because the campaign could not
honestly claim to have closed the quality half, and the reason is a specific trap: the
Step found two over-long advisories, fixed them, and gated exactly those two. A set
derived from the work cannot support a completeness claim about the tree.

## Method

An AST sweep over every `.py` under `src/cadrumo`, excluding tests, collecting every
keyword `message=` argument to a `CalculationSourceDiagnostic` or
`CalculationSourceIssue` construction. Each site was classified on whether its message
can GROW with data -- an f-string interpolation, a `.join(...)`, or a `.format(...)` --
rather than on its length, because a constant message is not in the class however long
it is.

The headroom-gate cross-reference reads
`application/aggregation/tests/test_diagnostic_message_bound.py` for factory names.

## Findings

**68 construction sites** carry a `message=` argument.

**Zero have a static floor above the cap.** The two sites that were previously
unbuildable at any input -- a 528-character floor against a 512 cap -- are fixed.

**31 are constant-length and therefore not in the class.** The two thinnest messages in
the tree (487 and 475 characters, both in `_calculate_input.py`, the DT 12ª
window-unverified advisory and the maternidad cotizaciones-ceiling advisory) are pure
static prose with no interpolation at all. They are close to the cap and will stay
exactly that close forever. They need no gate.

**37 sites are growable.** These are the class.

**35 of the 37 have no headroom assertion.** The gate names two.

## Where the ungated growable sites live

Roughly seven are in `application/modelo/_minimo_descendientes_advisory.py`, which is
this campaign's own surface and is owned by Step `S49`.

The remaining ~28 are outside this campaign entirely:
`_prior_payment_advisory.py`, `_prorrata_regularizacion_advisory.py`,
`_official_box_advisory.py`, `_settlement_grade_advisory.py`,
`_bienes_inversion_advisory.py`, `_calculation_source_staging.py`,
`aggregation/_source_mesh.py`, `aggregation/_modelo_bindings.py` (six sites in one
family of `resolve` methods), `aggregation/_oss_ioss.py`,
`aggregation/_retencion_rate_advisory.py`, `calculations/_relation_prefill.py`, and
`calculations/_iva_compensation_annual_partition.py`.

## Severity, stated honestly

**Corrected after measurement.** This section originally filed the whole class as a
quality gap rather than a correctness one. That holds for most of the population and
does NOT hold for the two advisories now known to truncate in production.

The general case is a quality gap, and the distinction is load-bearing rather than a
softening. Before `4277ecc160` an over-long advisory raised and stopped the filing.
After it, an over-long advisory silently loses its tail. That inversion is why the
truncating type and the headroom gate are both correct and neither redundant: the type
makes the severe failure impossible, and the gate keeps truncation a floor rather than
a licence.

But an advisory whose PURPOSE is telling an operator how to fix an under-declaration,
truncated so that the remedy is the part cut, is not a degraded message. The advisory
still fires -- nothing is silent -- and the operator is left knowing something is wrong
with no instruction for fixing it. That sits closer to correctness than to polish, and
filing it under quality under-ranked it.

## Two advisories are truncating in production today

Measured against the real factories, not reconstructions:

| advisory | rendered | state |
| --- | --- | --- |
| `dependencia_suppressed` (l.586) | 521 | **over cap, eliding now** |
| `prorrata_inferred` (l.239) | 516 | **over cap, eliding now** |

The trigger is a late-qualifying subset of a large household. **Four children is enough**
to reach 498 and 493 respectively -- not an extreme-tail case requiring an implausible
family.

## The static-floor ranking in this document was inverted

The floor table ranks by FIXED PROSE, and the risk is not in the fixed prose. It put
`count_desync` (floor 406) at the top and `dependencia_suppressed` (floor 333) last.
Measured, that is exactly backwards: `count_desync` does not use the fact-path renderer
at all and is the SAFEST growable advisory in the module, while `dependencia_suppressed`
is the one already over the cap.

A static floor is a lower bound on a message, not a ranking of risk. Ranking by it
substitutes the part that cannot grow for the part that can.

## The interpolation delta is ~123, and shaped differently than assumed

The working assumption was ~100 characters, extrapolated from two sites. Measured: 96 at
a household of four, 101 at a million all-qualifying, and **123** at a late-qualifying
household. The renderer emits enumerate positions, so length grows with index DIGITS as
well as with the remainder, and the true worst case is a late-qualifying subset of a
large household rather than the all-qualify shape.

The sibling gate's `_ids(1_000_000)` convention models the weaker case and under-measures
this module by ~22 characters -- a gate understating headroom in the safe-looking
direction, inside the instrument built to measure headroom.

**Of the 96 characters at four children, 78 are the `renta_family.descendiente.` prefix
repeated three times.** The cost is in the rendering ceremony, not the message.
Compressing a shared prefix would return ~60 characters to every advisory in the module
at once with no prose lost -- larger and cheaper than per-advisory trimming, subject to
checking whether anything downstream parses that string.

## What this does not claim

It does not claim the ~28 out-of-scope sites are near their caps. Their static floors
were measured; their RENDERED worst cases were not, because doing so requires
constructing a realistic profile per factory and those factories belong to domains this
campaign has no grounding in. A follow-up should measure before acting.

It also does not claim 37 is exact. The sweep detects growth through f-strings, joins,
and format calls; a message assembled through a helper that returns a string would read
as constant. The number is a floor on the growable population, not a census of it.

## Instrument note

The first cross-reference pass reported the gate covering zero sites, because the
ripgrep glob `*/tests/*` does not match nested test directories on this tree while
`**/tests/**` does. The corrected pass found the two. A gate-coverage number produced
by a filter that silently matches nothing reads identically to a real finding of zero
coverage, which is the failure mode worth recording alongside the result.
