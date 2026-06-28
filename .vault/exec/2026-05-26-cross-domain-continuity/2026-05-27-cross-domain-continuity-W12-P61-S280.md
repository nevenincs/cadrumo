---
step_id: S280
tags:
  - "#exec"
  - "#cross-domain-continuity"
date: 2026-05-27
modified: '2026-05-27'
related:
  - "[[2026-05-27-cross-domain-continuity-W12-P61-S279]]"
  - "[[2026-05-27-cross-domain-continuity-W12-P61-S278]]"
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# cross-domain-continuity W12.P61 — S280

## Objective

Eliminate 14 `cast()` type-erasure operations from workflow adapter and TOML
loader boundaries; document remaining legitimate `object` annotations inline.

## Sites addressed

### `workflow/_adapters.py` (6 cast calls)

| line (original) | original | replacement |
|---|---|---|
| 107 | `cast(ModeloProfile, profile)` | `profile  # type: ignore[arg-type]` + inline comment |
| 112 | `cast(RegistryModeloDraftProtocol, draft)` | `draft  # type: ignore[return-value]` + inline comment |
| 141 | `cast(AeatSession, session)` | `session  # type: ignore[arg-type]` + inline comment |
| 147 | `cast(AeatSession, session)` | `session  # type: ignore[arg-type]` + inline comment |
| 203 | `cast(ExpedientesSource, _live_expedientes_source)` | removed; helper return type narrowed |
| 204 | `cast(NotificationsSource, _live_notifications_source)` | removed; helper return type narrowed |

`_live_expedientes_source` return type narrowed to
`tuple[WorkflowExpedienteProtocol, ...]`; `_live_notifications_source` to
`WorkflowNotificationsSnapshotProtocol`. This eliminated the need for the
outer Protocol casts at the assignment sites.

### `registry/_loader.py` (1 cast call)

`cast("dict[str, object]", value)` after `isinstance(value, dict)` replaced
with `value  # type: ignore[return-value]`; docstring updated to clarify the
TOML deserialization boundary without referencing cast.

### `registry/_schema.py` (2 cast calls)

Already in HEAD from a prior peer commit — confirmed as pre-existing clean state.

### `object` field/parameter declarations (3 sites)

`review/_actions.py:18` (`split: object = None`), `_schedules.py:86`
(`current: object = ...`), and `workflow/_models.py:408`
(`get(..., default: object = None) -> object`) are all confirmed legitimate:
the first is a validation-trap parameter, the second is a traversal
accumulator, the third is the standard dict-protocol method signature.
No changes needed.

## Imports cleaned

- `workflow/_adapters.py`: removed `cast`, `ModeloProfile`, `ExpedientesSource`,
  `NotificationsSource`; added `WorkflowExpedienteProtocol`,
  `WorkflowNotificationsSnapshotProtocol`
- `registry/_loader.py`: removed `cast` from `typing` import

## Verification

`uv run --no-sync pytest src/aeat/application/workflow/ -x -q` (excluding
`test_engine.py` which has a pre-existing `_PreviousModeloSelector.relation`
failure from peer WIP) — 52 passed.

`ruff check` on `_adapters.py` and `_loader.py` — clean.

## Commit

`be7a18a8b` — W12.P61.S280: eliminate cast() type-erasure at workflow adapter and TOML loader boundaries
