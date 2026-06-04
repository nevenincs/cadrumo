---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-W12-P26-S240]]'
---

# `secure-storage-production-hardening` `W12.P26.S240` Review

## S240-001 | PASS | Contract is manifest discovery, not storage ownership

`src/aeat/application/operator_surface/_contract.py` declares immutable
operator-surface contract records and exposes cached lookup helpers. The module
does not construct storage repositories, select secure storage backends, build
SQL routes, read environment variables, open files, write plaintext side stores,
or mutate bucket state.

## S240-002 | PASS | User-facing refusals remain localized application errors

The invalid-root and invalid-source-kind paths raise
`OperatorSurfaceContractError`. That exception derives from `AeatError`, is
registered as `REFUSED_OPERATOR_SURFACE_CONTRACT`, and formats its message
through `tr()`. The contract resolver passes localized refusal reasons and
suggestions rather than raw exception text.

## S240-003 | PASS | Shared models and duplicate concerns were re-grounded

Vaultspec RAG searches clustered the contract with
`src/aeat/application/operator_surface/_models.py`,
`src/aeat/application/operator_surface/test_contract.py`, and adjacent
application contract records. The implementation already uses strict Pydantic
models and local operator-surface enums; source-kind drift is guarded by the
existing subset test against `AggregationSourceKind`.

## S240-004 | PASS | No silent swallowing or settings bypass found

The focused source scan found no `except` blocks, `pass`-style swallowing,
`os.environ`/`getenv` calls, `load_settings` calls, or settings overrides in
the contract module. The only diagnostic side effect is a debug log carrying
stable non-secret contract counts.

## S240-005 | PASS | Validation

- `uv run --no-sync ruff check src/aeat/application/operator_surface/_contract.py src/aeat/application/operator_surface/test_contract.py` passed.
- `uv run --no-sync pytest -q src/aeat/application/operator_surface/test_contract.py` passed with 15 tests.
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit` passed.

Disposition: close `AFR-138` as `manifest-discovery`; no code migration was
required.
