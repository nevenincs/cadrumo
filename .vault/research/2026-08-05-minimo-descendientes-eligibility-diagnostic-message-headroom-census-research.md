---
tags:
  - '#research'
  - '#minimo-descendientes-eligibility'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:fdef0dfa1c6d94f16a35902160bd979396f964324fdd0e2b2ac22a78100a0e7d'
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

This is a QUALITY gap, not a correctness one, and the distinction is load-bearing
rather than a softening. Before `4277ecc160` an over-long advisory raised and stopped
the filing. After it, an over-long advisory silently loses its tail. An operator reads
a truncated explanation instead of a complete one; nothing is mis-declared.

That inversion is exactly why the truncating type and the headroom gate are both
correct and neither is redundant: the type makes the severe failure impossible, and the
gate keeps truncation a floor rather than a licence.

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
