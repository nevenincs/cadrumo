---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-28'
modified: '2026-08-28'
body_schema: 'body-v2'
body_hash: 'sha256:e19bd0663068b77255da744967adf63c5730a6ac7db3f8bb2c3891f376632289'
related:
  - "[[2026-08-28-tui-architecture-computed-casilla-dormancy-export-refs-trap-audit]]"
---

# `tui-architecture` audit: `The non-negative constraint refusal surface, mapped`

## Scope

## Findings

## Recommendations

## What enforcement actually does

Casilla constraints are checked against **computed** values, not only operator
input: `formula_runtime.py:509` calls `constraints.violates(value)` after rounding
and raises `CasillaConstraintViolationError` on failure, carrying the casilla
number, label, value, formula id and the constraint's own `legal_refs` and
`source_refs`.

So a `sign = "non_negative"` casilla whose formula produces a negative does not
clamp and does not warn — it **refuses the calculation**, loudly, with its legal
basis attached. That is the right shape for a wrong-direction guard, and it means
the failure mode to look for is over-refusal of a legitimate filer, not a silent
wrong number.

## The surface

88 computed casillas are constrained `non_negative`. Of those, **21** have an
expression whose root can reach a negative value, in two structurally different
groups:

**Self-reducing (3)** — modelo 131's `modulos-rendimiento-neto-actividad`, across
three revisions:

```
subtract(modulos-rendimiento-neto-modulos,
         percent(modulos-rendimiento-neto-modulos, m131-modulos-reduccion-general))
```

This is `x - 0,05x = 0,95x` (the reduction parameter is 5 %), so it is bounded
below by zero whenever `x` is. The base carries no constraints of its own, but it
is produced by `m131_resolve_modulos_indices_generales`, a multiplicative
índices chain over `modulos-rendimiento-neto-minorado`, so its non-negativity is
structural rather than accidental. A root-operator scan flags this shape
spuriously: the subtrahend is a fraction *of the minuend*, not an independent term.

**Independent subtraction (18, across 11 distinct formulas)**

| modelo | formula |
|---|---|
| 111, 115, 117, 123 (x2), 126, 128, 136 | `modelo-<n>-resultado-ingresar` |
| 216 | `modelo-216-resultado` |
| 303 | `modelo-303-compensacion-pendiente-periodos-posteriores` |
| 309 | `modelo-309-resultado` |

These subtract genuinely independent terms, so the constraint is load-bearing
rather than decorative.

## Direction, and what is not claimed here

Every one of these guards refuses a **negative** result on a box that has no
refund mechanism of its own — a retención declaration's resultado a ingresar, an
IVA compensación carried forward. Refusing is the protective direction: it stops a
filing that asserts a repayment the form cannot express. The campaign's own rule
applies — when a guard refuses, ask which side it protects before calling it a
bug — and on the face of it these protect the correct side.

**They are not adjudicated here.** Establishing whether any of the eleven can
legitimately go negative for a real taxpayer is a per-modelo tax review against
each form's official design, not something to infer from expression shape. The
list is recorded so that review has a starting point, and no row on it is claimed
as a defect.

The one observation worth an owner's eye: the M131 chain's non-negativity depends
on an upstream base that declares no constraint of its own. It holds today
because the índices are multiplicative, but nothing in the registry says so.

No production code, registry data or test was changed by this audit.
