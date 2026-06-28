---
tags:
  - '#exec'
  - '#calculation-truth-registry'
date: '2026-05-05'
modified: '2026-05-05'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
  - '[[2026-05-05-calculation-truth-registry-phase2-step13-review-audit]]'
---



# `calculation-truth-registry` `phase2` `step13`

Removed filing and coverage authority from the declaración parser schema.

- Modified: `src/aeat/adapters/inbound/declaracion/__init__.py`
- Modified: `src/aeat/adapters/inbound/declaracion/_parser.py`
- Modified: `src/aeat/adapters/inbound/declaracion/_schema.py`
- Modified: `src/aeat/application/verification/_verify.py`
- Modified: `src/aeat/application/verification/test_verify.py`
- Modified: `.vault/plan/2026-05-03-calculation-truth-registry-rebuild-plan.md`
- Created: `.vault/audit/2026-05-05-calculation-truth-registry-phase2-step13-review.md`

## Description

The declaration parser now returns `DeclaracionObservation`, an observed PDF
value record. The previous filing-named aggregate and parser-owned extraction
status field were removed. Parser output carries provenance, template identity,
observed casilla values, and extraction warnings only.

Verification now consumes `DeclaracionObservation` and remains the layer that
loads the registry snapshot, resolves verification expectations, computes
coverage, and classifies discrepancies.

## Tests

- `uv run pytest src\aeat\adapters\inbound\declaracion src\aeat\application\verification -q`
  passed: 9 tests.
- `uv run ruff check src\aeat\adapters\inbound\declaracion src\aeat\application\verification`
  passed.
- `uv run ty check src\aeat\adapters\inbound\declaracion src\aeat\application\verification`
  passed.
