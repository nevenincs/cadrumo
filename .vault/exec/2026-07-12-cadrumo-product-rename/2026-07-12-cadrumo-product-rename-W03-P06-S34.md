---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-12'
modified: '2026-07-12'
step_id: 'S34'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

# Retarget runtime companion discovery exclusively to the `cadrumo_data` PEP 420 namespace and prove byte access across both built wheel portions

## Scope

- `src/cadrumo/core/resources/_boundary.py`
- `src/cadrumo/core/resources/tests/test_corpus_companion_seam.py`

## Description

- Derive companion discovery from the canonical Cadrumo identity tuple.
- Remove the former namespace from resource-boundary prose, constants, fixtures, and module cleanup.
- Preserve `aeat_official` as the official authority corpus partition.
- Build both real companion wheels and read byte-exact payloads through the production resource resolver.

## Outcome

Runtime discovery now calls `importlib.resources.files` for `cadrumo_data` only,
with no former namespace fallback, alias, or dual import. Both synthetic
multi-portion coverage and freshly built manuals/official wheel portions resolve
through the same production boundary. Nine focused degradation, discovery,
byte-access, and missing-companion tests pass.

## Notes

The official wheel continues to use `corpus/aeat_official`, which identifies
official AEAT source evidence and is not a product namespace. Existing unrelated
staged core changes are excluded from S34 through an explicit four-path commit.
