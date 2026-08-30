---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-29'
modified: '2026-08-29'
body_schema: 'body-v2'
body_hash: 'sha256:31cabf7522690b8e1fdbe164bbdee8cba91847c1c940750416864056637d0ec0'
step_id: 'S02'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# Promote the canonical evidence-reference and amendment-reason aliases to public defining modules and dedupe the twice-declared discard-reason alias

## Scope

- `src/cadrumo/domain/modelos/`

## Changes

- `A` `src/cadrumo/domain/modelos/filing_text.py`
- `M` `src/cadrumo/domain/modelos/calculation_revision.py`
- `M` `src/cadrumo/domain/modelos/_work_unit.py`
- `M` `src/cadrumo/domain/modelos/_verification_report.py`
- `M` `src/cadrumo/domain/modelos/_filing_record.py`
- `verify:` `uv run --no-sync pytest src/cadrumo/domain/modelos/tests` -> `pass`
