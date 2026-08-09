---
tags:
  - '#exec'
  - '#cli-verb-profile-diagnostics'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:385675946f7bd2aeb5c12661cd27070995c74e6561acc430d37447b2744bfad1'
step_id: 'S23'
related:
  - "[[2026-08-09-cli-verb-profile-diagnostics-plan]]"
---
# Render the missing declarant-identity facts in the modelo export refusal as grounded requirement rows rather than raw dotted paths

## Scope

- `src/cadrumo/application/modelo/_export.py`

## Description

- Added `_grounded_identity_requirements`, rendering declarant-identity paths through the canonical requirement builder and the shared requirement formatter.
- Applied it to all three refusal branches: the legal-entity legal-name branch, the legal-entity name-slot branch, and the natural-person surnames/name branch.

## Outcome

An operator refused at export is now told which identity field to fill in, by the label the profile editor shows, with whatever legal grounding the registry carries.

Two details worth stating:

The rendering is a string, not a list. The refusal's translated message interpolates the value directly, so the previous list rendered Python's own bracket and quote punctuation into operator-facing text. That was a second, quieter defect at the same site.

This is a filing-grade surface, which is why it was worth doing rather than deferring: an operator blocked here cannot produce a return at all, so the cost of an unactionable message is highest exactly here.

The refusal CONDITIONS are untouched. The same absent facts trigger the same three branches.

## Verification

    uv run --no-sync pytest src/cadrumo/application/modelo/tests/test_export_declarant_identity_grounding.py -n 0 -q
    4 passed in 1.17s

    uv run --no-sync pytest src/cadrumo/application/modelo/tests/test_export_headers.py -m "unit or integration" -n 0 -q
    6 passed in 15.73s

## Notes

**Found during the honesty review, not the original inventory.** The initial pass scoped itself to the CLI tree plus the application sites named in the initiating brief, and this site was in neither. It was reached by sweeping the locale catalogue for operator-facing messages interpolating a missing-field list, which is the sweep the original inventory should have run to completion.

An existing test pinned the old raw-path context exactly. It was corrected to assert the schema-derived label rather than being left asserting a contract this work deliberately replaces.
