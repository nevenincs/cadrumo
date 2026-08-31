---
tags:
  - '#exec'
  - '#test-reconciliation-sweep'
date: '2026-08-28'
modified: '2026-08-28'
body_schema: 'body-v2'
body_hash: 'sha256:4e7f2e756213d04c4a996d30caf1e6e0e2a061957946dbbbe15b3ad1b0e0bb8a'
step_id: 'S03'
related:
  - "[[2026-08-28-test-reconciliation-sweep-plan]]"
---

# Give the M303 filing-evidence document one canonical test-side home and pass it on every M303 calculate invocation

## Scope

- `src/cadrumo/entrypoints/cli/tests/`

## Changes

- `A` `src/cadrumo/entrypoints/cli/tests/_m303_filing_evidence_support.py`
- `M` `src/cadrumo/entrypoints/cli/tests/test_m303_filing_evidence_creation_contract.py`
- `M` `src/cadrumo/entrypoints/cli/tests/test_modelo_source_mesh_calculate.py`
- `verify:` `pytest src/cadrumo/entrypoints/cli/tests/test_m303_filing_evidence_creation_contract.py` -> `pass`
