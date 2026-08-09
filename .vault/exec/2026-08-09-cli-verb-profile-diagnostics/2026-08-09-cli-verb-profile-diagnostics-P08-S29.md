---
tags:
  - '#exec'
  - '#cli-verb-profile-diagnostics'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:7e538e43332fbacd6fe187afc4ee3ff8dce7074c9711a9c0b0c2ea097c41b9bd'
step_id: 'S29'
related:
  - "[[2026-08-09-cli-verb-profile-diagnostics-plan]]"
---
# Name the missing identity field by its schema-derived operator label in the wizard status refusal instead of baking a selector token into the sentence

## Scope

- `src/cadrumo/application/wizard/_status.py`

## Description

- Added `_grounded_tax_id_requirement`, rendering the tax-identifier field through the canonical requirement builder and shared formatter.
- Passed the result on the refusal's `context` under a `requirements` key, and lifted the previously inline path to a named constant used by both the presence check and the rendering.

## Outcome

The refusal now names the field by its operator label with whatever legal grounding the registry carries.

The identifier this refusal printed was the field's declared SELECTOR TOKEN, not its path. That is worth stating precisely because a sweep looking only for dotted paths would have walked past it: the token and the path differ, and the token appears nowhere in the profile editor.

The second, quieter defect was that the field name lived in the locale catalogues. A schema rename would have required chasing the name through four translations, with nothing to fail if one were missed. The name is now read from the schema and the catalogues carry only the sentence around it.

The refusal CONDITION is unchanged: the same absent fact triggers it.

## Verification

    uv run --no-sync pytest src/cadrumo/application/wizard src/cadrumo/application/modelo/tests/test_export_declarant_identity_grounding.py src/cadrumo/application/modelo/tests/test_export_headers.py src/cadrumo/application/tests/test_diagnostics.py -m "unit or integration" -n 0 -q
    376 passed in 31.82s

## Notes

`wizard status` is one of the three surfaces whose READINESS VERDICT stays deferred. This changes neither that verdict nor this refusal's condition - only the sentence an already-refusing path emits.
