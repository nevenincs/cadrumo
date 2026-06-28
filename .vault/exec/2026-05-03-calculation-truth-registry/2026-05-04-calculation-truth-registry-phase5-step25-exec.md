---
tags:
  - '#exec'
  - '#calculation-truth-registry'
date: '2026-05-04'
modified: '2026-05-04'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
---

# `calculation-truth-registry` `phase5` `step25`

Tied declaration export and verify behaviour to registry snapshot export-layout
closure.

- Modified: `src/aeat/application/filing/_export.py`
- Modified: `src/aeat/application/filing/test_export.py`
- Modified: `.vault/plan/2026-05-03-calculation-truth-registry-rebuild-plan.md`

## Description

`export_draft` and `verify_export` now select the active registry-backed filing
subview before doing export work. They reject drafts built against a different
snapshot and fail closed when the selected registry snapshot declares no export
layout.

The tests exercise the current behaviour with a real registry-backed Modelo 130
draft. Since Modelo 130 currently has no export layout in committed TOML, export
raises a layout-coverage error and verify returns a `MISSING` verdict with the
file hash.

## Tests

- `uv run pytest src/aeat/application/filing/test_export.py -q`
- `uv run ruff check src/aeat/application/filing/_export.py src/aeat/application/filing/test_export.py`
- `uv run ty check src/aeat/application/filing/_export.py src/aeat/application/filing/test_export.py`
