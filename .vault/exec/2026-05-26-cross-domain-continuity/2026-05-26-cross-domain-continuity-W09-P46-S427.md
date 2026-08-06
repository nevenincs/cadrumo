---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-11'
modified: '2026-07-11'
body_hash: 'sha256:dbbe9068cf7f19300445ffb5cc5792b7fc140385c15af1ef76fac329d917c62b'
step_id: 'S427'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# Consolidate duplicated prior-quarter ordinal and expanding-span logic onto the registry period-offset authority while preserving Modelo 130 cumulative-payment semantics

## Scope

- `src/aeat/domain/calculations/registry/_period_offset_math.py`
- `src/aeat/domain/calculations/registry/_bindings_previous_filing.py`
- `src/aeat/domain/calculations/registry/__init__.py`
- `src/aeat/application/modelo/_prior_payment_advisory.py`
- Focused registry and Modelo 130 carry/advisory tests

## Description

- Ground the work with `vaultspec-rag`, then read the period-offset authority, prior-filing resolver, Modelo 130 advisory, and their real repository-backed tests in full.
- Add the registry-owned `same_ejercicio_prior_quarter_anchors()` primitive, deriving ordered current-ejercicio prior-quarter anchors by repeatedly applying `apply_period_offset()` until the prior-year boundary.
- Route the previous-filing expanding-span selector through that primitive while retaining its consumer-specific invalid-period error context.
- Re-export the primitive through the registry facade and route Modelo 130 advisory prior-quarter selection through it, retaining non-quarterly empty behavior and the 1T first-filer safeguard.
- Add independently enumerated expected-anchor coverage and a real encrypted-store 3T degradation advisory regression that names only `1T, 2T` and never a prior-year `4T`.

## Outcome

The same-ejercicio prior-quarter sequence now has one registry authority. Modelo 130 casilla `05` keeps its existing cumulative `Σ max(0, prior 07) − Σ prior 16` behavior, while the advisory continues to distinguish a real non-first-quarter degradation from a first obligation. No fake, mock, stub, patch, or monkeypatch was used.

Validation passed:

- `uv run --no-sync ruff check src/aeat/domain/calculations/registry/_period_offset_math.py src/aeat/domain/calculations/registry/_bindings_previous_filing.py src/aeat/domain/calculations/registry/__init__.py src/aeat/application/modelo/_prior_payment_advisory.py src/aeat/domain/calculations/registry/tests/test_bindings_previous_filing.py src/aeat/application/modelo/tests/test_modelo_130_prior_payment_advisory.py`
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/tests/test_bindings_previous_filing.py src/aeat/domain/calculations/registry/tests/test_bindings_previous_filing_offset.py src/aeat/application/calculations/tests/test_modelo_130_casilla_05_carry.py src/aeat/application/modelo/tests/test_modelo_130_prior_payment_advisory.py -q` — 29 passed.
- Independent code review approved the offset-derived sequence, selector error contract, casilla-05 cumulative identity, and real first-filer/advisory coverage.

## Notes

The plan checkbox is intentionally unchanged pending independent review.
