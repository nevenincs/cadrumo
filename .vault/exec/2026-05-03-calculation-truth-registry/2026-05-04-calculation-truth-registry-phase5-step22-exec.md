---
tags:
  - '#exec'
  - '#calculation-truth-registry'
date: '2026-05-04'
modified: '2026-05-04'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
---

# `calculation-truth-registry` `phase5` `step22`

Moved spending-category profile authority out of runtime Python and into
committed registry TOML.

- Modified: `registry/aeat/categories/profiles/2025.toml`
- Modified: `src/aeat/domain/categories/_registry.py`
- Modified: `src/aeat/domain/categories/_corpus.py`
- Modified: `src/aeat/domain/categories/_proportionality.py`
- Modified: `src/aeat/domain/categories/__init__.py`
- Modified: `.vault/plan/2026-05-03-calculation-truth-registry-rebuild-plan.md`

## Description

Category profiles now load from `registry/aeat/categories/profiles/2025.toml`.
Runtime Python validates TOML shape, category coverage, decimal fields,
statutory caps, VAT hints, citations, and immutable registry exposure.

The previous manual-corpus entry point now resolves reviewed committed
registry data for the requested year and fails for unregistered years. Category
runtime documentation now describes stable registry-backed behaviour instead of
fallback behaviour.

Category tests now assert committed registry profile loading, coverage,
proportionality behaviour, and validation failures through public runtime
calls.

## Tests

- `uv run pytest src/aeat/domain/categories -q`
- `uv run ruff check src/aeat/domain/categories`
- `uv run ty check src/aeat/domain/categories`
