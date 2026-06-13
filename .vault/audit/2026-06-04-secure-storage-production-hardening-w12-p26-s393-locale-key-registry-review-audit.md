---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# `secure-storage-production-hardening` Code Review

## S393-001 | PASS | Locale registry enrollment

The review found that `src/aeat/application/modelo/_work_create_policy.py` declares
live operator-facing locale keys through `STUB_MODELO_LOCALE_KEYS`, but the locale
scanner previously only collected direct `tr()` calls, error-constructor keys, and
dynamic namespace prefixes. The new scanner rule is narrow: only assignment targets
ending in `*_LOCALE_KEY` or `*_LOCALE_KEYS` are traversed for dotted literals.

## S393-002 | PASS | No broad dictionary sweep

The regression test builds a real temporary Python module and scans it through
`scan_source_tree`. It verifies that a bounded locale-key registry is collected while
an unrelated dictionary value carrying a dotted string remains ignored. The test uses
the production scanner and does not mock, monkeypatch, skip, or duplicate scanner
logic.

## S393-003 | PASS | Canonical locale CLI usage

Locale catalogue repair was performed through `python -m aeat.locales scaffold` and
`python -m aeat.locales set`. The resulting `python -m aeat.locales audit` reports all
four catalogues as clean.

Validation passed:

- `uv run --no-sync ruff check src/aeat/locales/_ast_scanner.py src/aeat/locales/test_parity.py src/aeat/application/wizard/_prompter.py src/aeat/application/wizard/test_prompter.py src/aeat/application/wizard/test_setup_runtime.py src/aeat/application/wizard/test_questionary_smoke.py`
- `uv run --no-sync pytest -q src/aeat/locales/test_parity.py src/aeat/application/wizard/test_prompter.py src/aeat/application/wizard/test_setup_runtime.py src/aeat/application/wizard/test_questionary_smoke.py`
- `uv run --no-sync -q python -m aeat.locales audit`

Disposition: S393 follow-up remains closed.
