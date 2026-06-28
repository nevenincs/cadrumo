---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
step_id: 'W45.P225'
related:
  - '[[2026-05-13-cli-workflow-redesign-epic-plan]]'
  - '[[2026-05-13-cli-workflow-redesign-app-modelo-discard-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-adr]]'
---

# `cli-workflow-redesign` `W45.P225`

Thin-CLI-exposure + tightening loop for the wave.

## Description

CLI registration
(`src/aeat/entrypoints/cli/_modelo.py`):

- `aeat app modelo work discard WORK_UNIT_ID --by ACTOR
  [--reason TEXT]` — translates
  `WorkUnitNotFoundError` and `WorkUnitAlreadyDiscardedError`
  to `typer.BadParameter` so operator-facing errors stay
  clean.
- `aeat app modelo work list` gains `--include-discarded`
  (default `False`). The listing now carries a `state` column.
- `_work_unit_payload` and `_work_unit_lines` emit the new
  state and discard-audit fields in both JSON and text
  formats; the JSON payload carries `null` for the
  discard-* fields on draft units.
- `aeat app modelo work rename` propagates
  `WorkUnitMutationRefusedError` to the operator with the
  same `typer.BadParameter` translation.

Localization: each locale file (`es`, `en`, `hu`, `ca`) gains
four new keys under `cli.app.modelo.work.*`:

- `actor_help`, `discard_help`,
  `include_discarded_help`, `reason_help`.

All four files carry real translations distinct from English;
the locale honesty test passes. The residual codebase-to-locale
parity gap is unchanged from before the wave.

Type checking: `uv run --no-sync ty check
src/aeat/domain/modelos/_work_unit.py
src/aeat/domain/modelos/_repository.py
src/aeat/application/modelo/_actions.py
src/aeat/entrypoints/cli/_modelo.py` reports `All checks
passed!`.

Source-purity tightening: the new state / discard surface uses
domain-language docstrings and no wave / phase metadata. Wave
references live only in the commit message and this exec
record.

Closed plan rows: `W45.P225.S1345`, `W45.P225.S1346`,
`W45.P225.S1347`, `W45.P225.S1348`, `W45.P225.S1349`,
`W45.P225.S1350`.

## Tests

`uv run --no-sync pytest src/aeat/domain/modelos/test_work_unit.py
src/aeat/entrypoints/cli/test_modelo.py
src/aeat/locales/test_locale_translation_honesty.py -q` —
44 / 44 pass.
