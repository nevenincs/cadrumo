---
tags:
  - '#audit'
  - '#calculation-correctness-campaign'
date: '2026-08-27'
modified: '2026-08-30'
body_schema: 'body-v2'
body_hash: 'sha256:009ebfa2d85e67bfdf37dec3c6ce5cc40d5afdfbab036829019845d9902345b8'
related: []
---

# `calculation-correctness-campaign` audit: `the restrictive-default class swept across the calculation path`

## Scope

## Findings

## Recommendations

## What was swept, and why

`no-silent-under-declaration` names the tell for the direction nothing here
watches: "a RESTRICTIVE PROVISION USED AS A DEFAULT". A relief that falls back
to zero when its input is missing raises nothing and warns nothing -- it
produces a valid return on which the taxpayer pays more than they owe.

Every zero fallback in `domain/` and `application/` was derived by AST -- the
`or 0`, `x if cond else 0` and `.get(key, 0)` forms -- and classified by
DIRECTION: does the name it resolves reduce what is owed (relief) or increase
it (liability)? The probe is at
`C:/Users/hello/.claude/jobs/94d17a45/tmp/restrictive_defaults.py`.

Result: 10 relief-side, 9 liability-side. Every relief-side site was read.

## Verdict: the class is clean

None of the ten is a restrictive default. They fall into three honest shapes:

- **Optional field, zero is the true value.** `recargo_amount or Decimal("0")`,
  `suplido_amount or Decimal("0")`. An invoice that charged no recargo has a
  recargo of zero; the fallback states a fact rather than assuming one.
- **Accumulation, absent means no contribution.** The
  `partition_values.get(binding_id, Decimal("0"))` sites in `_iva_ledger.py`
  scale one partition's contribution to a deducible binding. A binding absent
  from that partition contributed nothing TO THAT PARTITION; the deduction is
  not lost, it simply was not in that slice.
- **Explicit determination required.** See below.

## The reference pattern, worth copying

The DANA 2024 reduction is how this is meant to look. It refuses to guess:

- absent eligibility yields `None`, NOT a zero reduction -- "not declared" and
  "declared not eligible" stay distinguishable;
- a missing legal authority RAISES rather than proceeding;
- and for the 2024 annual simplified result the eligibility evidence is
  REQUIRED: `requires_dana_eligibility != (dana_2024_eligibility is not None)`
  raises, so a taxpayer cannot silently lose the relief by saying nothing.

Zero appears only after someone explicitly determined the taxpayer ineligible.
That is a decision on the record, not a default.

## What this does NOT cover

The sweep finds fallbacks that are WRITTEN. It cannot find a relief that was
never modelled, or one modelled with no way to reach it -- for that class see
the tabaco rung, where a rate and boxes exist but no `IvaCategory` can route to
them. Nor does it reach a restrictive default expressed as something other than
a literal zero.

## Status

Closed for the literal-zero-fallback signature. Re-run the probe after any
change that adds a relief.
