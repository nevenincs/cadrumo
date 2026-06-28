---
tags:
  - '#exec'
  - '#calculation-truth-registry'
date: '2026-05-05'
modified: '2026-05-05'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
  - '[[2026-05-05-calculation-truth-registry-phase2-step14-review-audit]]'
---


# `calculation-truth-registry` `phase2` `step14`

Removed concrete modelo examples from the generic fichero-BOE format layer.

- Modified: `src/aeat/adapters/outbound/aeat/export/_formats/__init__.py`
- Modified: `src/aeat/adapters/outbound/aeat/export/_formats/_record_spec.py`
- Modified: `src/aeat/adapters/outbound/aeat/export/_formats/_serialise.py`
- Modified: `src/aeat/adapters/outbound/aeat/export/_formats/_deserialise.py`
- Modified: `src/aeat/adapters/outbound/aeat/export/_formats/test_currency_edge_cases.py`
- Modified: `src/aeat/adapters/outbound/aeat/export/_formats/test_envelope.py`
- Modified: `src/aeat/adapters/outbound/aeat/export/_formats/test_record_spec.py`
- Modified: `.vault/plan/2026-05-03-calculation-truth-registry-rebuild-plan.md`
- Created: `.vault/audit/2026-05-05-calculation-truth-registry-phase2-step14-review.md`

## Description

The format layer now describes and tests generic fixed-width record and segment
primitives only. Concrete modelo layout facts, segment identifiers, sign
conventions, encodings, and optional segment decisions belong in reviewed
registry export definitions.

The reduced envelope tests now use neutral segment literals and still exercise
the same serialise/deserialise behaviour, duplicate guards, required-header
checks, and merged casilla views.

Review found that the generic tests do not yet load committed registry export
layouts, so the corresponding plan row was reopened. Review also removed the
non-authoritative default encoding fallback; callers must pass the
registry-selected encoding explicitly.

## Tests

- `uv run pytest src\aeat\adapters\outbound\aeat\export\_formats -q`
  passed: 100 tests.
- `uv run ruff check src\aeat\adapters\outbound\aeat\export\_formats`
  passed.
- `uv run ty check src\aeat\adapters\outbound\aeat\export\_formats`
  passed.
- Static text discovery over `src\aeat\adapters\outbound\aeat\export\_formats`
  found no concrete modelo identifiers in the active format layer.
