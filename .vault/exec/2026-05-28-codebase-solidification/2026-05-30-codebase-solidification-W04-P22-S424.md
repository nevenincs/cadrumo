---
step_id: "W04.P22.S424"
date: 2026-05-30
modified: '2026-05-30'
agent: coder-delta8
commit: e7f96f6ec
tags:
  - "#exec"
  - "#codebase-solidification"
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
---

# W04.P22.S424 — CounterpartSourceKind single canonical home

Domain version (`domain/calculations/registry/_bindings.py:1627`) includes
`"invoice"` plus the four specific source kinds — this is the broader set used
by `CounterpartAggregationObservation`. Application version was narrower (no
`"invoice"`); the 4-member restriction is enforced by `_CANONICAL_SOURCE_KINDS`
and `_validate_source_kind` at observation construction, not at the type alias.

Resolution: domain is canonical; application `_counterpart.py` imports from it.
Removed local `Literal[...]` definition and unused `from typing import Literal`.

**Files touched:** `src/aeat/application/aggregation/_counterpart.py`
