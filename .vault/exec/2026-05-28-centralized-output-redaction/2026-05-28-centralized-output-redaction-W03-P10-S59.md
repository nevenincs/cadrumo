---
tags:
  - '#exec'
  - '#centralized-output-redaction'
date: '2026-06-02'
modified: '2026-07-17'
body_hash: 'sha256:2a3488810780d78e966d1d896f9fc89e114298f423ce7154907268f43118521b'
step_id: 'S59'
related:
  - "[[2026-05-28-centralized-output-redaction-plan]]"
---

# update modelo source-mesh tests for central redaction of identifiers

## Scope

- `src/aeat/entrypoints/cli/test_modelo_source_mesh_calculate.py`

## Description

- Validate `src/aeat/entrypoints/cli/test_modelo_source_mesh_calculate.py` against the centralized JSON output path.
- Reuse the S58 output-contamination repair: removing `DBG146` stderr probes restored parseable JSON for `work calculate` source-mesh output.

## Outcome

- `uv run pytest -q src/aeat/entrypoints/cli/test_modelo_source_mesh_calculate.py --tb=short -vv` passed: 1 passed.
- The source-mesh assertions continue to inspect the persisted calculation revision and compare public JSON observations against stored observation source refs.

## Notes

- This row depends on the same `work calculate` JSON emission contract as S58. The validation confirms source-mesh behavior after central output redaction without adding fakes, monkeypatching, or mirrored business logic.
