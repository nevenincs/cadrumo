---
tags:
  - '#exec'
  - '#ledger-invoice-decomposition'
date: '2026-08-06'
modified: '2026-08-06'
body_schema: 'body-v1'
body_hash: 'sha256:db946ab77cabcb7297a57b3e9f7ac944a901283eae694046c89f7ccbc1c20b74'
step_id: 'S57'
related:
  - "[[2026-08-05-ledger-invoice-decomposition-plan]]"
---

# Wire RentaDeductibilityContext.iva_deduction_ratio to a real producer: a wholly EXENTO iva.regime profile fact resolves to zero, otherwise the bucket's ProrrataRegister whole-entity entry contributes its in-force provisional percentage, mirroring the resolution the M303 side already applies

## Scope

- `src/cadrumo/application/aggregation/_renta_ledger.py`
- `src/cadrumo/application/aggregation/tests/test_renta_ledger.py`
- `src/cadrumo/domain/renta/_ledger_expenses.py`

## Description

- Search by meaning (`vaultspec-rag`) for an existing IVA-deduction-fraction fact before assuming none exists; found two, both real and already reachable in production: `TaxpayerProfile.iva_regime` (`domain.deadlines`, operator-set at profile create, path `iva.regime`) and `domain.prorrata_register.ProrrataRegister` (a full, persisted, CLI-managed per-ejercicio prorrata register).
- Add `_resolve_iva_deduction_ratio` to `_renta_ledger.py`, mirroring the existing `_resolve_residence_ccaa` shape: a wholly `EXENTO` `iva.regime` fact resolves to `0` outright; otherwise the bucket's `ProrrataRegister` whole-entity (`sector_id=None`) entry for the ejercicio contributes its `resolve_provisional` percentage under `GENERAL`/`ESPECIAL` — the SAME resolution `_iva_ledger._active_prorrata_apportionment` already applies on the M303 side, read via the register's own public methods rather than duplicated or reached into privately.
- Thread the resolved ratio through `aggregate_renta_ledger_expenses_from_repositories` → `aggregate_renta_ledger_expenses` → `RentaDeductibilityContext(iva_deduction_ratio=...)`, as new keyword-only parameters with `None` defaults, so the one production caller (`_modelo_bindings.py`'s M100 first-slice source resolver) picks up the real wiring with zero changes of its own — it already omits both new parameters, so it loads the real active-bucket profile and register by default.
- Correct `RentaDeductibilityContext.iva_deduction_ratio`'s own docstring, which asserted "No production caller populates this field yet" — no longer true — and name the M130 quarterly gasto path (`_renta_gasto_ledger.py`, which builds no `RentaDeductibilityContext` at all) as an explicit, separate, NOT-covered follow-up rather than silently widening this Step's scope.
- Add three end-to-end scenario tests to `test_renta_ledger.py`, driven through the real repository path (`aggregate_renta_ledger_expenses_from_repositories`), never a hand-built context: the médico radiólogo `EXENTO` case and the 70%-prorrata `GENERAL` case reuse the exact oracle figures the domain-level unit tests already ground against the AEAT Manual práctico de Renta 2024 and LIVA art. 104.Uno; a third proves a `NINGUNA` regime entry is byte-identical to no entry at all (full deduction rights, no apportionment).

## Outcome

`RentaDeductibilityContext.iva_deduction_ratio` now has a real, live production producer for the M100 annual first slice. The wiring reaches the actual calculation path with no change to the source-mesh resolver: `_modelo_bindings.py` already calls `aggregate_renta_ledger_expenses_from_repositories` with no `profile_record`/`prorrata_register_repository` override, so it now loads the real active-bucket `iva.regime` fact and `ProrrataRegister` on every M100 first-slice calculation. The M130 quarterly gasto path remains unwired — confirmed by grep, not assumed — and is named as a separate follow-up, not silently absorbed into this Step.

## Verification

```
uv run --no-sync pytest src/cadrumo/application/aggregation/tests/test_renta_ledger.py -n 0 -q --no-header
31 passed in 6.43s
```

```
uv run --no-sync pytest src/cadrumo/application/aggregation src/cadrumo/domain/renta src/cadrumo/domain/prorrata_register -n 0 -q --no-header
753 passed, 7 deselected in 42.13s

uv run --no-sync pytest src/cadrumo/application/aggregation src/cadrumo/domain/renta src/cadrumo/domain/prorrata_register -n 0 -q --no-header -m integration
7 passed, 753 deselected in 287.60s (0:04:47)
```

```
uv run --no-sync pytest src/cadrumo/application/modelo/tests/test_e2e_ledger_m130_quarters_to_m100_annual.py -n 0 -q --no-header -m "unit or integration"
5 passed in 27.97s
```

```
uv run --no-sync ruff format --check src/cadrumo/application/aggregation/_renta_ledger.py src/cadrumo/application/aggregation/tests/test_renta_ledger.py src/cadrumo/domain/renta/_ledger_expenses.py
3 files already formatted
uv run --no-sync ruff check src/cadrumo/application/aggregation/_renta_ledger.py src/cadrumo/application/aggregation/tests/test_renta_ledger.py src/cadrumo/domain/renta/_ledger_expenses.py
All checks passed!
```

Mutation proofs against `_renta_ledger.py` (backed up first, sha256 `e0e6c8d6b3ad1eb15eea344c6a40213126a66ea7c0089654cca71cddf83cabf1`, restored and verified byte-identical after each):

```
M1  disable _resolve_iva_deduction_ratio entirely (return None unconditionally)
    reddens exento + prorrata_register tests (2), leaves the NINGUNA
    byte-identical test passing (correctly -- that test's own claim is
    "changes nothing")
M2  disable only the EXENTO branch (if False and regime is IVARegime.EXENTO)
    reddens exactly the exento test, leaves prorrata_register and ninguna
    tests passing -- proves the two positive tests are independently
    load-bearing, not one carrying the other
```

## Notes

The M303 side (`_iva_ledger.py:_active_prorrata_apportionment`) already resolves the register's PROVISIONAL percentage for the ongoing ejercicio, never the definitive one, even for the year's final liquidation -- the art. 105.Cuatro regularización is a separate correction line, not a retroactive rewrite of what was already deducted quarter by quarter. This Step follows the same convention for M100 rather than inventing a definitive-first policy, so the two filings covering the same ejercicio stay consistent with what the ledger actually recovered through IVA that year.

`ProrrataRegisterRegime.NINGUNA` means FULL deduction rights (no prorrata needed, LIVA art. 94 default stands) -- it is the opposite of a wholly-exempt taxpayer, which is `EXENTO` on `iva_regime` instead. A wholly-exempt taxpayer never triggers LIVA art. 102.Uno prorrata at all (it requires con-derecho AND sin-derecho operations "conjuntamente"), so the register legitimately carries no entry for them; checking `iva_regime` first and the register second, rather than trying to fold both into one axis, avoids inventing a third register regime that LIVA does not name.
