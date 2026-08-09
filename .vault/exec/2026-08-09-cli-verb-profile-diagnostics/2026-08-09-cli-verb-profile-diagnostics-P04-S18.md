---
tags:
  - '#exec'
  - '#cli-verb-profile-diagnostics'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:8cccfa1a883b857f52a7c3769265d9b62b58e99b4f912e0d7bdb334662865861'
step_id: 'S18'
related:
  - "[[2026-08-09-cli-verb-profile-diagnostics-plan]]"
---
# Confirm locale catalogue parity and translation honesty across all four catalogues

## Scope

- `src/cadrumo/locales`

## Description

- Ran the catalogue drift gate after every locale mutation in this work.
- Confirmed each of the three added keys carries a real translation in all four catalogues, and that no self-referencing placeholder was used.
- Confirmed the two superseded keys removed here had no remaining code reference, and that the one retained key still does.

## Outcome

All four catalogues are in parity with no drift.

Three keys were added: the overview incomplete-profile refusal, the overview undeclared-taxpayer-model refusal, and the diagnostics missing-fields summary. Two were removed as superseded and unreferenced.

The retention decision is the one worth recording: `cli.overview.taxpayer_model_undeclared` was NOT removed even though the CLI stopped rendering it, because the application layer still sets it as the calendar payload's `incomplete_reason`, which machine consumers read. Removing it on the strength of the CLI change alone would have emptied a payload field.

## Verification

    uv run --no-sync python -m dev.locales scaffold --check
    ca.yml: ok
    en.yml: ok
    es.yml: ok
    hu.yml: ok

Every mutation went through the locale CLI; no catalogue file was hand-edited and the intentional-identical allowlist was not touched.

## Notes

The gate's `extra` report is what identified each superseded key as unreferenced, rather than a manual judgement about whether it was still needed.
