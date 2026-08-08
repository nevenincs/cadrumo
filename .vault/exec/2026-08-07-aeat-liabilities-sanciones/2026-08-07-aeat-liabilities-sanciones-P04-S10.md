---
tags:
  - '#exec'
  - '#aeat-liabilities-sanciones'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:da913707dfee8f1ec4ed88aaf694220175374227c361a525a1e5988ba3922f94'
step_id: 'S10'
related:
  - "[[2026-08-07-aeat-liabilities-sanciones-plan]]"
---
# Add the deudas CLI entrypoint and its list, view and latest payload models as new OutputSchema subclasses in the existing _app_live_payloads module, mirroring the expedientes payload shapes. Introduces tr help keys, so this row and S11 and S12 land as ONE unit with P07.S23 rather than independently: the codebase-to-locale parity gate is tree-wide and immediate, so the moment a tr key exists in source it must exist in all four catalogues

## Scope

- `src/cadrumo/entrypoints/cli/_app_live_deudas_cli.py`
- `src/cadrumo/entrypoints/cli/_app_live_payloads.py`

## Description

- Verify rather than author: the payload models and the CLI entrypoint module
  for this row were already on disk when this record was opened.
- Confirm the five payload types exist as `OutputSchema` subclasses in the
  existing payloads module and that the three result types are registered
  against their envelope command ids.
- Confirm the entrypoint module exists and enumerate the `tr` keys it
  introduces, since this row's stated reason for landing as one unit with the
  locale row is precisely that it introduces them.

## Outcome

`DeudaRowPayload` and `DeudaSnapshotSummaryPayload` are declared in
`src/cadrumo/entrypoints/cli/_app_live_payloads.py`, together with
`DeudasListResult`, `DeudasViewResult` and `DeudasLatestResult` registered
against `app.live.deudas.list`, `.view` and `.latest` respectively. The
entrypoint module `src/cadrumo/entrypoints/cli/_app_live_deudas_cli.py` exists
and declares no `pull` verb, consistent with the specimen-blocked read landing.

The row introduces exactly five `tr` keys: the family help, the three verb
helps, and the snapshot-id argument help. Four of the five are reached only
through multi-line `tr(` calls, so a single-line grep finds one key and misses
four. That mattered: the count of keys is what the locale row has to satisfy,
and an undercount there would have left four placeholders in place while
reading as complete.

## Verification

    rg -n "class DeudaRowPayload|class DeudaSnapshotSummaryPayload|class DeudasListResult|class DeudasViewResult|class DeudasLatestResult|register_schema\(\"app.live.deudas" src/cadrumo/entrypoints/cli/_app_live_payloads.py
    833:class DeudaRowPayload(OutputSchema):
    855:class DeudaSnapshotSummaryPayload(OutputSchema):
    869:@register_schema("app.live.deudas.list")
    870:class DeudasListResult(OutputSchema):
    883:@register_schema("app.live.deudas.view")
    884:class DeudasViewResult(OutputSchema):
    900:@register_schema("app.live.deudas.latest")
    901:class DeudasLatestResult(OutputSchema):

    uv run --no-sync pytest src/cadrumo/entrypoints/cli/tests/test_live_deudas_verbs.py -m integration -n0 -q
    8 passed in 6.97s

The marker lane is load-bearing. The same path without the marker expression
deselected all eight tests and the runner said so explicitly:
"8 deselected", with a warning that a green result means the selection matched
nothing. Quoted here because a paraphrase would discard the part that shows
the selection was real.

## Notes

The content predates this record. The payload models and the entrypoint module
landed in commit `ed09a6dd4b`, whose subject reads "feat(cadrumo): land the
in-flight source work" and names neither deudas nor this row. Attribution
therefore lives here rather than in the commit history, which is the reason
this record exists at all.
