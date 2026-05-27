---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-05-27'
step_id: 'S306'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-05-27-observability-store-persistence-closeout-audit]]'
---

<!-- DO NOT add 'Related:', 'tags:', 'date:', or other frontmatter fields
     outside the YAML frontmatter above -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the body. If you must name a source file,
       class, or function, use inline `code`. -->

# `secure-storage-production-hardening` `W12.P26.S306`

Closed the observability recorder plaintext-exception review for AFR-204.

## Changes

- Confirmed `record_event` raises registered `RunContextMissingError` when no run context is active.
- Confirmed recorder output stays structured through logging `extra` and does not bypass the sink/store persistence path.

## Validation

- `uv run ruff check` on the touched observability and error-registry slice.
- `uv run pytest` on observability store/model/context tests plus error-registry contract tests.
- `uv run python -m aeat.locales audit`
