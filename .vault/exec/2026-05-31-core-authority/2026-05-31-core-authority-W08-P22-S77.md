---
tags:
  - '#exec'
  - '#core-authority'
step_id: S77
date: '2026-05-31'
modified: '2026-05-31'
related:
  - '[[2026-05-31-core-authority-plan]]'
  - '[[2026-05-31-core-authority-adr]]'
---

# core-authority W08.P22.S77 - FinancialProviderProtocol + remove adapter imports

## Outcome

Created `src/aeat/application/ledger/_protocols.py` with `FinancialProviderProtocol`
— a `runtime_checkable` Protocol covering only the two methods `_actions.py` calls:
`ingest(path: Path) -> Iterator[RawTransaction]` and `validate_source(path: Path) -> ProviderValidation`.
`ProviderValidation` is TYPE_CHECKING-guarded in the Protocol file (ADR Exception C).

Updated `application/ledger/_actions.py`:

1. Removed module-scope `from ...adapters.inbound.financial.providers import (CsvProvider, FinancialProvider, FinancialProviderError, OfxProvider, PdfN26Provider, ProviderValidation, XlsxProvider, detect_provider)` — RELOC-020.
2. Concrete providers and `detect_provider` moved to lazy local imports inside `_resolve_financial_provider` with `# noqa: PLC0415`.
3. `FinancialProviderError` moved to lazy local import inside `import_ledger_source` (required for except clause; cannot be annotation-only).
4. `ProviderValidation` moved to `TYPE_CHECKING` guard.
5. `FinancialProvider` type annotation replaced with `FinancialProviderProtocol`.
6. `from ...adapters.inbound.pdf._utils import sha256_file` → `from ...core.hashing import sha256_file`.
7. `from ...adapters.persistence.storage.attachment import AttachmentStore` removed; `AttachmentStore()` default in `_verify_attachment_references` uses lazy local import.
8. Fixed pre-existing `AttachmentStoreProtocol` import path (`_repository` → `_protocols`).

## Commit

`431049aae` — refactor(ledger): W08.P22.S77 - FinancialProviderProtocol + remove adapter imports

## Files touched

- `src/aeat/application/ledger/_protocols.py` — new Protocol file
- `src/aeat/application/ledger/_actions.py` — all adapter imports removed from module scope

## Before / After

Before: 3 module-scope `application→adapters` edges in `_actions.py`.
After: 0 module-scope application→adapters edges; lazy local imports with noqa where
runtime adapter access is unavoidable (exception class, concrete instantiation).

## Verification

192 ledger tests pass. 4 pre-existing failures on `source_jurisdiction` field in
export fieldnames — unrelated to S77. `ruff check` passes with no errors.
