---
tags:
  - '#exec'
  - '#calculation-truth-registry'
date: '2026-05-05'
modified: '2026-05-05'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
---



# `calculation-truth-registry` `Phase 2` `Step 18`

Cleaned the categories CLI boundary so it exposes year-keyed factual category
profiles without filing-target or casilla projection semantics.

- Modified: `src/aeat/entrypoints/cli/categories.py`
- Modified: `src/aeat/locales/en.yml`
- Modified: `src/aeat/locales/es.yml`
- Modified: `.vault/plan/2026-05-03-calculation-truth-registry-rebuild-plan.md`

## Description

The categories CLI no longer imports the convenience `CATEGORY_PROFILES_2025`
mapping. Operators must pass `--year`, and the command resolves the exact
committed category profile registry for that year. This avoids embedding a
current-year assumption in the CLI layer while keeping the command factual and
read-only.

The command payload remains limited to category identity, category family, and
proportionality profile data. It does not expose modelo, casilla, filing target,
or calculation authority.

## Tests

- `uv run python -` with `CliRunner` invoking `categories list --year 2025`
- `uv run ruff check src\aeat\entrypoints\cli\categories.py`
- `uv run ty check src\aeat\entrypoints\cli\categories.py`
