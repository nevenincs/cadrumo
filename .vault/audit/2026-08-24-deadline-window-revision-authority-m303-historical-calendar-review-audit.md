---
tags:
  - '#audit'
  - '#deadline-window-revision-authority'
date: '2026-08-24'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:81bb1692480764c0dfd229bf983a55c5d014b0dd79af3e23e10a71746b379b0b'
related: []
---
# Modelo 303 historical deadline materialisation review

## Verdict

Pass for the implemented S12 increment. No critical, high, medium, or low findings.

## Scope reviewed

- Modelo 303 deadline-window fragments for revisions `2022`, `2024-hasta-08-y-2t`, `2024-desde-09-y-3t`, and `2025`.
- Their owning construct deadline memberships and calendar source closure.
- Exact census, date, payment-cutoff, and canonical ownership regressions in `test_modelo_303_registry.py`.
- The S12 execution record and its intentionally open plan status.

## Evidence

- The bundled official AEAT 2022, 2024, 2025, and following-January calendars directly publish every added presentation deadline and direct-debit cutoff.
- Exactly 21 missing historical coordinates were materialised. No cadence arithmetic or inferred future date appears in the changed data.
- The 2024 early/late owner split matches the existing period selectors and resolves through the existing `select_revision` function.
- Focused M303 validator/deadline tests passed: `6 passed`.
- Ruff passed on the focused M303 test module; `git diff --check` passed.
- Vaultspec RAG before and after the edit located only the existing revision selector, ownership validator, registry projection, and filing-window resolver. Exact search found no redeclaration in the owned surface.

## Residual

Filing-year 2026 month `12` is the sole missing M303 selector coordinate. Its filing and payment dates fall in the unpublished 2027 calendar cycle. It is correctly left unauthored, without an inferred cutoff, so S12 remains open.
