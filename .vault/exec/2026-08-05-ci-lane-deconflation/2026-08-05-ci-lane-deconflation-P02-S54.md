---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-30'
modified: '2026-08-30'
body_schema: 'body-v2'
body_hash: 'sha256:da6ec9e082cd9518e1d43025d0b4c21adf0142c440bb3812279362ee08a283e3'
step_id: 'S54'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---

# Close the sixteen-key codebase-to-locale parity drift left by the view verb family and the taxpayer_type.declaration_roles schema field, both landed within hours of the 2026-08-28 measurement. The keys are missing from ALL FOUR catalogues, so this is an unfinished co-commit rather than a translation backlog: cli.app.ledger.counterparty.view_help, cli.app.ledger.evidence.review.view_help, cli.app.modelo.audit.view_help, the three cli.app.modelo.reconcile.list_* keys, cli.config.auth.diagnostics.view_help, the two cli.config.google view_help keys, cli.config.profile.capabilities.view_help, the two cli.config.storage.view keys, the three cli.operator_surface.help.* keys and profile.schema.field.taxpayer_type.declaration_roles.label. Deliberately left to the verbs' own author rather than absorbed, because inventing help prose for someone else's in-flight surface collides with their wording; the scaffold placeholder and an omitted ca or hu are both refused, so there is no partial landing

## Scope

- `src/cadrumo/locales/{en`
- `es`
- `ca`
- `hu}`

## Changes

- `M` `src/cadrumo/locales/en/cli.yml`
- `M` `src/cadrumo/locales/es/cli.yml`
- `M` `src/cadrumo/locales/ca/cli.yml`
- `M` `src/cadrumo/locales/hu/cli.yml`
- `M` `dev/locales/_fstring_registry.py`
- `verify:` `python -m dev.locales scaffold --check` -> `pass`

## Notes

The row specifies sixteen keys including `profile.schema.field.taxpayer_type.declaration_roles.label`. That key had already landed by the time this was measured; the drift at execution was fifteen keys, identical in all four catalogues, zero extras and zero moves. Sixty strings were authored with Spanish as source, `ca` and `hu` as real translations rather than copies, and no `_intentional_identical.json` entry.

The row's stated reason for deferral -- that inventing help prose for another lane's in-flight surface collides with its author -- was resolved by taking wording from each key's own call site and its nearest sibling in `es/cli.yml`, not by inventing it.

`dev/locales/_fstring_registry.py` is included because the whole `dev.locales` CLI was dead when this row was picked up: a function-local import still named the retired `cadrumo.core.errors._registry`, so the module imported cleanly while every verb died on call, and the parity gate was unmeasurable rather than red.
