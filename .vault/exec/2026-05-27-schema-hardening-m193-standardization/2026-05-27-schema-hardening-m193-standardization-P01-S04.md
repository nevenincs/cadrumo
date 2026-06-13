---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-27'
modified: '2026-05-27'
step_id: 'S04'
related:
  - '[[2026-05-27-schema-hardening-m193-standardization-plan]]'
---



# `schema-hardening-m193-standardization` `P01.S04`

Records the Modelo 193 standardization review outcome, the post-split
reviewability baseline, and the next single-file normalization edge.

- Modified: `.vault/plan/2026-05-27-schema-hardening-m193-standardization-plan.md`
- Created: `.vault/exec/2026-05-27-schema-hardening-m193-standardization/2026-05-27-schema-hardening-m193-standardization-P01-S04.md`

## Description

The S01 inventory mapped the M193 single-file source into a 15-fragment
directory layout matching the established loader contract. The S02
mechanical split landed `manifest.toml` plus the
`revisions/2024-y-siguientes/` fragment tree without altering any
casilla, binding, formula, application-link, or detail-record row
builder. The S03 verification confirmed loader equivalence,
referential integrity, the annual-summary relation behaviour, and
the detail-record row-set assembly + round-trip all hold from the
fragment layout (26 tests passed).

Post-split reviewability baseline: 15 TOML fragments, largest 72
lines (application_links), no fragment over the per-fragment
reviewability ceiling. The original `193.toml` is removed; the
fragment tree is the canonical M193 source.

The remaining single-file modelos under the root registry tree are
`347.toml` (373 lines), `309.toml` (363), `360.toml` (324),
`036.toml` (300), `308.toml`, and `840.toml`. `347.toml` is the
largest and therefore the next single-file normalization edge; the
same mechanical split strategy (inventory -> manifest + revisions
split -> directory-loader verification -> baseline record) carries
over with no contract change required.

## Tests

- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_modelo_193_registry.py src/aeat/domain/calculations/registry/test_loader_directory_mode.py -q`
- Result: covered by the S03 verification pass (26 passed) — no
  additional tests required at the standardization-record step.
