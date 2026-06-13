---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-14'
modified: '2026-05-14'
step_id: 'S06'
related:
  - '[[2026-05-14-cli-workflow-redesign-modelo-145-reopen-plan]]'
  - '[[2026-05-14-cli-workflow-redesign-modelo-145-reopen-adr]]'
  - '[[2026-05-14-cli-workflow-redesign-modelo-145-reopen-research]]'
---



# `cli-workflow-redesign` `P01.S01-S06`

Completed the Modelo 145 source and legal catalogue phase for the approved
local payer communication reopening.

- Created: `registry/aeat/legal/modelo-145.toml`
- Created: `corpus/aeat_official/instructions/modelo_145/files/modelo-145-procedure.html`
- Created: `corpus/aeat_official/instructions/modelo_145/files/modelo-145-obligaciones-retenedor.html`
- Created: `corpus/aeat_official/forms/modelo_145/files/mod145_es_es.pdf`
- Created: `corpus/aeat_official/disenos_registro/modelo_145/files/dr145v20.pdf`
- Created: `corpus/aeat_official/disenos_registro/modelo_145/manifest.json`
- Created: `corpus/normatives/html/boe-a-2011-208-modelo-145.html`
- Created: `corpus/normatives/html/boe-a-2014-59-modelo-145-amendment.html`
- Created: `corpus/normatives/html/boe-a-2014-13679-modelo-145-amendment.html`
- Created: `src/aeat/domain/calculations/registry/test_modelo_145_source_catalogue.py`

## Description

Added a dedicated Modelo 145 legal/source catalogue loaded by the shared
registry tree. The catalogue records reviewed BOE legal authority for the 2011
approval resolution and the 2013 and 2014 amendments, plus AEAT source
authority for G603, the non-electronic payer-processing obligations page, the
current form PDF, and the official record-design PDF.

The source entries are checksum-backed against local corpus files. The record
design has a per-modelo corpus manifest so the committed record-design manifest
test can verify the source entry without special cases.

Code review identified that checksum-only tests did not pin the ADR-critical
non-filing text or the official record-design marker. The tests now assert the
AEAT non-presentation, payer-side, and non-electronic source text and parse the
official record-design PDF to verify the `<T145010>` marker.

## Tests

Passed:

- `uv run --no-sync pytest -q src/aeat/domain/calculations/registry/test_modelo_145_source_catalogue.py src/aeat/domain/calculations/registry/test_catalogue_verification.py`
- `uv run --no-sync ruff check registry/aeat/legal/modelo-145.toml src/aeat/domain/calculations/registry/test_modelo_145_source_catalogue.py`
- `uv run --no-sync ty check src/aeat/domain/calculations/registry/test_modelo_145_source_catalogue.py`
- `uv run --no-sync vaultspec-core vault plan check .vault/plan/2026-05-14-cli-workflow-redesign-modelo-145-reopen-plan.md --json`
