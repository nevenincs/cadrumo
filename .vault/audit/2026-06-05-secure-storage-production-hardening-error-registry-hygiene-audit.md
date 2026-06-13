---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
modified: '2026-06-05'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# `secure-storage-production-hardening` Error Registry Hygiene

## ERH-001 | FIXED | IVA wallet seed exceptions bypassed the AEAT error base

Root-help and core-error validation during the W12.P26 closeout surfaced that the
Modelo IVA wallet seed exception root still derived from built-in `Exception`.
The seed error now derives from the modelo error hierarchy and has explicit
central error-code entries for the base seed error, missing-taxpayer refusal, and
negative-amount refusal.

## ERH-002 | FIXED | Registry enforcement depended on prior test imports

The registry enforcement test walked the error-test package path when run in
isolation and could also observe intentionally unregistered test-only classes
created by sibling tests in the same process. The guard now imports production
`aeat` modules deterministically and excludes test-only subclasses from the
production registry invariant.

## Validation

- `uv run --no-sync ruff check ...`
- `uv run --no-sync pytest -q src/aeat/core/errors/tests`
- `uv run --no-sync pytest -q -m integration src/aeat/entrypoints/cli/tests/test_root_help_shape.py`
- `uv run --no-sync python -m aeat.locales audit`

## Review

The `vaultspec-code-reviewer` review reported no findings for the scoped repair.
