---
tags:
  - '#adr'
  - '#iva-workflow'
date: '2026-09-21'
modified: '2026-09-21'
body_schema: 'body-v2'
body_hash: 'sha256:ba09257679723157cee17296ac2d816ecd83b55f829bce063c7a75bea708c499'
related:
  - "[[2026-09-21-iva-workflow-reference]]"
---
# `iva-workflow` adr: `Selected-scope IVA completeness issue gating` | (**status:** `accepted`)

## Problem Statement

The IVA ledger can reject a transaction inside the selected filing scope while
returning valid observations from other rows. Unless the rejection survives as
durable calculation evidence, later verification and export can present the
partial result as complete. A durable blocking boundary is required without
turning every informational diagnostic or intentional exclusion into a filing
failure. The measured contract is recorded in
`2026-09-21-iva-workflow-reference`.

## Considerations

- Invoice document facts and transaction ledger facts have separate canonical
  owners; linkage establishes evidence association and does not create monetary
  precedence (`2026-09-21-iva-workflow-reference`).
- Aggregation already emits typed issues, so the decision can classify and carry
  the existing outcome rather than introduce another validation engine.
- Reviewed exclusions and period/profile filtering are intentional selection
  decisions, not incomplete evidence.
- Informational invoice-to-ledger differences must remain visible without
  overriding ledger-owned tax facts; existing hard contradictions remain hard.
- The user authorized implementation only where incomplete or contradictory
  selected evidence cannot yield an apparently complete return, and prohibited
  a second ledger, aggregation engine, authority loader, or silent precedence.

## Considered options

1. Persist and block every aggregation diagnostic. Rejected because it collapses
   informational discrepancies and intentional exclusions into filing failures.
2. Classify the existing typed issues and durably block only selected-scope
   financial-completeness failures. Chosen because it closes silent omission while
   preserving the established diagnostic boundary.
3. Permit operator waivers for blocking issues. Rejected for this slice because
   no grounded waiver policy exists and a waiver would weaken the required
   completeness invariant.

## Constraints

- A selected-scope issue is blocking only when the row was otherwise in scope and
  missing, unsupported, or contradictory financial evidence prevents a reliable
  IVA observation or deduction result.
- Reviewed-excluded rows and rows outside the chosen bucket, profile, period, or
  year remain outside the blocking set.
- A non-blocking linked-invoice discrepancy never changes transaction amounts or
  classifications. An existing hard invoice contradiction stays a refusal.
- Persisted issue evidence carries stable source identity and typed reason, not
  raw taxpayer payloads or plaintext financial evidence.
- No operator waiver, inferred zero, copied invoice total, or frontend-specific
  tax arithmetic is introduced by this decision.

## Implementation

Define one explicit blocking classification over the existing IVA aggregation
issue reasons. Aggregation continues to return observations and typed issues.
Calculation staging projects each blocking selected-scope issue into the existing
durable source-issue/evidence channel with enough stable identity to audit and
recompute it. Verification and export refuse completeness while any such issue is
unresolved. Non-blocking diagnostics remain operator-visible through the existing
notice channel.

Regression coverage pins both sides of the boundary: every blocking evidence
failure survives calculation persistence and prevents verification/export, while
reviewed exclusions, out-of-window rows, and explicitly diagnostic invoice
differences remain non-blocking. The detailed insertion points and current gap are
owned by `2026-09-21-iva-workflow-reference`.

## Rationale

The chosen option is the smallest change that makes completeness durable. It
reuses the typed aggregation result, calculation source mesh, and existing
verification/export gates. Blocking every diagnostic has an unacceptable
false-refusal profile; adding waivers before a policy exists reopens silent
under-declaration through an operator bypass. Persisting only typed
financial-completeness failures preserves one fact owner and one calculation path.

## Consequences

Calculations may still return useful partial diagnostics, but cannot be verified
or exported as complete while selected financial evidence is missing or
contradictory. Operators receive a stable issue identity across reopening and
recalculation. The blocking taxonomy becomes a reviewed contract that must be
updated when new IVA issue reasons are added. A future waiver mechanism, if ever
required, needs separate evidence and authorization.
