---
tags:
  - '#exec'
  - '#registry-authority-artifact-boundary'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:cbde295d1b75856ea7da3207ccdd2a45bedc2978b2ea7e703b29ab1be167b905'
step_id: 'S10'
related:
  - "[[2026-09-10-registry-authority-artifact-boundary-plan]]"
---

# Project runtime provenance and inspection data into signed authority artifacts

## Scope

- `src/cadrumo/domain/calculations/registry/authority_artifact.py`

## Changes

- `M` `src/cadrumo/domain/calculations/registry/authority_artifact.py`
- `M` `src/cadrumo/domain/calculations/registry/static_inspection.py`
- `M` `src/cadrumo/application/filing/_export_parity.py`
- `M` `src/cadrumo/application/modelo/_work_review_assembly.py`
- `A` `src/cadrumo/application/filing/tests/test_signed_evidence_xml_components.py`
- `verify:` `uv run pytest -n 0 src/cadrumo/application/filing/tests/test_signed_evidence_xml_components.py src/cadrumo/domain/calculations/registry/tests/test_bundled_authority_artifact_runtime.py` -> `pass`
