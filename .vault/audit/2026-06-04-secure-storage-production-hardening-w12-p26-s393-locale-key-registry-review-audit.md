---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-10-03'
body_hash: 'sha256:e7e07131d8afdce6c9a53303e0fac35d2e1abcab90c4b8082aa902a8a8252b27'
related: []
---

# `secure-storage-production-hardening` Code Review

## S393-001 | PASS | Locale registry enrollment

The review found that the retired module declared
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

- the historical check
- the historical check
- `uv run --no-sync -q python -m aeat.locales audit`

Disposition: S393 follow-up remains closed.
