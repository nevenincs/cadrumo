---
tags:
  - "#exec"
  - "#p2a-financial-provider"
date: "2026-04-13"
modified: '2026-04-13'
related:
  - "[[2026-04-13-p2a-financial-provider-plan]]"
---

# `p2a-financial-provider` `phase-1` `task-1`

Implemented the new T1 financial ingest package and provider surface.

- Modified: `pyproject.toml`
- Modified: `src/aeat/config.py`
- Created: `src/aeat/domain/financial/`
- Created: `src/aeat/domain/financial/providers/`

## Description

Created the public `aeat.domain.financial` package, the strict frozen `RawTransaction` and `RawProvenance` models, the `FinancialProvider` ABC, typed provider validation records, CSV/XLSX/OFX providers, and provider auto-detection. The implementation keeps the T1 contract file-based and provenance-first, uses deterministic synthetic transaction identifiers when no external ID exists, and keeps the public import surface rooted at `aeat.domain.financial` and `aeat.domain.financial.providers`.

## Tests

Verified the new provider modules with focused `pytest`, `ruff`, and `ty` runs before moving to branch-wide gates.
