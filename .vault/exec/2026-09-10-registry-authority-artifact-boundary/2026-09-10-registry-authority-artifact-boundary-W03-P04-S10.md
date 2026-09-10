---
tags:
  - '#exec'
  - '#registry-authority-artifact-boundary'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:c4983c1a4c6802c6878536e2d4b5c6cd20278e1673be9dd1159dda8cad930e88'
step_id: 'S10'
related:
  - "[[2026-09-10-registry-authority-artifact-boundary-plan]]"
---
<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

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
