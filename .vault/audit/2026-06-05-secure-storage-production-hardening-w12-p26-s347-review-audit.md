---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
modified: '2026-06-05'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-05-secure-storage-production-hardening-W12-P26-S347]]'
---

# `secure-storage-production-hardening` `W12.P26.S347` Review

## S347-001 | PASS | IVA schema is not a storage authority

`src/aeat/domain/iva/_schema.py` defines strict Pydantic records, StrEnum catalogues,
and catalogue validation helpers. It does not open files, resolve buckets, construct SQL
repositories, read environment values, or persist secure objects. Runtime enrollment is
therefore not applicable to this module.

## S347-002 | PASS | Remote-provider signal maps to remote-mirror data shape

The remote-provider signal comes from legal and regulatory citation shapes:
`IvaCitationSource`, `IvaCitation.url`, retrieval dates, BOE/directive references, and
manual references. Those fields mirror external legal evidence consumed by IVA
catalogue and lookup code, but they are not a local persistence API.

## S347-003 | PASS | Schema and API consistency are explicit

The module uses strict, extras-forbidden Pydantic configuration for frozen records and
keeps the catalogue aggregate mutable only for loader assembly. Cross-field validators
enforce effective-date windows, translation-key presence, citation presence, and
catalogue key alignment. The API surface is typed and stable around shared domain enums
and Pydantic models.

## S347-004 | PASS | Ignore pragma is scoped and justified

`IvaCatalogue.__iter__` carries pyright, ty, and pyrefly ignore comments for an
intentional Pydantic iterator override. The pragma is tied to a specific static-analysis
override mismatch and does not suppress storage, exception, localization, or runtime
logic failures.

## S347-005 | PASS | Validation

- `uv run --no-sync ruff check src/aeat/domain/iva/_schema.py src/aeat/domain/iva/test_recargo_equivalencia.py src/aeat/domain/iva/test_catalogue_period_keyed.py` passed.
- `uv run --no-sync pytest -q src/aeat/domain/iva/test_recargo_equivalencia.py src/aeat/domain/iva/test_catalogue_period_keyed.py` passed with 17 tests.
- `uv run --no-sync -q python -m aeat.locales audit` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.
- `uv run --no-sync vaultspec-rag search "IvaCategory IvaRegulation IvaCitation IvaCatalogue remote provider mirror legal citation schema no persistence" --type code --port 8766 --max-results 8` returned `src/aeat/domain/iva/_schema.py` and IVA lookup evidence.

Reviewer note: no critical, high, medium, or low runtime-storage findings remain for
the S347 slice.

Disposition: close `AFR-245` as `remote-mirror`.
