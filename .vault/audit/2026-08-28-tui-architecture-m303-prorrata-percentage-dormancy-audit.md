---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-28'
modified: '2026-08-28'
body_schema: 'body-v2'
body_hash: 'sha256:bb5a3577fbc77679164fb1242ecfd23214a6ba66df9de7dab5d5f09a2b8b650a'
related:
  - "[[2026-08-28-tui-architecture-rounding-discipline-sweep-audit]]"
---

# `tui-architecture` audit: `The M303 prorrata percentage is a declared-dormant computation; the tax effect runs through box 44`

## Scope

## Findings

## Recommendations

## What was checked

Every `divide` node in the registry: 37 across all modelos. Division by zero
raises `RegistryValidationError` with a translated message, so the failure is
loud, never a silent wrong quotient.

Six nodes -- the same M303 prorrata formula across six revisions -- looked
unguarded to a probe that recognised only `max`/`clamp` floors. They are guarded,
by an upstream conditional:

```
if_then_else(
  greater_than(iva.prorrata-volumen-total, <dispatch>),
  divide(multiply(iva.prorrata-volumen-con-derecho, 100), iva.prorrata-volumen-total),
  100
)
```

That is a probe limitation, not a defect: a guard need not sit on the denominator.
Recording it so the next reader does not re-flag the same six rows.

## The prorrata chain is coherent, and the direction is watched

The `else` branch defaults the percentage to **100**, full deduction. For the
majority of filers, who apply no prorrata, 100 is the neutral and correct value.
The exposure would be a prorrata filer leaving the two optional manual volume
boxes blank and silently receiving full deduction -- an under-declaration.

That direction has a watch. The revision declares

> `implies_nonzero(["iva.prorrata-volumen-total", "44"])`

grounded on LIVA arts. 104 and 105: a declared prorrata volume must produce a
non-zero box 44. This is one of the few predicates in the registry and it sits
exactly where the silent path would be.

And the tax effect itself does reach the return. Casilla **44**, regularización
por prorrata, is manual, exported at `m303-2025.dp30301.f077`, and consumed by
`modelo-303-iva-cuota-deducible-total`. Prorrata restricts deduction through the
operator-entered regularisation, which mirrors how the official form works.

## The percentage itself is dormant, and says so

`iva.prorrata-porcentaje` is `computed`, and:

- consumed by **no formula in any of the six M303 revisions**;
- carries **no `export_refs`**, with `export_exemption_reason =
  "record_block_not_modelled"`;
- is present in the completeness manifest.

So it is computed and reaches nothing. That is a dormant computation of the same
family as the recorded RIC 80 % finding -- with one important difference: this one
is **declared**. The exemption reason states plainly that the export record block
is not modelled. It is a known gap wearing a label, not a silent one, and it
should be read as such.

## Correction to this campaign's own previous commit

The `integer-ceiling` precondition gate shipped in the preceding commit guards
exactly this casilla. Its message argued that a violation would round a negative
result toward zero and "shorten what the taxpayer gets back".

**That consequence cannot occur today**, because the value reaches no formula and
no export. The gate remains correct to hold -- the precondition is declared
mandatory by `apply_rounding`'s own docstring, and the value would matter the
moment the record block is modelled or a consumer is added -- but its practical
reach at HEAD is narrower than that message implied, and the message should not
be read as evidence of live exposure.

Stated here rather than left standing, because a gate whose stated stakes exceed
its actual reach is the kind of claim that later gets quoted as proof of
something it never established.

No production code, registry data or test was changed by this audit.
