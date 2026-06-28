---
name: 2026-04-13-modelo-inventory-phase4-entries
description: Phase 4 execution record — populate 20 modelo registry entries (#108)
type: exec
tags:
  - "#exec"
  - "#modelo-inventory"
date: 2026-04-13
modified: '2026-04-13'
related:
  - "[[2026-04-13-modelo-inventory-plan]]"
  - "[[2026-04-13-modelo-inventory-research]]"
---

# phase 4 — populate registry entries

## delivered

- Added `src/aeat/domain/modelos/_entries/_common.py` with `build_entry`,
  `build_applicability`, `make_citation` helpers to reduce boilerplate
  across entry modules. `make_citation` routes through
  `LegalCitation.model_validate(...)` so the helper's declared
  `url: str | None` parameter does not clash with `HttpUrl | None` at
  the pydantic boundary.
- Populated all 20 entry modules with authoritative data from the
  research doc §3: `modelo_036`, `modelo_037`, `modelo_100`,
  `modelo_111`, `modelo_115`, `modelo_123`, `modelo_130`, `modelo_131`,
  `modelo_180`, `modelo_190`, `modelo_200`, `modelo_202`, `modelo_232`,
  `modelo_303`, `modelo_347`, `modelo_349`, `modelo_369`, `modelo_390`,
  `modelo_720`, `modelo_840`.
- Every entry carries non-empty `legal_basis`, a complete trilingual
  `display_label`, a partitioned `ModeloApplicability` built from the
  research D2 matrix, and at least one `known_gotchas` entry.
- `caps_into` values: 130→100, 131→100, 111→190, 115→180, 202→200,
  303→390. 123 stores `None` with a gotcha flagging that modelo 193 is
  absent from the v1 registry, as recorded in the plan's `caps_into`
  gap mitigation.
- 202 categorised as `QUARTERLY` with the three-periods nuance in
  `trigger_notes_es` / `known_gotchas`, matching the plan.

## gate outcomes

- `just lint` — initially flagged 1 UP035 + 1 I001 + 3 RUF001 en-dash
  warnings; fixed by switching `Sequence` to `collections.abc`, fixing
  modelo_369 import order, and replacing en-dashes with hyphen-minus
  in modelo_123/modelo_840. Re-run passed.
- `just typecheck` — initially failed because the raw
  `LegalCitation(url=...)` constructor expected `HttpUrl | None`;
  fixed by routing through `model_validate` in `make_citation`.
  Re-run passed.
- `just test` — 740 passed, 1 skipped, 23 deselected.
- `just hooks` — initially triggered ruff-format which reformatted
  11 files; re-run passed cleanly.

## deviations

None material. Ruff and ruff-format cleanup were stylistic only.

## commit

`3f3817e feat(models): populate registry with 20 modelo metadata entries (#108)`
