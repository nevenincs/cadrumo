---
tags:
  - '#exec'
  - '#calculation-chain-integrity'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:4b4ebba096652a92084a7c6f4760930de6157aef2567e357d9414070a1529625'
step_id: 'S53'
related:
  - "[[2026-08-07-calculation-chain-integrity-plan]]"
---

# Add the effective-dated temporary food rates to the Spanish rate table goods-blind, on the measured ground that neither the M390 nor M303 diseno carries any goods axis so a goods distinction would encode information no AEAT box can receive

## Scope

- `src/cadrumo/_data/registry/aeat/legal/`

## Description

- Measure whether the rate table can hold two rates for one tier at one moment.
- Add a typed coexistence marker and scope the tier lookup and overlap rule to it.
- Author three effective-dated records and rescope the two gates that encoded the
  old invariant.

## Outcome

Three records, not four. The zero arm needs none because zero is its own tier and
already classifies.

The naive append is impossible: the tier lookup is single-valued per tier per
date and the loader refuses a same-tier window collision. Measured rather than
assumed, and the refusal is loud rather than silent, which is the safe direction
and the opposite of a first reading.

The representation follows from the law. A tier-to-value question is ambiguous in
these windows with no goods axis anywhere in the filing to disambiguate; a
value-to-tier question is many-to-one and well-defined. Marking a rate as
coexisting rather than replacing keeps the forward lookup answering with the rate
the overwhelming majority of supplies carry, and gives the inverse its own
implementation.

Goods-blind by measurement: neither annual nor quarterly record design carries
any goods axis, so the declaration has nowhere to put the distinction.

## Verification

```
uv run --no-sync pytest src/cadrumo/domain/iva -q --no-header -n0
307 passed in 21.15s

uv run --no-sync pytest src/cadrumo/domain/iva src/cadrumo/application/aggregation/tests -q -n0
1017 passed, 7 deselected in 73.69s
```

## Notes

A zero-rate coexisting record was written and removed after the guard caught it
resolving an August 2024 zero-rated sale to the super-reduced tier instead of
zero, changing the category the row declares under. That was the author's own
scope note contradicted by the author's own commit, caught by a test rather than
by review.

Two gates were rescoped rather than relaxed and both keep their teeth: the
overlap invariant now reads tier-defining records only, in both loader and test,
and a genuine tier-defining collision still fails it. The rate-count assertion
moved with its reason inline so the inventory change stays deliberate.
