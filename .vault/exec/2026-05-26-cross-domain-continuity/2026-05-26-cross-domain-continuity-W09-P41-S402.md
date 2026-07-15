---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-10'
modified: '2026-07-10'
step_id: 'S402'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
  - "[[2026-07-10-cross-domain-continuity-audit]]"
---
# S400a precursor: author m210-2025-profile-country-of-fiscal-residence binding declaration so the formula op at S400 can consume the enum binding via ctx.enum_binding_values

## Scope

- `matches the canonical M100 precedent at modelos/100/revisions/2025/bindings/0008-renta-2025-profile-tax-residence-ccaa.toml (source=profile`
- `selector profile_model+field+typed_enum`
- `aggregation op=copy)`
- `small 1-file 10-line TOML`
- `unblocks S400 main formula authoring`
- `src/aeat/_data/registry/aeat/modelos/210/revisions/2025/bindings/0001-bindings.toml`

## Description

Reconciled the retained historical execution evidence for this Step. The related reconciliation audit names commit `f79cc34a8a` as the direct evidence.

No production sources changed.

## Outcome

Restores one-Step/one-record traceability for this checked Step without rewriting historical implementation.

## Notes

The related reconciliation audit names the exact historical evidence. This documentation-only record makes no new production-behavior claim.
