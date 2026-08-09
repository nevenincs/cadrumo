---
tags:
  - '#exec'
  - '#cli-verb-profile-diagnostics'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:5a4377a0f6671357c17254490d0d353bb0ac4e4e6ba68f3f29fe84d89a1209d5'
step_id: 'S32'
related:
  - "[[2026-08-09-cli-verb-profile-diagnostics-plan]]"
---
# Add real tests asserting both refusals name their fields by operator label and carry no raw dotted path

## Scope

- `src/cadrumo/application/wizard/tests/test_status_refusal_grounding.py`

## Description

- Added a wizard module asserting the tax-identifier refusal renders the operator label and carries neither the dotted path nor the legacy selector token.
- Added the export no-profile assertions to the existing modelo export grounding module.
- Added an anchor test asserting the label differs from BOTH the path and the token.

## Outcome

Both refusals are covered against the real committed schema.

The anchor test checks three-way distinctness rather than two, because the wizard refusal printed the SELECTOR TOKEN and not the path. A test asserting only that the path is absent would have passed against the unfixed code, since the path was never there to begin with.

The test placement was corrected before landing. The first draft asserted the export behaviour from the wizard tests package, which meant importing a private module across package boundaries - the same defect corrected earlier in this work. The export assertions were moved to the modelo package, where the code they exercise lives, rather than allowlisted.

## Verification

    uv run --no-sync pytest src/cadrumo/application/wizard/tests/test_status_refusal_grounding.py src/cadrumo/application/modelo/tests/test_export_declarant_identity_grounding.py -n 0 -q
    9 passed in 1.09s

    uv run --no-sync pytest src/cadrumo/application/wizard src/cadrumo/application/modelo/tests/test_export_declarant_identity_grounding.py src/cadrumo/application/modelo/tests/test_export_headers.py src/cadrumo/application/tests/test_diagnostics.py -m "unit or integration" -n 0 -q
    376 passed in 31.82s

## Notes

Confirmed no pre-existing test pinned either refusal's old wording. The `tax.id` occurrences elsewhere in the wizard tests are flow-compilation fixtures naming a question's profile key, which is a different concern and correct as it stands.
