---
tags: ["#exec", "#registry-authority-flow"]
date: '2026-05-21'
modified: '2026-07-17'
body_hash: 'sha256:4334a6ba4b08596f70b518d85a3831afc7101a6746922ab62d8751ed980cc0be'
step_id: 'S21'
related:
  - '[[2026-05-20-registry-authority-flow-plan]]'
---

# `registry-authority-flow` `W05.P09.S21`

Cleaned package-wide registry ruff residuals.

- Modified: `src/aeat/domain/calculations/registry`
- Created: this execution record

## Description

Applied mechanical ruff import ordering and unused-import cleanup across the registry package files that were blocking `uv run ruff check src/aeat/domain/calculations/registry`.

## Tests

`uv run ruff check src/aeat/domain/calculations/registry` passed. A focused data-type test slice passed with 155 tests.
