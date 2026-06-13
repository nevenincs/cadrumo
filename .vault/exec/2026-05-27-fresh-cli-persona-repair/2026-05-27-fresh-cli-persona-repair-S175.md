---
tags:
  - "#exec"
  - "#fresh-cli-persona-repair"
date: '2026-05-27'
modified: '2026-05-27'
step_id: S175
commit: 51c99c2da
related:
  - "[[2026-05-21-fresh-cli-persona-repair-plan]]"
  - "[[2026-05-27-lourdes-cli-testimonial-audit]]"
---

# fresh-cli-persona-repair S175 — foral-regime refusal (País Vasco + Navarra)

## What was done

Addressed Lourdes F1 audit finding: `profile create --tax-residence-ccaa
pais_vasco` previously returned a generic Click "not one of" error rather
than a localised redirect to Hacienda Foral.

**`src/aeat/application/wizard/_commands.py`**

- `_ccaa_choice_values()` now appends `["pais_vasco", "navarra"]` to the
  15 common-regime enum values so Click passes the token through instead of
  refusing it at the choice layer.
- `_command_body()` gained a foral pre-check: after `canonical`/`explicit_flags`
  are assembled but before any persistence or flow walk, it calls
  `parse_tax_region(token)` on the `tax-residence-ccaa` value. A
  `ForalRegimeError` is caught and converted to `typer.BadParameter` carrying
  the enriched locale message. Fires on both `--quiet` patch-edit and
  full interactive-flow paths.

**Locale files — `profile.errors.foral_regime`**

- `es.yml`: replaced one-line generic message with a Concierto Económico
  redirect citing Ley 12/2002 and Hacienda Foral URLs (bizkaia, gipuzkoa,
  araba, navarra).
- `en.yml`: equivalent English redirect.
- `ca.yml`: equivalent Catalan redirect.
- `hu.yml`: unchanged — already resolves via pass-through ref to `es.yml`.

**`src/aeat/entrypoints/cli/test_profile_create_taxpayer_type_paths.py`**

Two regression tests appended:
- `test_profile_create_refuses_pais_vasco_with_concierto_economico_redirect`
- `test_profile_create_refuses_navarra_with_concierto_economico_redirect`

Both assert: non-zero exit, no traceback, and that the output contains at
least one of "Concierto", "Ley 12/2002", "Hacienda Foral", or "foral".

## Verification

- `pytest test_profile_create_taxpayer_type_paths.py`: 10/10 passed (4.09 s)
- `pytest test_apex_workflow_verification.py`: 18/18 passed (38 s)
- `python -m aeat.locales audit`: all four locales ok
- `ruff check`: all checks passed
- `pyright`: 0 errors, 4 pre-existing warnings
