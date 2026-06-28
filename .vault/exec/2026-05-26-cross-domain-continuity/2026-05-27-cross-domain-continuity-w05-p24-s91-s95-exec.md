---
step_id: S91
date: 2026-05-27
modified: '2026-05-27'
tags:
  - "#exec"
  - "#iva-classification-enrichment"
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
  - "[[2026-05-27-iva-classification-enrichment-adr]]"
commit: c95617243
---

# cross-domain-continuity W05.P24.S91-S95 — IVA intracom/export enrichment

## Deliverables

**S91 — Transaction model + aggregation gate:**

- `src/aeat/domain/transactions/_models.py` — added `iva_category: IvaCategory | None = None` and `counterparty_eu_member_state: EUMemberState | None = None` to `Transaction`; imported `EUMemberState` and `IvaCategory` from `domain.iva._schema`; extended `_coerce_transaction_enum_fields` to coerce both new enum fields from strings on load; updated class docstring with field descriptions.
- `src/aeat/application/aggregation/_iva_ledger.py` — added three new `IvaLedgerAggregationIssueReason` members: `MISSING_COUNTERPARTY_EU_MEMBER_STATE`, `DOMESTIC_COUNTERPARTY_ON_INTRA_COMMUNITY_TRANSACTION`, `EU_MEMBER_STATE_ON_EXPORT_TRANSACTION`; updated `_classify_iva_transaction` to branch on explicit `iva_category` before the `_RATE_KIND_TO_DOMESTIC_CATEGORY` fallback; added `_validate_intracom_export_counterparty` helper enforcing ADR D5 rules (INTRA_COMMUNITY_SUPPLY requires non-ES member state; EXPORT_THIRD_COUNTRY_ZERO_RATED must carry no member state).

**S92 — Casilla 59/60 application-tier helpers:**

- `src/aeat/application/aggregation/_iva_ledger.py` — added `casilla_59_base_imponible(aggregation)` and `casilla_60_base_imponible(aggregation)` functions summing REPERCUTIDO observations by category; exported in `__all__`. These are the pre-registry-binding counterparts per ADR D4; S94 TOML annotation deferred.

**S93 — CLI surface:**

- `src/aeat/entrypoints/cli/_ledger.py` — added `--iva-category` (`IvaCategory | None`) and `--counterparty-eu-member-state` (`EUMemberState | None`) options to `ledger classify`; imported `EUMemberState` and `IvaCategory` from `domain.iva._schema`; passed both through `_patch_from_options`.
- `src/aeat/application/ledger/_models.py` — added `iva_category: IvaCategory | None = None` and `counterparty_eu_member_state: EUMemberState | None = None` to both `ManualLedgerTransactionCommand` and `ManualLedgerTransactionPatch`; imported enums from `domain.iva._schema`.
- `src/aeat/application/ledger/_actions.py` — extended `_command_from_patch` to carry both new fields; extended `_transaction_from_command` payload dict to include them.
- `src/aeat/locales/en.yml`, `es.yml`, `ca.yml`, `hu.yml` — added `iva_category_help` and `counterparty_eu_member_state_help` keys under `cli.ledger.classify`.

**S94 — Registry binding (deferred per ADR):**

No TOML registry changes. Casillas 59 and 60 remain `input_kind = "manual"` pending registry-formula team confirmation of the binding type schema. The application-tier helpers in S92 are the working pre-binding projections.

**S95 — Marc persona test:**

- `src/aeat/application/aggregation/test_intracom_export.py` (new file) — 7 tests covering: INTRA_COMMUNITY_SUPPLY goods populates casilla 59; DOMESTIC_NOT_SUBJECT R12 services do not; EXPORT_THIRD_COUNTRY_ZERO_RATED populates casilla 60; D5 gate rejects ES counterparty on intracom; D5 gate rejects missing counterparty on intracom; D5 gate rejects EU member state on export; combined Marc scenario (goods + R12 services).

## Test outcome

- `test_intracom_export.py` — 7/7 passed
- `test_iva_ledger.py` — 24/24 passed (no regression)
- `test_models.py` (transactions) — 16/16 passed
- `test_catalogue.py` — 20/20 passed

Note: `test_actions.py` in `application/ledger/` fails to collect due to a pre-existing circular import (`DeadlineWindowDefinition` in `registry/__init__`) introduced by concurrent foreign WIP from Task #114 — not caused by this step's changes.
