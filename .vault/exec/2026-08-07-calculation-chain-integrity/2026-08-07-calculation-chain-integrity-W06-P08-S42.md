---
tags:
  - '#exec'
  - '#calculation-chain-integrity'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:8a58783048f2b4e0137bd39663db642a9384acb40a59ae15b9cbe0e1841bef37'
step_id: 'S42'
related:
  - "[[2026-08-07-calculation-chain-integrity-plan]]"
---
# `calculation-chain-integrity` exec W06.P08.S42

## Outcome

Documented at the declaration, so the subset is not refiled as a defect.

## What is recorded

The comment on `_CLAVE_BY_KIND_AND_CATEGORY` (`application/invoices/_source_resolver.py:119-120`) states that **R / D / C**, the call-off stock claves, report movements that carry no invoice at all, so no invoice-sourced path can reach them.

That is unreachability by SCOPE rather than an omission: a call-off stock movement is a transfer of goods under a consignment sales arrangement, reported without an invoice, so there is no invoice for an invoice-sourced resolver to classify. No amount of widening the category table would reach them.

## Why this needed its own Step

A reader comparing the four-entry table against the ten-member operation-type enum sees a large shortfall and reasonably files it as incomplete. The register this campaign inherited did exactly that once already. Recording the scope boundary at the table converts a recurring false finding into a settled one.

It sits alongside the M/H note from `S35`, and the two are deliberately distinguished: M/H are reachable-but-ambiguous, R/D/C are unreachable-by-construction. A single "these five are not emitted" note would have lost that.
