---
tags: ["#exec", "#declaracion-extraction-architecture"]
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'W02.P12.S68'
related:
  - '[[2026-05-21-declaracion-extraction-architecture-plan]]'
  - '[[2026-05-21-declaracion-extraction-architecture-adr]]'
---

# `declaracion-extraction-architecture` `W02.P12.S68`

TOML stanza migration: all 20 registry `target_casillas` stanzas migrated
from flat `casilla-id` string lists to `ExtractionTargetDefinition`
inline-table array form. Covers steps S49 through S68.

- Modified: `src/aeat/_data/registry/aeat/modelos/115.toml`
- Modified: `src/aeat/_data/registry/aeat/modelos/130.toml`
- Modified: `src/aeat/_data/registry/aeat/modelos/184.toml`
- Modified: `src/aeat/_data/registry/aeat/modelos/190.toml`
- Modified: `src/aeat/_data/registry/aeat/modelos/193.toml`
- Modified: `src/aeat/_data/registry/aeat/modelos/347.toml`
- Modified: `src/aeat/_data/registry/aeat/modelos/349.toml`
- Modified: `src/aeat/_data/registry/aeat/modelos/720.toml`
- Modified: `src/aeat/_data/registry/aeat/modelos/840.toml`
- Modified: `src/aeat/_data/registry/aeat/modelos/111/revisions/2019-y-siguientes/extraction_profiles/0005-extraction_profiles.toml`
- Modified: `src/aeat/_data/registry/aeat/modelos/123/revisions/2019-2023/revision.toml`
- Modified: `src/aeat/_data/registry/aeat/modelos/123/revisions/2024-y-siguientes/revision.toml`
- Modified: `src/aeat/_data/registry/aeat/modelos/131/revisions/2019-2023.toml`
- Modified: `src/aeat/_data/registry/aeat/modelos/131/revisions/2024.toml`
- Modified: `src/aeat/_data/registry/aeat/modelos/131/revisions/2025.toml`
- Modified: `src/aeat/_data/registry/aeat/modelos/131/revisions/2026.toml`
- Modified: `src/aeat/_data/registry/aeat/modelos/180/revisions/2019-2022/extraction_profiles/0001-modelo-180-export-record.toml`
- Modified: `src/aeat/_data/registry/aeat/modelos/180/revisions/2023-y-siguientes/extraction_profiles/0001-modelo-180-export-record.toml`
- Modified: `src/aeat/_data/registry/aeat/modelos/232/revisions/2016-2017/extraction_profiles/0001-modelo-232-2016-declaracion-pdf.toml`
- Modified: `src/aeat/_data/registry/aeat/modelos/232/revisions/2018-y-siguientes/extraction_profiles/0001-modelo-232-2018-declaracion-pdf.toml`

## Description

Every `target_casillas` stanza that previously held a flat list of bare
casilla-id strings was rewritten to use TOML inline tables in the form
`{casilla_id = "NN", match_strategy = "numeric_casilla", value_kind = "amount"}`.

Numeric casillas (modelos 111, 115, 123, 130, 131, 180) all use
`match_strategy = "numeric_casilla"` and `value_kind = "amount"`.

Dead-stub modelos (184, 190, 193, 347, 349, 720, 840) whose `decl.*`
slug targets are non-matchable were migrated to the inline-table form
using `numeric_casilla` as a placeholder strategy; W04 will replace these
with real targets once the dead-stub classification Step (S80) and
per-modelo decisions (P14) are executed.

Modelo 232 `decl.cnae` targets use `match_strategy = "named_label"` and
`value_kind = "text"` with `label_pattern = 'C\\.N\\.A\\.E\\.?\\s+de\\s+la\\s+actividad\\s+principal'`
because `decl.cnae` has `data_type = "text"` and the text-casilla gate
now enforces `named_label` for `text`-typed casillas.

Registry loads 26 modelos successfully after migration.

## Tests

`uv run pytest -q src/aeat/domain/calculations/registry/` passed with 141 tests confirming all 26 modelos load and validate.
