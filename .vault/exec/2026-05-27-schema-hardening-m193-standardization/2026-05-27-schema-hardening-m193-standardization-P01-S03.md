---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-27'
modified: '2026-05-27'
step_id: 'S03'
related:
  - '[[2026-05-27-schema-hardening-m193-standardization-plan]]'
---



# `schema-hardening-m193-standardization` `P01.S03`

Verified the Modelo 193 directory-fragment layout against the focused
M193 registry suite and the loader directory-mode suite. The
mechanical split preserves loader equivalence, the annual-summary
relation tree, the detail-record row builders, and the deterministic
snapshot fingerprint.

- Modified: `.vault/plan/2026-05-27-schema-hardening-m193-standardization-plan.md`
- Created: `.vault/exec/2026-05-27-schema-hardening-m193-standardization/2026-05-27-schema-hardening-m193-standardization-P01-S03.md`

## Description

The verification confirmed registered Modelo 193 casillas, bindings,
formulas, application-links, relations, and the row-builder coverage
all load from the fragment tree with no behaviour change. Loader
directory-mode tests confirmed single-file vs fragment-directory
equivalence, stale sibling detection, and TOML reviewability limits.

Reviewability baseline after the split:

- `193.toml` no longer exists.
- Modelo 193 has 15 TOML fragments.
- Largest Modelo 193 fragment: 72 lines (application_links).
- Five other fragments above 35 lines: bindings (65),
  relations (45), casillas (41), formulas (36).

## Tests

- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_modelo_193_registry.py src/aeat/domain/calculations/registry/test_loader_directory_mode.py -q`
- Result: 26 passed in 154 s.
