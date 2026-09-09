---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:959861c2e97a4d5c29fcc80206f712cf000ec2515c88cc098ec9b6919465bd03'
step_id: 'S175'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the displaced domain.iva sectoral-prorrata model, heuristic, calculator, constant, self-tests, now-unraisable error contract, and dangling implementation reference after proving the accepted operator-declared sector register and ledger apportionment path is already live; amend the governing differentiated-sectors ADR and clear the module-level production-metastate finding.

## Scope

- `IVA prorrata domain substrate`
- `errors and tests`
- `central error registry and locale mirrors`
- `core regulatory constant prose`
- `legal registry note`
- `differentiated-sectors ADR`
- `production-metastate gate`
- `reachability burndown reference`
- `live sector aggregation tests`
- `unused-symbol measurement`

## Changes

- `M` `src/cadrumo/domain/iva/prorrata.py`
- `M` `src/cadrumo/domain/iva/tests/test_prorrata.py`
- `M` `src/cadrumo/domain/iva/errors.py`
- `M` `src/cadrumo/core/external_constants.py`
- `M` `src/cadrumo/core/prorrata_register.py`
- `M` `src/cadrumo/core/errors/registry/_domain_part2.py`
- `M` `src/cadrumo/_data/registry/aeat/legal/iva.toml`
- `M` `src/cadrumo/locales/en/errors.yml`
- `M` `src/cadrumo/locales/es/errors.yml`
- `M` `src/cadrumo/locales/ca/errors.yml`
- `M` `src/cadrumo/locales/hu/errors.yml`
- `M` `.vault/adr/2026-07-07-prorrata-sectores-diferenciados-adr.md`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `rg -n "ProrrataSectorError|ERROR_IVA_PRORRATA_SECTOR|error_iva_prorrata_sector|ProrrataSector|requires_sectoral_separation|compute_sectoral_prorrata|PRORRATA_SECTORAL_SEPARATION_SPREAD_PP" src/cadrumo dev -g "*"` -> `pass`
- `verify:` `uv run ruff check <S175 Python paths>` -> `pass`
- `verify:` `uv run pytest <S175 prorrata, live sector aggregation, and register paths> -q -n0` -> `pass` (82 passed)
- `verify:` `uv run pytest src/cadrumo/core/errors/tests/test_registry.py src/cadrumo/core/errors/tests/test_registry_enforcement.py -q -n0` -> `pass` (23 passed)
- `verify:` `uv run --no-sync python -m dev.locales audit` -> `fail` (four peer-owned missing/extra pairs)
- `verify:` `uv run python -m dev.quality.production_metastate` -> `fail` (five live findings)
- `verify:` `uv run python -m dev.quality.unused_symbol_coverage` -> `fail` (357 exact symbols; 18 orphan test modules)

- `verify:` `git diff --check -- <S175 paths>` -> `pass`

## Notes

The zero-target metastate gate improved from six findings to five. The exact unused signal improved from 359 to 357 while orphan tests remained at 18. The broader exception-base hygiene gate remains red on 23 unrelated peer exception classes, and the locale audit remains red on the same four peer-owned missing/extra pairs in every locale; neither red names an S175 identity.
