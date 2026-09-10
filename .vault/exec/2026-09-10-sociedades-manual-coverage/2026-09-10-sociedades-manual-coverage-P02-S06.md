---
tags:
  - '#exec'
  - '#sociedades-manual-coverage'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:b9dcb3bfbb0279cf96fe9721a88036777e253aeb08005e146b2d9400833c982d'
step_id: 'S06'
related:
  - "[[2026-09-10-sociedades-manual-coverage-plan]]"
---
# Enroll annual Sociedades sources in the legal registry with year-bounded applicability

## Scope

- `src/cadrumo/_data/registry/aeat/legal/is.toml`

## Changes

- `M` `src/cadrumo/_data/registry/aeat/legal/is.toml`
- `verify:` `uv run pytest src/cadrumo/domain/calculations/registry/tests/test_catalogue_verification_verifiers.py -q` -> `pass`
