---
tags:
  - '#exec'
  - '#calculation-truth-registry'
date: '2026-05-04'
modified: '2026-05-04'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
---

# `calculation-truth-registry` `phase5` `step21`

Moved the VAT rate and catalogue authority out of runtime Python and into
committed registry TOML.

- Modified: `registry/aeat/vat/rates.toml`
- Modified: `registry/aeat/vat/catalogues/2025.toml`
- Modified: `src/aeat/domain/vat/_rates.py`
- Modified: `src/aeat/domain/vat/_catalogue.py`
- Modified: `src/aeat/domain/vat/_corpus.py`
- Modified: `src/aeat/domain/vat/_lookup.py`
- Modified: `src/aeat/domain/vat/_schema.py`
- Modified: `src/aeat/domain/vat/_verify.py`
- Modified: `src/aeat/domain/vat/__init__.py`
- Modified: `src/aeat/domain/vat/_classification.py`
- Modified: `src/aeat/domain/vat/errors.py`
- Modified: `src/aeat/domain/vat/test_catalogue_period_keyed.py`
- Modified: `src/aeat/domain/vat/test_corpus.py`
- Modified: `src/aeat/domain/vat/test_rates_temporal.py`
- Modified: `src/aeat/domain/vat/test_rules.py`
- Modified: `src/aeat/domain/vat/test_verify.py`
- Modified: `env/.env.example`
- Modified: `.vault/plan/2026-05-03-calculation-truth-registry-rebuild-plan.md`

## Description

VAT rates now load from `registry/aeat/vat/rates.toml`, with runtime code
limited to strict TOML loading, pydantic validation, immutable table exposure,
and overlap checks. VAT catalogue records now load from
`registry/aeat/vat/catalogues/2025.toml`, with exact-year resolution and no
runtime fallback year.

The VAT regulation schema no longer carries `declares_in_modelos`; modelo and
casilla binding authority must be expressed by modelo registry snapshots rather
than VAT category records. The public VAT package no longer exports a
year-specific catalogue alias, and `cite` now requires either an explicit
catalogue or effective date.

VAT tests now assert committed registry rate and catalogue loading, exact-year
resolution, temporal lookup behaviour, and validation failures for malformed
or incomplete registry data.

## Tests

- `uv run pytest src/aeat/domain/vat -q`
- `uv run pytest src/aeat/domain/calculations/registry src/aeat/domain/deadlines src/aeat/domain/vat -q`
- `uv run ruff check src/aeat/domain/calculations/registry src/aeat/domain/deadlines src/aeat/domain/vat`
- `uv run ty check src/aeat/domain/calculations/registry src/aeat/domain/deadlines src/aeat/domain/vat`
- `git diff --check -- .vault/plan/2026-05-03-calculation-truth-registry-rebuild-plan.md registry/aeat/vat src/aeat/domain/vat env/.env.example`
