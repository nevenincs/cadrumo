---
tags:
  - '#exec'
  - '#calculation-truth-registry'
date: '2026-05-05'
modified: '2026-05-05'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
  - '[[2026-05-03-calculation-truth-registry-pending-adr]]'
---



# `calculation-truth-registry` `Wave 4` `Modelo 123 registry foundation`

Established the Modelo 123 registry foundation for the 2024-and-later and
2019-through-2023 record designs.

- Created: `registry/aeat/modelos/123.toml`
- Modified: `registry/aeat/legal/irpf.toml`
- Created: `corpus/aeat_official/instructions/modelo_123/files/modelo-123-procedure.html`
- Created: `corpus/normatives/html/orden-eha-3435-2007.html`
- Created: `corpus/normatives/html/orden-hac-56-2024.html`
- Modified: `src/aeat/domain/calculations/registry/test_committed_registry.py`
- Modified: `src/aeat/application/filing/test_export.py`
- Modified: `src/aeat/application/filing/runtime.py`
- Modified: `src/aeat/domain/calculations/registry/_schema.py`
- Modified: `src/aeat/domain/deadlines/_models.py`
- Modified: `src/aeat/domain/deadlines/test_engine.py`
- Modified: `src/aeat/application/setup/_models.py`
- Modified: `src/aeat/application/setup/_env_writer.py`
- Modified: `.vault/plan/2026-05-03-calculation-truth-registry-rebuild-plan.md`

## Description

Wave 4 started with a grounded pass over the official Modelo 123 surfaces. AEAT
exposes separate presentation entries for 2024 and later and for 2020 through
2023. The current official record-design workbook is layout authority, not an
executable calculation oracle. LibreOffice conversion succeeded and classified
the 2024-and-later and 2019-through-2023 workbooks as `record_design_layout`.

The 2024-and-later registry defines the current fourteen-casilla structure:
dividend/participation rent count, other-rent count, total count, matching base
and withholding splits, periodification fields, total liquidation, prior
autoliquidation result, and payable amount. The implemented formula surface is
aggregation-only: `03 = 01 + 02`, `06 = 04 + 05`, `09 = 07 + 08`,
`12 = 09 + 11`, and `14 = 12 - 13`. No per-income withholding rate was inferred
from the record design.

The shared catalogue now carries BOE legal authority for Orden EHA/3435/2007
Anexo II and Orden HAC/56/2024 article first, plus AEAT/BOE source references
for the current procedure page, record-design workbook, and form text evidence.
The registry snapshot includes export layout, strict export/declaration
extraction profiles, static official remote-state guard, workbook layout
classification, verification expectations, and application links for
calculation, filing, export, verification, review, extraction, portal
cross-reference, and workflow use.

The authenticated read-only declaration register scan for Modelo 123 from 2020
through 2026 returned zero rows. Live sanitized fixture and filed-data parity
tests remain open because there is no live Modelo 123 artefact available in the
scanned account and period range.

Historical 2019-through-2023 layout material is now represented as an explicit
registry revision with the eight-casilla shape from the official record design:
retention count, base, withholding amount, periodification fields, total
liquidation, prior autoliquidation result, and payable amount. Its implemented
formula surface is `06 = 03 + 05` and `08 = 06 - 07`. The historical revision
now also carries its own export layout records and a behavior test that builds
a 2023 draft, calculates the derived casillas, writes the official
eight-casilla payload, and parses it back through the selected registry layout.

Adding Modelo 123 as the first multi-revision filing registry exposed a runtime
provider defect: the default filing schema provider assumed every modelo had
one revision. The provider now selects the current open-ended revision
deterministically when callers do not request a specific filing period, and
period-specific snapshot selection remains available for historical filings.

The remaining applicability gap was closed with a first-class
`pays_capital_income_with_retencion` profile flag. Modelo 123 now has four 2026
registry deadline windows gated by that condition, and the setup profile writer
persists the field into the encrypted profile envelope. Deadline behavior tests
prove the model is not applicable by default and becomes applicable only when
the profile declares capital-income withholding payments.

The active source/test registry scan found no remaining non-registry Modelo 123
filing-grade authority in Python rulesets, category mappings, casilla
projections, deadline logic, hydrate paths, or generated export code. Remaining
source hits are the new registry/catalogue definitions, portal metadata, and
behavior tests.

## Tests

- `uv run aeat app registry verify --registry-root registry\aeat --source-root . --json`
- `uv run pytest src\aeat\application\filing\test_export.py src\aeat\domain\calculations\registry\test_committed_registry.py -q`
- `uv run pytest src\aeat\domain\calculations\registry\test_committed_registry.py src\aeat\application\filing\test_export.py src\aeat\domain\calculations\registry\test_remote_state_guard.py -q`
- `uv run pytest src\aeat\domain\deadlines\test_engine.py src\aeat\domain\deadlines\test_models.py src\aeat\application\setup\test_env_writer.py src\aeat\application\setup\test_models.py -q`
- `uv run pytest src\aeat\domain\calculations\registry\test_committed_registry.py src\aeat\application\filing\test_export.py src\aeat\domain\calculations\registry\test_remote_state_guard.py src\aeat\domain\deadlines\test_engine.py src\aeat\domain\deadlines\test_models.py src\aeat\application\setup\test_env_writer.py src\aeat\application\setup\test_models.py -q`
- `uv run ruff check src\aeat\application\filing\runtime.py src\aeat\domain\calculations\registry\_schema.py src\aeat\domain\calculations\registry\test_committed_registry.py src\aeat\application\filing\test_export.py src\aeat\domain\deadlines\_models.py src\aeat\domain\deadlines\test_engine.py src\aeat\application\setup\_models.py src\aeat\application\setup\_env_writer.py`
- `uv run ty check src\aeat\application\filing\runtime.py src\aeat\domain\calculations\registry\_schema.py src\aeat\domain\calculations\registry\test_committed_registry.py src\aeat\application\filing\test_export.py src\aeat\domain\deadlines\_models.py src\aeat\domain\deadlines\test_engine.py src\aeat\application\setup\_models.py src\aeat\application\setup\_env_writer.py`
- `uv run aeat app registry list-filed-data --modelo 123 --from-year 2020 --to-year 2026 --json`
- `uv run aeat app registry list-filed-data --modelo 115 --from-year 2020 --to-year 2026 --json`
- `git diff --check -- registry\aeat\modelos\123.toml registry\aeat\legal\irpf.toml src\aeat\domain\calculations\registry\test_committed_registry.py src\aeat\application\filing\test_export.py corpus\aeat_official\instructions\modelo_123\files\modelo-123-procedure.html corpus\normatives\html\orden-eha-3435-2007.html corpus\normatives\html\orden-hac-56-2024.html`
