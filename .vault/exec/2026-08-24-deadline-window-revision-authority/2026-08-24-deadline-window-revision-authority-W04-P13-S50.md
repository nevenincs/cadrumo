---
tags:
  - '#exec'
  - '#deadline-window-revision-authority'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:c98a2e935d86f4c2c812cb8e8ff828db19c398078a2b15b1a8754993e84149d5'
step_id: 'S50'
related:
  - "[[2026-08-24-deadline-window-revision-authority-plan]]"
---

# Restore real CLI calendar parity for canonical filing evidence and locked-profile rendering after concurrent projection changes, keeping the CLI a thin consumer of overview and registry deadline authority

## Scope

- `src/cadrumo/entrypoints/cli/`
- `src/cadrumo/application/overview/`
- `src/cadrumo/entrypoints/cli/tests/test_overview_calendar_verb.py`

## Description

- Reproduce the six real CLI parity failures under the integration marker.
- Trace each missing field to the compact transport projection rather than the canonical overview builder.
- Replace lossy entry and event summaries with the existing complete typed payloads.
- Resolve warning remedies through the existing command-catalogue resolver and reuse the result in JSON.
- Render the common profile header for locked profiles while retaining the explicit locked-state row.
- Confirm by exact-symbol search that no deadline, evidence, status, cadence, selector, or action resolver was redeclared.

## Outcome

The real calendar JSON now preserves canonical deadline shift metadata, complete filing evidence, AEAT submission timestamps, and schema-resolved warning remedies. All-profile text includes a common profile header for locked profiles. The CLI remains a transport adapter over application-owned calendar state.

## Notes

The initial integration run established exactly six failures and 16 passes. Clean detached verification then exposed two remaining warning-action nesting failures. The follow-up preserves canonical `ResolvedNoticeAction` resolution while projecting its stable identity into the established nested warning envelope. Both remaining real-CLI tests pass (`2 passed in 118.57s`). Ruff and format checks pass. Formal follow-up review accepted the typed transport composition with no findings. The follow-up code was captured by concurrent commit `be01c4b0be`; this record-and-plan commit closes the verified step without duplicating it.
