---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
step_id: 'W38.P190'
related:
  - '[[2026-05-13-cli-workflow-redesign-epic-plan]]'
  - '[[2026-05-12-cli-workflow-redesign-modelo-work-units-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-adr]]'
---

# `cli-workflow-redesign` `W38.P190`

Thin-CLI-exposure + tightening loop for the wave.

## Description

CLI registration (`src/aeat/entrypoints/cli/_modelo.py`):

- `work_app` Typer registered under the parent `aeat app modelo`
  via `app.add_typer(work_app, name="work")`. The root contract
  stays `aeat config` + `aeat app` only.
- Four commands: `aeat app modelo work {create, list, status,
  rename}`.
- `WorkUnitNotFoundError` is translated to
  `typer.BadParameter` at the CLI boundary so the operator
  sees a clean error message rather than a Python traceback.

Localization: each locale file (`es`, `en`, `hu`, `ca`) gains
twelve new keys under `cli.app.modelo.work.*`:

- `app_help`, `bucket_id_help`, `create_help`, `list_help`,
  `modelo_help`, `name_help`, `period_help`, `rename_help`,
  `revision_help`, `status_help`, `work_unit_id_help`,
  `year_help`.

All four locale files carry distinct real translations so the
locale honesty test passes; the residual codebase-to-locale
parity gap is unchanged from before the wave (the 8 missing
keys remain pre-existing glob-pattern gaps from other waves).

Type checking: `uv run --no-sync ty check
src/aeat/domain/modelos/_work_unit.py
src/aeat/domain/modelos/_repository.py
src/aeat/application/modelo/_actions.py
src/aeat/application/modelo/__init__.py` reports `All checks
passed!`.

Source-purity tightening: the new modules describe what the code
IS, not the wave that produced it. No `W38`, `P186`, or `ADR`
references in source code or tests; wave references live only in
the commit message and this vault exec record.

Error-message-key locale entries for the two new error codes
(`FAIL_MODELO_WORK_UNIT_PERSISTENCE`,
`ERROR_MODELO_WORK_UNIT_NOT_FOUND`) are deferred to a follow-up
locale sweep alongside other registered-error-code message
gaps; the registry-side bindings are in place and the runtime
renders the code identifier directly when the locale key is
absent.

Closed plan rows: `W38.P190.S1135`, `W38.P190.S1136`,
`W38.P190.S1137`, `W38.P190.S1138`, `W38.P190.S1139`,
`W38.P190.S1140`.

## Tests

`uv run --no-sync pytest src/aeat/domain/modelos/test_work_unit.py
src/aeat/entrypoints/cli/test_modelo.py
src/aeat/locales/test_locale_translation_honesty.py -q` — 35 /
35 pass.
