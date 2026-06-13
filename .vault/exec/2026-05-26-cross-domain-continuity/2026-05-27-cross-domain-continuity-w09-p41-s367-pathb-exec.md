---
step_id: S367
tags:
  - "#exec"
  - "#cross-domain-continuity"
date: 2026-05-27
modified: '2026-05-27'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
  - "[[2026-05-27-m721-informativa-criptomonedas-research]]"
---

# cross-domain-continuity W09.P41.S367 — M721 Path-B work create refusal guard

## Outcome

`aeat app modelo work create --modelo 721 --year 2024 --period 0A --revision 2023-y-siguientes`
returns a legally-grounded refusal (exit non-zero) citing Orden HFP/887/2023,
the €50.000 threshold, and AEAT Sede — instead of silently provisioning an
uncalculable work unit or returning a generic crash.

The refusal guard fires before the active-profile check: an operator without a
profile still receives the legal-grounded message, not a "no active profile" error.

## Implementation

**Commit** `9fc5dd5ed`

- `src/aeat/entrypoints/cli/_modelo.py` — `_STUB_ONLY_MODELOS: frozenset[str] =
  frozenset({"721"})` + `_guard_stub_modelo(modelo)` function; guard inserted in
  `work_create` after `_validate_registry_target` and before `_require_active_profile`.
  Raises `CliRefusedBoundaryError` with `tr("cli.app.modelo.work.create_stub_modelo_refused")`.
  Refusal message cites all three legal authorities:
  - Ley 11/2021 Art. 13 / DA 10ª (obligation basis)
  - Orden HFP/887/2023 BOE-A-2023-17455 (form approval + €50.000 threshold)
  - RD 1065/2007 Art. 42 quáter (reglamento operativo)

- `src/aeat/locales/es.yml`, `en.yml`, `ca.yml`, `hu.yml` — locale key
  `cli.app.modelo.work.create_stub_modelo_refused` added via
  `python -m aeat.locales scaffold` and translated for all four supported languages.

- `src/aeat/entrypoints/cli/test_modelo_721_stub_refusal.py` — three regression tests:
  1. `test_work_create_721_refuses_with_legal_authority_message` — asserts exit != 0,
     "HFP/887/2023" in output, "50" in output, "sede.agenciatributaria" in output;
     no "Traceback", no "could not evaluate", no "Modelo desconocido"
  2. `test_work_create_721_registry_loader_accepts_without_integrity_error` — roundtrip:
     `load_registry_tree` + `RegistryValidator.validate_modelo` + `build_snapshot`
     for year 2024, period 0A resolves to revision "2023-y-siguientes" without error
  3. `test_work_create_721_refusal_fires_before_profile_check` — no profile created;
     exit != 0 and output contains "HFP/887/2023", not a profile error

## Prior work (same S367)

The prior step record at `2026-05-27-cross-domain-continuity-P41-S367.md` covers
commits `37933ecca` (registry stub) and `c72742b42` (`overview explain` regression
test). This record covers the `work create` refusal guard added in the current
task iteration.

## Quality gates

- G1 (no naked env reads): pass — no `os.environ` / `os.getenv` added
- G2 (typed pydantic at boundaries): pass — no new persistence boundaries
- G3 (tr() for user messages): pass — `CliRefusedBoundaryError` raised with `tr()`
- G5 (no shims/duplication): pass — single canonical guard function and frozenset
- G6 (no tautological tests): pass — tests assert specific legal authority strings
  ("HFP/887/2023", threshold, Sede URL) that must come from the guard implementation

## Test results

```
src/aeat/entrypoints/cli/test_modelo_721_stub_refusal.py — 3 passed
src/aeat/domain/calculations/registry/test_referential_integrity.py — 49 passed
```
