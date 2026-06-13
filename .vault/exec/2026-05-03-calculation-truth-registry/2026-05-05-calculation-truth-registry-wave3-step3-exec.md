---
tags:
  - '#exec'
  - '#calculation-truth-registry'
date: '2026-05-05'
modified: '2026-05-05'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
  - '[[2026-05-03-calculation-truth-registry-pending-adr]]'
  - '[[2026-05-04-calculation-authority-evidence-tiering-adr]]'
  - '[[2026-05-04-live-filing-data-capture-adr]]'
---



# `calculation-truth-registry` `Wave 3` `Modelo 115 verification boundary`

Added Modelo 115 application verification coverage on top of the committed
registry definition.

- Modified: `src/aeat/application/filing/test_export.py`
- Modified: `src/aeat/application/verification/test_verify.py`
- Modified: `.vault/plan/2026-05-03-calculation-truth-registry-rebuild-plan.md`

## Description

`verify_export` now has a Modelo 115 behaviour test that exports an approved
draft through the committed record-design layout, re-reads the generated
payload, and verifies that the exported casillas still match the approved
draft.

`verify_declaracion` now has a Modelo 115 behaviour test that builds a parsed
declaration observation for casillas 01 through 05 and verifies it against the
committed registry calculation expectation. The test uses the registry
snapshot and public verification API; it does not define a local schema,
formula, or calculation fixture.

The plan now records the Modelo 115 export-verification and
declaration-verification boundaries under the Wave 3 export/filing linkage row.
The live sanitized fixture and live filed-data parser rows remain open until a
read-only AEAT declaration artefact is available.

## Tests

- `uv run ruff check src\aeat\application\verification\test_verify.py src\aeat\application\filing\test_export.py`
- `uv run ty check src\aeat\application\verification\test_verify.py src\aeat\application\filing\test_export.py`
- `uv run pytest src\aeat\application\verification\test_verify.py src\aeat\application\filing\test_export.py -q`
