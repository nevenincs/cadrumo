---
tags:
  - '#exec'
  - '#iva-prorrata-complexity'
date: '2026-07-08'
modified: '2026-07-17'
body_hash: 'sha256:b57b08b88cf0239690d9865dd0c5d55ba719d74d0df2656f39dd68041795f23d'
step_id: 'S12'
related:
  - "[[2026-07-07-iva-prorrata-complexity-plan]]"
---

# Make the shared ledger IVA apportionment regime-aware so especial routes each deducible cuota via _deductible_percentage_for (100/0/general), the general path stays byte-identical, and provenance carries the applied classification and percentage

## Scope

- `src/aeat/application/aggregation/_iva_ledger.py`

## Description

- Promote `_deductible_percentage_for` to the public `deductible_percentage_for` in `src/aeat/domain/iva/_prorrata.py`, add it to the module `__all__` and re-export it through the `aeat.domain.iva` package facade so the application aggregation layer consumes the single canonical art. 106.Uno regla mapping (100 / 0 / general) rather than re-deriving it.
- Carry the operator-declared art. 106 use-classification onto the IVA ledger observation: add `input_classification: InputClassification | None` to `IvaLedgerObservation` in `src/aeat/domain/calculations/registry/_ledger_bindings.py`, and populate it from the source transaction in `_iva_observation` (settlement and cash-accounting paths) in `src/aeat/application/aggregation/_iva_ledger.py`.
- Add a `regime: ProrrataRegisterRegime` axis (default `GENERAL`) to `IvaLedgerProrrataApportionment`, and make `_active_general_prorrata_apportionment` regime-aware (renamed `_active_prorrata_apportionment`): a `GENERAL` or `ESPECIAL` register entry both resolve the provisional percentage; `ESPECIAL` stamps the regime so the binding resolver routes per input.
- Branch `resolve_iva_ledger_binding_values` on regime: `GENERAL` keeps the flat `cuota * percentage` deducible-cuota multiplier byte-identical, `ESPECIAL` delegates to a new `_apply_especial_apportionment` that partitions observations by classification, re-resolves the deducible cuota bindings through the SAME canonical registry resolver per partition, and weights each by `deductible_percentage_for` (exclusively-deductible 100 %, exclusively-non-deductible 0 %, common and unclassified at the general percentage); non-deducible bindings keep their unapportioned aggregate.
- Make the apportionment provenance `source_ref` in `src/aeat/application/aggregation/_modelo_bindings.py` regime-aware (`:{regime}:` instead of a hardcoded `:general:`); the `GENERAL` string is byte-identical to the prior value.

## Outcome

Prorrata especial per-input apportionment (LIVA art. 106.Uno) now routes each deducible IVA cuota by the transaction's declared use, reusing the one shared aggregation path. Added three regressions to `test_iva_ledger_prorrata_apportionment.py`: a byte-identical general-regime pin (10.50 * 80 % == 8.400), a three-regla especial routing proof (10.50 + 0 + 8.40 == 18.900), and an especial-all-common == general byte-identical proof. Gates green on the owner slice: ruff, ruff format, ty, and the whole-tree `--collect-only` all clean; 657 aggregation + IVA domain tests, 5 apportionment regressions, and 481 source-mesh + calculations tests pass.

## Notes

- The general-regime path is proven byte-identical both by an exact-value pin and by the especial-all-common equivalence test; adding the optional `input_classification` field to the transient `IvaLedgerObservation` does not perturb general binding resolution.
- Unclassified deducible inputs under especial are apportioned at the general percentage (the mixed-use / common default), never assumed exclusive. Surfacing an operator advisory specifically for unclassified especial inputs is out of this step's scope and belongs to the CLI/notice surfacing work.
- Pre-existing peer-owned broken-HEAD failures are NOT from this step: the bienes-inversión M390 `casilla-63` "missing binding fact" registry-completeness errors (6 in the registry suite, 1 in `test_binding_prefill.py`) and the M131 `0604` / art-105/107-110 closure failures are the documented bienes-inversión / M131 campaign broken-HEAD; none of the failing tests reference any symbol changed here, and the registry TOML is unmodified.
