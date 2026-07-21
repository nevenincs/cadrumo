---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-12'
modified: '2026-07-12'
step_id: 'S11'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

# Retarget packaged-resource lookup to the Cadrumo root

## Scope

- `src/cadrumo/core/resources`

## Description

- Ground the packaged-data boundary semantically and read its implementation in full.
- Retarget the primary package anchor through the canonical Cadrumo identity.
- Preserve the authority-owned `registry/aeat` taxonomy and defer the companion namespace to S34.
- Run direct real-resource, lint, formatting, residue, plan, and diff checks.

## Outcome

`files()` now consumes `PRODUCT_IDENTITY.python_package`, resolving `cadrumo/_data` without duplicating the product string authority. Resource facade and boundary prose identify Cadrumo, while `aeat_data`, `aeat_official`, and `registry/aeat` remain unchanged because they are companion/authority surfaces outside this Step.

## Notes

- No mocks, patches, new tests, dynamic-string rewrites, or authority taxonomy changes were introduced.
- The first focused pytest invocation was blocked before collection by the repository-root `conftest.py` still importing the removed `aeat` package; this is pre-existing post-relocation debt outside the resource boundary. The broad resource-directory Ruff invocation also surfaced 22 pre-existing test-docstring findings, so lint verification was narrowed to the two edited production files.
