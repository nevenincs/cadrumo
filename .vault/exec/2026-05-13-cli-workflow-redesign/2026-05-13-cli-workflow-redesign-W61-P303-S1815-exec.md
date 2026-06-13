---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-14'
modified: '2026-05-14'
step_id: 'W61.P303.S1815'
related:
  - "[[2026-05-13-cli-workflow-redesign-epic-plan]]"
  - "[[2026-05-13-cli-workflow-redesign-manual-ledger-storage-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-ledger-transaction-management-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-app-ledger-ratios-shape-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-iva-prorrata-art-101-103-adr]]"
---

# `cli-workflow-redesign` `W61.P303.S1815`

Closed plan rows:

- `W61.P303.S1815`

## Description

Attached usage-ratio references to bucket-local manual ledger rows for mixed private and business usage, then remediated the S1815 review findings.

Usage-ratio profiles are category-keyed and bucket-scoped in secure object storage under namespace `aeat.domain.usage_ratios`, object key `profile:{bucket_id}`, schema version `1`, and FINANCIAL classification. `load_usage_ratios` validates the decrypted inner envelope classification and schema version before returning the payload.

`UsageRatioProfile.ratios` is typed as `Mapping`, frozen with `MappingProxyType`, and serialized through a `field_serializer` so callers cannot mutate validated profile contents after construction.

Added `UsageRatioReference` and `validate_usage_ratio_reference` so ledger rows validate proportional deduction references against the active bucket profile. A ledger `usage_ratio_id` must be a concrete eligible `SpendingCategory.value`, must match the row `category_id`, must exist in the bucket's `UsageRatioProfile`, and must match `business_pct` when `business_pct` is present. Aliases and parallel identifiers are rejected.

Manual ledger commands carry `business_pct`, `category_id`, `usage_ratio_id`, and `prorrata_reference` as separate fields. Mixed rows require `business_pct` in `[0, 1]`; non-mixed rows reject `business_pct`.

`create_manual_transaction` and `update_manual_transaction` validate usage-ratio references before appending bucket events or saving transaction catalogues. Persisted transactions carry `usage_ratio_id` and `prorrata_reference` as separate transaction fields and raw fields. Usage-ratio event payloads include `usage_ratio_id` and `business_pct` when present.

This step treats usage ratios as business/personal split coefficients for proportional deduction. It does not implement or rename this behavior as IVA prorrata.

## Modified Paths

- `.vault/plan/2026-05-13-cli-workflow-redesign-epic-plan.md`
- `src/aeat/application/ledger/_actions.py`
- `src/aeat/application/ledger/_models.py`
- `src/aeat/application/ledger/test_actions.py`
- `src/aeat/application/ledger/test_models.py`
- `src/aeat/domain/usage_ratios/__init__.py`
- `src/aeat/domain/usage_ratios/_model.py`
- `src/aeat/domain/usage_ratios/_service.py`
- `src/aeat/domain/usage_ratios/test_model.py`
- `src/aeat/domain/usage_ratios/test_service.py`

## Tests

- `uv run --no-sync ruff check src/aeat/domain/usage_ratios src/aeat/application/ledger/_actions.py src/aeat/application/ledger/_models.py src/aeat/application/ledger/test_actions.py src/aeat/application/ledger/test_models.py`
  - All checks passed
- `uv run --no-sync ty check src/aeat/domain/usage_ratios src/aeat/application/ledger/_actions.py src/aeat/application/ledger/_models.py src/aeat/application/ledger/test_actions.py src/aeat/application/ledger/test_models.py`
  - All checks passed
- `uv run --no-sync pytest src/aeat/domain/usage_ratios/test_model.py src/aeat/domain/usage_ratios/test_service.py src/aeat/application/ledger/test_models.py src/aeat/application/ledger/test_actions.py -q`
  - 57 passed

Coverage includes bucket-scoped usage-ratio persistence, decrypted inner-envelope classification and schema-version validation, immutable profile ratios, configured category-key acceptance, alias rejection, category mismatch rejection, missing active-bucket profile entries, `business_pct` drift rejection, manual ledger persistence of `usage_ratio_id`, and create-path plus update-path no-save/no-event behavior when usage-ratio validation fails.

## Residuals

`usage_ratio_id` remains a concrete category-backed reference, not an alias layer.

`prorrata_reference` is carried separately from usage-ratio fields. Later `W61.P303` rows remain responsible for IVA prorrata handling and aggregation routing without conflating legal IVA prorrata with usage ratios.
