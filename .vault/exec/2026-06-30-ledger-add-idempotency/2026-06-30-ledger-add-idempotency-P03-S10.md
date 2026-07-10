---
tags:
  - '#exec'
  - '#ledger-add-idempotency'
date: '2026-06-30'
modified: '2026-07-08'
step_id: 'S10'
related:
  - "[[2026-06-30-ledger-add-idempotency-plan]]"
---

# Confirm verify_modelo_revision upserts the outcome-pinned report in place so a non-granting retry collapses to one report while the granting path stays self-limiting

## Scope

- `src/aeat/application/modelo/_verification_actions.py`

## Description

- Update the `verify_modelo_revision` report-id derivation call to pass the classified `completeness` and the `findings` tuple (already computed before the derivation) instead of `run_at`.
- Confirm `verify_modelo_revision` persists via `upsert_verification_report`, which keys on `verification_report_id`: with the outcome-pinned id, a non-granting retry with identical findings upserts in place (collapses to one report) while the granting path stays self-limiting (it flips the revision out of BORRADOR, so a re-verify refuses before persisting).

## Outcome

Landed in commit `e67b8d7cb`. The collapse is by construction of the id; the behavioural proof (identical-findings retry collapses, changed-finding re-verify diverges) lands as `S17`.

## Notes

Co-committed with `S08` and `S09`. The end-to-end verify-flow suite (`test_file_flow_verify.py`) is currently red in the working tree from an UNRELATED peer M390 registry edit (a new `relations/0004-...-simplificado.toml` not yet covered by `modelo-390-dep-303`), which fails registry snapshot build for any test that loads the full registry; that failure is the M349/M390 peer campaign's surface, not this change (proven: the same `RegistryValidationError` reproduces in pure registry-validation tests, and the verify-report unit roundtrip + CLI view tests pass).
