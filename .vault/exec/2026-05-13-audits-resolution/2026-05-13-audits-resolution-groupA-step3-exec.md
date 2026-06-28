---
tags:
  - '#exec'
  - '#audits-resolution'
date: '2026-05-13'
modified: '2026-05-13'
related:
  - "[[2026-05-13-audits-resolution-plan]]"
  - "[[2026-05-13-eliminate-shims-audit]]"
---

# audits-resolution group-a step-3

## scope

Plan row A3: confirm the sede `_STRICT_FROZEN` aliases actually carry
`strict=True`.

## verification

Reading the live source:

- `src/aeat/adapters/outbound/aeat/sede/_schema.py:26-30` — the
  alias is `ConfigDict(strict=True, frozen=True, extra="forbid")`.
- `src/aeat/adapters/outbound/aeat/sede/_declarations.py:114-118` —
  same shape.
- `src/aeat/adapters/outbound/aeat/sede/_notifications.py:55-59` —
  same shape.

The audit's flag against the sede cluster was already resolved by an
earlier slice on this branch — every record that inherits
`_STRICT_FROZEN` carries the strictness triple at HEAD.

`grep -n 'strict=True' src/aeat/adapters/outbound/aeat/sede/_schema.py`
returns line 27 (the alias's `strict=True` line).

`pytest src/aeat/adapters/outbound/aeat/sede/ -q` returns 141 passed
plus one concurrent-agent failure in
`test_declarations.py::TestFiledObservationRelations::test_modelo_100_relations_resolve_from_standardized_filed_observations`
that arises from a registry-renta wiring change owned by another
stream. Flagged for the orchestrator; not in audits-resolution scope.

No code change required for this step.
