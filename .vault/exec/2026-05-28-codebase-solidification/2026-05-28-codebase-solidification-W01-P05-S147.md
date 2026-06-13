---
step_id: S147
tags:
  - "#exec"
  - "#codebase-solidification"
date: 2026-05-28
modified: '2026-05-28'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
  - "[[2026-05-27-centralized-module-drift-audit]]"
---

# codebase-solidification W01.P05.S147 — reconcile `_parse_bool` signatures

## Outcome

Canonical `_parse_bool(raw: str | None) -> bool | None` placed at
`src/aeat/core/parsing/_utils.py`. Local copies deleted from
`_profiles.py` (returned `bool`) and `_censo.py` (returned `bool | None`).

## Signature decision

`bool | None` chosen. `None` for absent/unrecognisable tokens lets each
call-site pick its own fallback without silently coercing garbage to
`False`. The `_censo.py` call-site already consigned to `bool | None`
(field `CensoFactSet.fiscal_address_is_habitual_vivienda: bool | None`).
The `_profiles.py` call-site assigns to `TaxpayerProfile.fiscal_address_is_habitual_vivienda: bool = False`;
the `None` case is coerced at the call-site with `... or False`.

## Files touched

- `src/aeat/core/parsing/__init__.py` — created (new package)
- `src/aeat/core/parsing/_utils.py` — created (canonical implementation)
- `src/aeat/domain/deadlines/_profiles.py` — local `_parse_bool` deleted; import added; call-site guarded with `or False`
- `src/aeat/adapters/outbound/aeat/sede/_censo.py` — local `_parse_bool` deleted; import added

## Collision signal

`git diff` on both source files returned empty before edit — no non-authored WIP.

## Test outcomes

`uv run --no-sync pytest src/aeat/core/parsing/test_utils.py src/aeat/adapters/outbound/aeat/sede/test_census_parser.py -v -m "unit or live_read"` — 51 passed, 0 failed.
