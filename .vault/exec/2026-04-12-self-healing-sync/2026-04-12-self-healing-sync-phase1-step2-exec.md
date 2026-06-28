---
tags:
  - "#exec"
  - "#self-healing-sync"
date: 2026-04-12
modified: '2026-04-12'
related:
  - "[[2026-04-12-self-healing-sync-plan]]"
  - "[[2026-04-12-self-healing-sync-adr]]"
---

# step 2 — divergence types + semantic classifier

- `_divergence.py`: `DivergenceClassification`, `DivergenceKind`,
  `ResolutionState` StrEnums; concrete frozen pydantic v2 payload
  members for every divergence kind; `DivergencePayload` discriminated
  union via `Field(discriminator="kind")`; `DivergenceRecord`
  persistable model; static `MappingProxyType` classification table
  decoupling kind from bucket.
- `_classifier.py`: `DivergenceClassifier` with per-field semantic
  comparators over wire shapes (`diff_modelo`,
  `diff_portal_manifest`, `diff_filing_history`). Emits wrapped
  `DivergenceRecord`s with UTC timestamps and UUID4 record ids.
- `test_classifier.py`: one parametrised-ish case per kind covering
  every classification bucket plus a "no divergence" baseline.

18 unit tests green.
