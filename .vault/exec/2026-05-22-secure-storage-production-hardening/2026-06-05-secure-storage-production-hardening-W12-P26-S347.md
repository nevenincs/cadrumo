---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S347'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# W12.P26.S347 - Close AFR-245 for IVA schema

Scope: close `AFR-245` for `src/aeat/domain/iva/_schema.py` with signal
`remote-provider`, target `remote-mirror`, and owner `W12.P24.S98`.

## Description

- Audited `IvaCategory`, `IvaExemptionArticle`, `EUMemberState`, `IvaRateKind`, and
  `IvaCitationSource` as closed taxonomy values rather than persistence namespaces.
- Audited `IvaRateRecord`, `IvaCitation`, `IvaRegulation`, `IvaCatalogue`, and
  `IvaVerificationReport` as strict Pydantic models for legal-source and catalogue
  shape validation.
- Confirmed the module has no direct file, SQL, bucket, environment, or secure-object
  storage authority.
- Confirmed the only ignore pragma on `IvaCatalogue.__iter__` is scoped to the
  intentional Pydantic iterator override and does not hide runtime storage defects.
- Closed `W12.P26.S347` through `vaultspec-core vault plan step check` and updated the
  `AFR-245` register status to `closed`.

## Outcome

`AFR-245` is closed as `remote-mirror`. The IVA schema describes external legal and
catalogue evidence consumed by IVA lookup and verification flows; it is not a storage
runtime owner and does not need enrollment into `StorageRuntime`.

Validation passed:

- `uv run --no-sync ruff check src/aeat/domain/iva/_schema.py src/aeat/domain/iva/test_recargo_equivalencia.py src/aeat/domain/iva/test_catalogue_period_keyed.py`
- `uv run --no-sync pytest -q src/aeat/domain/iva/test_recargo_equivalencia.py src/aeat/domain/iva/test_catalogue_period_keyed.py`
- `uv run --no-sync -q python -m aeat.locales audit`
- `uv run --no-sync vaultspec-rag search "IvaCategory IvaRegulation IvaCitation IvaCatalogue remote provider mirror legal citation schema no persistence" --type code --port 8766 --max-results 8`

## Notes

No production code change was required. The storage hardening decision is to keep
`src/aeat/domain/iva/_schema.py` out of runtime-default enrollment because it defines
strict domain data shapes, not persisted profile or bucket data.
