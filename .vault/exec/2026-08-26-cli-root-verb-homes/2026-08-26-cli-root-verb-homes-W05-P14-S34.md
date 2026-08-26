---
tags:
  - '#exec'
  - '#cli-root-verb-homes'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:083c67e277203d756afdfcc34c7706c265d41de4fb9c7080ec0744fbc86c3644'
step_id: 'S34'
related:
  - "[[2026-08-26-cli-root-verb-homes-plan]]"
---

# Sweep the dev quality dispositions and CLI benchmark goldens

## Scope

- `dev/`

## Changes

- `M` `dev/quality/cli_action_census_dispositions.toml`
- `M` `dev/docs/sequences/_schema.py`
- `M` `dev/docs/tests/test_static_frame_reasons.py`
- `M` `dev/locales/tests/test_ledger_notice_action_conformance.py`
- `M` `dev/locales/tests/test_s89_action_conformance.py`
- `M` `dev/tests/test_utf8_enrollment_inventory.py`
- `M` `src/cadrumo/entrypoints/cli/_config/_archive_reconcile.py`
- `verify:` `pytest dev/docs/tests + dev/locales/tests (sequential)` -> `pass`

## Notes

Two defects were found here, both introduced by this campaign. The S89 config
module scope had `_google_sync_calc.py` RENAMED to `_modelo_spreadsheet_cli.py`
when the file had in fact left `_config/` and needed deleting from the set; the
three modules the archive subject added were also absent. And moving
`_app_maintenance.py` into `_config/` brought it under that directory's ban on
`tr(..., default=...)` fallbacks, which it had carried legally outside it; the
three fallbacks are removed, their keys already being present in all four
catalogues.

The tracked `dev/benchmarks/cli/baseline.census.json` is NOT refreshed. It was
already stale before this campaign (peer verbs `evidence attachment-queue`,
`attachment-view`, `inventory closing-authority-record`, `modelo work run` are
live and absent from it), re-capture requires an uncontended tree, and
hand-editing it would fabricate timing provenance.
