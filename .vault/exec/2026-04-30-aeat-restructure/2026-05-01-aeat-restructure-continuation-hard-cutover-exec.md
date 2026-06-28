---
tags:
  - '#exec'
  - '#aeat-restructure'
date: '2026-05-01'
modified: '2026-05-01'
related:
  - '[[2026-04-30-aeat-restructure-plan]]'
---

# `aeat-restructure` `continuation` `hard-cutover`

Continued the restructure ADR cutover after the root package was reduced to package markers only.

- Modified: `src/aeat/application/auth/__init__.py`
- Modified: `src/aeat/adapters/inbound/financial/_raw_transaction.py`
- Modified: `src/aeat/adapters/outbound/aeat/auth/__init__.py`
- Modified: `src/aeat/adapters/outbound/aeat/browser/__init__.py`
- Modified: `src/aeat/adapters/outbound/aeat/sede/test_no_write_surface.py`
- Modified: `src/aeat/domain/invoices/__init__.py`
- Modified: `src/aeat/domain/rental/anexo_c_provider.py`
- Modified: `src/aeat/application/filing/_testing_loader.py`
- Modified: `src/aeat/domain/vat/_modelo_303_mapping.py`
- Modified: `migrations/env.py`
- Modified: `README.md`
- Modified: `env/.env.example`
- Modified: `tests/fixtures/site_health/README.md`
- Modified: `tests/import_contract/domain/invoices/test_reconciliation.py`
- Modified: `tests/import_contract/domain/rental/_test_anexo_c_aggregator.py`
- Modified: `tests/import_contract/domain/formulas/_rulesets/test_all_rulesets_have_citations.py`

## Description

Removed remaining old-layout contradictions found after the ADR migration: stale root package comments, obsolete `src/aeat/...` path references, old `aeat.storage` migration references, and compatibility-layer wording that no longer matches the hard-cut package layout.

Hardened public surfaces by routing application auth through the outbound provider factory and exposing invoice reconciliation service functions from `aeat.domain.invoices`, so import-contract callers do not need to reach into `_service`.

## Tests

Validation used targeted checks only:

- `uv run --no-sync ty check src tests`
- `uv run pytest tests/import_contract/test_adr_layout_import_smoke.py tests/test_docs.py tests/import_contract/domain/invoices/test_reconciliation.py tests/import_contract/domain/rental/_test_anexo_c_aggregator.py src/aeat/application/filing/reconciliation/test_no_write_surface.py src/aeat/adapters/outbound/aeat/sede/test_no_write_surface.py -q`
- `rg` scans for old root packages, old filesystem paths, compatibility-layer labels, and deleted script references.
