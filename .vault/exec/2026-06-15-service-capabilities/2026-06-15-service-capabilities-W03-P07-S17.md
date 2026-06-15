---
tags:
  - '#exec'
  - '#service-capabilities'
date: '2026-06-15'
modified: '2026-06-15'
step_id: 'S17'
related:
  - "[[2026-06-15-service-capabilities-plan]]"
  - "[[2026-06-15-service-capabilities-audit]]"
---




# DEFERRED follow-up: add an llm_vision=off two-mode (scan PDF + image) evidence-refusal regression (honesty review M1)

## Scope

- `src/aeat/application/ledger/tests`

## Description

- Persist a real `UserProfileRecord` carrying `capabilities.llm_vision=false` into the active test bucket (via `UserProfileLifecycleRepository.save`, no mocks), so `resolve_active_capability` reads the opted-out posture.
- Parametrize over both on-host read modes — a scan-only PDF (rasterise path) and an image attachment (direct-bytes path) — and assert `_resolve_evidence` raises `PurchaseInvoiceEvidenceInputError` naming the `llm_vision on` opt-in command.

## Outcome

Closes honesty-review finding M1. The `llm_vision` gate's coverage of every on-host read mode is now pinned by a regression, so a future read mode that lands above or below the gate cannot silently bypass the opt-out. 9 vision-evidence tests pass; ruff + ty clean. Committed as `9803e9dc0`.

## Notes

The `isolated_runtime_profile` fixture provisions a bucket manifest, so `register_minimal_profile` (which refuses on an existing manifest) is the wrong tool here; the record is written directly through the lifecycle repository — the same save path the source-mesh live tests use — and read back via the active-profile resolver.
