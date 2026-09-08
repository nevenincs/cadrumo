---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-04'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:ebd37fcf07e760ee4dbff803bd9988e0db832cb793f53a058c4af6529066ea6f'
step_id: 'S146'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the unraised IVA classification exception reserved for hypothetical future ranking behavior, including its error-registry identity and locale leaves, so production exposes only failure modes a current classifier path can emit

## Scope

- `IVA domain errors`
- `central error registry`
- `localized error catalogues`

## Changes

- `M` `src/cadrumo/domain/iva/errors.py`
- `M` `src/cadrumo/core/errors/registry/_domain_part1.py`
- `M` `src/cadrumo/locales/en/errors.yml`
- `M` `src/cadrumo/locales/es/errors.yml`
- `M` `src/cadrumo/locales/ca/errors.yml`
- `M` `src/cadrumo/locales/hu/errors.yml`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run pytest -q -n 0 src/cadrumo/core/errors/tests/test_registry_enforcement.py` -> `pass (7 passed, 1 existing Pydantic warning)`
- `verify:` focused `uv run ruff check` over the IVA error module and error registry -> `pass`
- `verify:` exact exception, code, locale-key, and future-rationale scan -> `pass (zero matches)`
- `verify:` `uv run python -m dev.locales audit` -> `fail (unrelated pre-existing four-locale missing `tui.declarations.lifecycle.verification_refused` / extra `aggregation.source_mesh.errors.ambiguous_source_disposition` drift)`

## Notes

The full locale audit remains red on one missing and one extra key repeated across all four locales. Neither key is in the edited `errors.yml` leaf set for this Step, and the removed IVA classification key has zero residue in every catalogue.
