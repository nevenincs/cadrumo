---
tags:
  - '#exec'
  - '#claude-ecosystem-packaging'
date: '2026-07-03'
modified: '2026-07-17'
step_id: 'S08'
related:
  - "[[2026-07-03-claude-ecosystem-packaging-plan]]"
---

# Exclude _data/corpus source binaries (*.pdf, *.xls, *.xlsx) from the aeat wheel via hatchling wheel excludes

## Scope

- `pyproject.toml`

## Description

- Add hatchling wheel excludes for `_data/corpus/**/*.pdf`, `**/*.xls`, `**/*.xlsx` in `pyproject.toml` so the published `aeat` wheel carries zero corpus source binaries.
- Absorb the in-scope consumer-gate fallout atomically in the same commit: `test_wheel_bundles_corpus_and_registry.py` and `smoke_core.py` expected-path lists now exclude the corpus binaries, and the Renta-PDF presence assertion is inverted to prove absence instead.
- Commit `0dbb97ddc6`.

## Outcome

- Measured slim wheel: 39.16 MB (down from 171.8 MB), zero corpus binaries, 18798 members (414 extracted markdown, 319 normative HTML, 16014 registry, 63 agent).

## Notes

No incidents. No skipped work.
