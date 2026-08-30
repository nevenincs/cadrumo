---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-30'
modified: '2026-08-30'
body_schema: 'body-v2'
body_hash: 'sha256:0f4d865419885b3ad278eedcdb4b99456c2beb60d9fd8e5acd8e5959bb2c640b'
step_id: 'S105'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# Keep ModeloCode on the review-package manifest and its CLI projection, both of which discarded the validated three-digit type for a hand-rolled one-to-eight string bound

## Scope

- `src/cadrumo/application/modelo/review_package.py`
- `src/cadrumo/entrypoints/cli/`

## Changes

- `M` `src/cadrumo/application/modelo/review_package.py`
- `M` `src/cadrumo/entrypoints/cli/_modelo_review_package_payloads.py`
- `M` `src/cadrumo/entrypoints/cli/tests/test_cli_payload_constraint_authority.py`
- `verify:` `pytest src/cadrumo/application/modelo/tests/test_modelo_work_review.py src/cadrumo/entrypoints/cli/tests/test_modelo_work_review_envelope.py -n 0 -m ""` -> `pass`

## Notes

`WorkUnit.modelo` is already `ModeloCode`, and the manifest was calling
`str(work_unit.modelo)` to downgrade it before restating a looser bound. The
JSON schema is unchanged -- still `{"type": "string"}` -- so the wire contract
holds while the validation behind it becomes the canonical three-digit check.

Two more fields ran the other way: the CLI already used `NonEmptyStr` where the
manifest restated `min_length=1`.
