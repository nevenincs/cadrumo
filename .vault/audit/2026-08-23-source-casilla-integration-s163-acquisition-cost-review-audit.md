---
tags:
  - '#audit'
  - '#source-casilla-integration'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:57b50ce1e434817cf482ff4e8f621537e1d22c8f0891e91cdfba73bc7354b6a2'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---



# `source-casilla-integration` audit: `s163 acquisition cost review`

## Scope

Formal review of the S163 inventory-domain acquisition-cost contract, arithmetic, valuation propagation, fingerprint identity, and focused behavioral tests against the accepted inventory mapping decision.

## Findings

### s163-acquisition-cost-review | high | resolved evidence completeness was tautological

The first implementation accepted generic evidence presence as proof that attributable-cost and IVA-recoverability reviews occurred. The corrected contract admits closed review evidence roles, binds both completeness references to their required roles, refuses review evidence as purchase consideration, and retains component evidence coverage. Role-substitution tests now prove refusal.

### s163-acquisition-cost-review | high | resolved weighted-average layers lost authoritative cents

The first implementation rounded weighted-average layer unit cost to cents, so an uneven quantity could not reproduce the authoritative complete acquisition total. The corrected engine retains the exact internal unit basis. A one-hundred-euro purchase of three units now produces a closing layer accepted unchanged as the following year's opening against the exact closing value.

### s163-acquisition-cost-review | medium | resolved decimal scale changed fingerprints

The first fingerprint projection used fixed-point formatting directly, allowing scale-equivalent decimals to hash differently. Every decimal now uses the shared canonical decimal spelling before canonical JSON hashing, and the mutation suite proves scale equivalence while retaining evidence and economic sensitivity.

### s163-acquisition-cost-review | pass | final contract satisfies S163

Re-review found no remaining critical, high, medium, or low findings. Complete acquisition cost is purchase-only, evidence-backed, cents-consistent, and the sole purchase authority across FIFO, weighted average, closing stock, cost of goods sold, and purchase aggregation. The focused suite passed 25 tests; Ruff and ty passed.

## Recommendations

Proceed with S164 application and operator propagation without duplicating the domain arithmetic or weakening the evidence-role contract.
