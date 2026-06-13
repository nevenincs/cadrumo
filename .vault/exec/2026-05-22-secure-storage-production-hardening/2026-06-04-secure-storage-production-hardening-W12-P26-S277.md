---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S277'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# W12.P26.S277 - Close AFR-175 for wizard translations

Scope: close `AFR-175` for `src/aeat/application/wizard/_translations.py` with
signals `plain-file, remote-provider`, target `remote-mirror`, and owner
`W12.P24.S98`.

## Description

- Verified wizard translation audit code performs local descriptor/source
  introspection only and does not own remote-provider or secure-storage routes.
- Repaired locale catalogue drift for modelo work-creation refusal keys using
  `python -m aeat.locales`.
- Verified the stale `relation_not_decimal` locale entry was pruned by the locale
  scaffold/audit flow.
- Ran focused translation tests, ruff, canonical locale audit, and vaultspec RAG
  duplication discovery.

## Outcome

`AFR-175` is closed as `remote-mirror`. `_translations.py` remains a local audit
surface, and the locale catalogues now resolve the concrete modelo work-creation
refusal keys referenced by code.

Validation passed:

- `uv run --no-sync ruff check src/aeat/application/wizard/_translations.py src/aeat/application/wizard/test_translations_helpers.py src/aeat/application/wizard/test_wizard_translations_resolve.py src/aeat/application/wizard/test_flow_description_keys.py src/aeat/locales`
- `uv run --no-sync pytest -q src/aeat/application/wizard/test_translations_helpers.py src/aeat/application/wizard/test_wizard_translations_resolve.py src/aeat/application/wizard/test_flow_description_keys.py`
- `uv run --no-sync -q python -m aeat.locales audit`
- `uv run --no-sync vaultspec-rag search "wizard translations audit cli translation keys locales source introspection remote provider mirror" --type code --port 8766 --max-results 8`

## Notes

The initial bare `python -m aeat.locales scaffold` attempt failed outside the project
environment. The successful invocation used the same module entry point through
`uv run --no-sync`.
