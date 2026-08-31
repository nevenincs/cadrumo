---
tags:
  - '#exec'
  - '#tui-interface'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:0e52ce3f4673f36cb43389346cd8236758c02808f115c1f3362c34a7654057df'
step_id: 'S86'
related:
  - "[[2026-08-11-tui-interface-plan]]"
  - "[[2026-08-11-tui-interface-W06-P12c-S85]]"
---

# Enroll export only through its canonical export-readiness capability and registered operation, and prove evidence-backed refusal, interaction, terminal effect, typed refresh, focus return, and every supported geometry independently

## Scope

- `src/cadrumo/entrypoints/tui/modelo/tests/test_c4_export_action.py`

## Changes

- `A` `src/cadrumo/entrypoints/tui/modelo/action/export.py`
- `A` `src/cadrumo/entrypoints/tui/modelo/tests/test_c4_export_action.py`
- `M` `src/cadrumo/application/modelo/operation_definitions.py`
- `verify:` `pytest test_c4_export_action.py test_c4_file_action.py test_c4_verify_action.py test_c4_discard_action.py test_c4_rename_action.py test_actions.py` -> `58 passed`

## Notes

THIS IS NOT THE EXPORT THAT BYPASSES THE SUPERVISOR, and a test pins the
difference because the names invite conflation. `modelo.export` and
`export.google-sheets` are distinct registered operations; only the latter is
reached by calling a service's `execute` directly, which is the unjournalled,
unleased defect recorded against the architecture lane in W07.P16.S340. This
enrolment submits through the composed supervisor like its siblings, and
asserting the two definition ids differ stops it inheriting that finding by
association.

THE CONFIDENTIALITY PROPERTY IS THE LOAD-BEARING ONE. The exported bytes never
enter the request OR the result, asserted over both whole field sets rather
than by naming a suspect field. An operation request is journalled, and a
filing artefact is a taxpayer's complete declared position -- the most
sensitive thing this application produces. Carrying the bytes would copy them
out of the encrypted store into the operations journal, a different store with
a different lifetime. The path is carried because a LOCATION IS NOT CONTENT.

Cancellation is UNSUPPORTED, so no surface may offer it -- a half-written
fichero is worse than one the operator waited for. Checked structurally on the
AST rather than by searching for the word, so this module's own prose
explaining the constraint stays permitted.

THE WHITESPACE DEFECT, THIRD OCCURRENCE, AND A THIRD DISTINCT REMEDY. A
whitespace-only `output_path` was accepted. Across the three C4 rows this class
has now appeared on a display name (W06.P12c.S82), an identifier
(W06.P12c.S84), and a destination path here -- and each needed a DIFFERENT fix,
which is why a blanket sweep of `min_length=1` fields would have been wrong. A
name is STRIPPED, matching the domain's own `_DisplayName`. An identifier and a
path are NOT: altering an identifier changes what it addresses, and trimming a
path masks a typo rather than surfacing it. Both get `pattern=r"\S"`, which
refuses an all-whitespace value while leaving an accepted one byte-exact.

CAUGHT BY MY OWN GUARD: the edit asserted a single `output_path` declaration
and there were TWO -- the request and the public result. Both are now guarded,
since a result echoing a whitespace path is equally meaningless. Had the
assertion not been there, the first match would have been patched and the
second left silently loose.

ENVIRONMENTAL FAILURE SEPARATED FROM CODE FAILURE. A run of the whole modelo
TUI package reported 112 passed with 24 ERRORS, all in the C2 accessibility
suite, all `EOFError: profile KDF worker closed its pipe` /
`KDF_SUPERVISION_UNAVAILABLE`. That is a host-level resource failure wearing a
domain-shaped error -- the same class as the credential-store saturation this
campaign has hit before -- not a regression from the constraint change. Checked
rather than assumed: the errors never mention `output_path`, and the six C4
suites run 58 passed on their own.
