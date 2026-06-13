---
step_id: S119
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
  - '[[2026-05-27-centralized-module-drift-audit]]'
---

# codebase-solidification W01.P04.S119 — ReplayPayload typed envelope

## Outcome

Introduced `ReplayPayload(_ParityModel)` in `_live_parity.py` as the canonical
typed envelope for decoded replay JSON payloads. The model carries `observed:
Mapping[str, str]` and `raw_evidence_locator: str | None`, inheriting
`strict=True, frozen=True, extra="forbid"` from `_ParityModel`. Added
`get_logger` / `_log` to the module (first logger in this file). Updated
`decode_replay_json_payload` return type from `dict[str, Any]` to
`ReplayPayload`; removed `Any` from the typing import. Updated the three
callers (aeat_nif_iva, groi, renta_web_open replay drivers) to use attribute
access on the typed envelope, eliminating the now-redundant per-caller
isinstance guards.

## Files touched

- `src/aeat/domain/calculations/registry/_live_parity.py` (model + function)
- `src/aeat/domain/calculations/registry/_aeat_nif_iva_oracle.py` (caller updated)
- `src/aeat/domain/calculations/registry/_groi_oracle.py` (caller updated)
- `src/aeat/domain/calculations/registry/_renta_web_open_oracle.py` (caller updated)

## Collision check

`git diff` on all target files returned empty output before first edit — no
peer WIP in scope.

## Test outcome

28/28 passed: `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_live_parity.py -xvs`
