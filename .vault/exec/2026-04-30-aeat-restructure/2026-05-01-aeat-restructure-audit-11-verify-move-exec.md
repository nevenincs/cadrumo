---
tags:
  - '#exec'
  - '#aeat-restructure'
date: '2026-05-01'
related:
  - "[[2026-04-30-aeat-restructure-adr]]"
  - "[[2026-04-30-aeat-restructure-plan]]"
  - "[[2026-04-30-aeat-restructure-step-13-missing-impl-audit-exec]]"
---

# aeat-restructure audit-11 verify-move

Extract `aeat.domain.justificante._verify` to `aeat.adapters.outbound.aeat.verify`.

## Summary

- Created: `src/aeat/adapters/outbound/aeat/verify/__init__.py`
- Created: `src/aeat/adapters/outbound/aeat/verify/test_verify.py`
- Created: `src/aeat/adapters/outbound/aeat/verify/test_verify_live.py`
- Deleted: `src/aeat/domain/justificante/_verify.py`
- Deleted: `src/aeat/domain/justificante/test_verify.py`
- Deleted: `src/aeat/domain/justificante/test_verify_live.py`
- Modified: `src/aeat/domain/justificante/__init__.py` — removed `verify_csv` import and `__all__` entry
- Modified: `src/aeat/domain/justificante/test_vocabulary_stable.py` — removed `verify_csv` from frozen surface
- Modified: `src/aeat/entrypoints/cli/justificante/__init__.py` — imports `verify_csv` from adapter

## Description

`verify_csv` performs live Playwright/browser automation against AEAT's Sede
electrónica. That is an outbound adapter concern, not a domain concern. The
domain layer must not depend on `aeat.adapters.outbound.aeat.browser` (this
was a latent layering violation — the import was lazy inside a function body,
so import-linter did not catch it statically, but the semantic boundary was
still wrong).

The new home `aeat.adapters.outbound.aeat.verify` imports
`JustificanteVerificationError` from `aeat.domain.justificante._errors` —
that direction (adapter to domain) is correct per the layered contract.

`JustificanteVerificationError` remains in `aeat.domain.justificante._errors`
and on the domain public surface so callers catching the error continue to
work unchanged.

No shim was left in `aeat.domain.justificante`.

## Tests

- `uv run pytest src/aeat/adapters/outbound/aeat/verify/test_verify.py` — 2 passed
- `uv run pytest src/aeat/domain/justificante/test_vocabulary_stable.py` — 1 passed
- `uv run ruff check src/aeat/adapters/outbound/aeat/verify/ src/aeat/domain/justificante/ src/aeat/entrypoints/cli/justificante/` — all checks passed
- `uv run lint-imports` — pre-existing stale ignore entry for `aeat.domain.attachments._repository` (not introduced by this change)
