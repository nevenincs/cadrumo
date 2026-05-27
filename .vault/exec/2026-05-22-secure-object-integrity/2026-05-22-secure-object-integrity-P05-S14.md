---
tags:
  - '#exec'
  - '#secure-object-integrity'
date: '2026-05-22'
step_id: 'S14'
related:
  - '[[2026-05-22-secure-object-integrity-attribution-plan]]'
---

<!-- DO NOT add 'Related:', 'tags:', 'date:', or other frontmatter fields
     outside the YAML frontmatter above -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path
     (e.g., S03 at L1, P02.S03 at L2, W01.P02.S03 at L3 / L4). The
     step_id frontmatter field below carries the canonical identifier;
     the heading restates the display path as a reading hint. -->

# `secure-object-integrity` `P05.S14`

Updated the new config repair attribution help text through the locale module CLI and verified locale catalogue parity.

- Modified: `src/aeat/locales/en.yml`
- Modified: `src/aeat/locales/es.yml`
- Modified: `src/aeat/locales/ca.yml`
- Modified: `src/aeat/locales/hu.yml`
- Created: `.vault/audit/2026-05-22-secure-object-integrity-P05-S14-review.md`

## Description

The locale workflow used `uv run python -m aeat.locales audit` to detect that `cli.config.repair.integrity_attribution_help` was missing from all locale catalogues. The key was then added through `uv run python -m aeat.locales scaffold`, which produced scaffolded entries in English, Spanish, Catalan, and Hungarian.

The scaffold placeholders were replaced with locale-specific text describing the command's metadata-only grouping of undecryptable secure-object rows. The wording avoids payload disclosure promises beyond the command's safe metadata contract and stays aligned with the attribution behavior implemented earlier in the plan.

## Tests

Focused gates passed:

- `uv run python -m aeat.locales audit`
- `uv run python -m aeat.locales scaffold --check`
- `uv run ruff check src/aeat/entrypoints/cli/_config/__init__.py`

Mandatory scoped review found no critical or high blockers.

Review audit: `2026-05-22-secure-object-integrity-P05-S14-review`.
