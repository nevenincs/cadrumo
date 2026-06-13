---
tags: ["#exec", "#registry-authority-flow"]
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'S23'
related:
  - '[[2026-05-20-registry-authority-flow-plan]]'
  - '[[2026-05-20-registry-authority-flow-adr]]'
  - '[[2026-05-20-registry-authority-flow-research]]'
---

# `registry-authority-flow` `W05.P10.S23`

Split oversized Modelo 200 export and construct fragments.

- Modified: `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/export`
- Modified: `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/records/constructs.part-001.toml`
- Created: additional M200 export and construct continuation fragments

## Description

Mechanically split the M200 export and construct TOML fragments that exceeded
1,500 lines, preparing the later fragment-size threshold reduction without
changing registry semantics. Export fragments were split at
`export_layouts.records.fields` table boundaries. Continuation fragments repeat
only the merge keys needed by the loader: the export layout id and record id.
Construct fragments were split at `casillas` list boundaries. Continuation
fragments repeat only the construct id and append additional `casillas` through
the existing construct-fragment merge path.

The split touched 23 M200 export files and one M200 construct file. The largest
M200 export/construct fragment after the split is 1,500 lines, and no M200
export or construct fragment remains above the S23 target.

The full committed reviewability gate is not claimed by this Step because that
gate currently reports two out-of-scope Modelo 100 manifest rows over the
600-character row limit. That residual belongs to the later verification and
residual-hygiene tracking rows, not to this M200 export/construct split.

## Tests

`uv run pytest -q src/aeat/domain/calculations/registry/test_modelo_200_registry.py src/aeat/domain/calculations/registry/test_loader_directory_mode.py::test_fragmented_revision_directories_are_schema_owned` passed: 8 tests.

`uv run python -c "from aeat.core.resources import bundled_path; from aeat.domain.calculations.registry import load_modelo_directory; m=load_modelo_directory(bundled_path('registry','aeat','modelos','200')); r=m.revisions['2024-y-siguientes']; print(m.id, r.id, len(r.export_layouts), sum(len(layout.records) for layout in r.export_layouts), sum(len(record.fields) for layout in r.export_layouts for record in layout.records), len(r.constructs), len(r.constructs[0].casillas))"` printed `200 2024-y-siguientes 1 77 6531 1 3215`.

`uv run pytest -q src/aeat/domain/calculations/registry/test_export.py src/aeat/domain/calculations/registry/test_export_layout_encoding.py src/aeat/domain/calculations/registry/test_export_parse.py` passed: 72 tests.

`uv run pytest -q src/aeat/domain/calculations/registry/test_modelo_200_registry.py src/aeat/domain/calculations/registry/test_modelo_parity_coverage.py` passed: 8 tests.

`git diff --check -- src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/export src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/records` passed.
