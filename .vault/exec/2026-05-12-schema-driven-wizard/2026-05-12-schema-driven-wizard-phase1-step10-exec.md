---
tags:
  - '#exec'
  - '#schema-driven-wizard'
date: '2026-05-12'
modified: '2026-05-12'
related:
  - "[[2026-05-12-schema-driven-wizard-plan]]"
  - "[[2026-05-12-schema-driven-wizard-adr]]"
---

# `schema-driven-wizard` `phase1` `step10`

Landed the `wizard.*` locale catalogue block plus the locale-parity
audit gate.

## What landed

- `src/aeat/locales/{en,es,ca,hu}.yml`: each gains a `wizard.setup`
  subtree covering every `Translatable` referenced by `WIZARD_FLOWS`
  — section titles, question prompts, IVA / CCAA choice labels,
  the flow title / description, and `errors.missing_required_flags`.
  Existing `setup.wizard.*`, `cli.setup.*`, `cli.init.*` keys remain
  in place (W11 deletes them).
- `src/aeat/application/wizard/_translations.py` declares
  `audit_wizard_translations()` which walks every `Translatable`
  reachable from `WIZARD_FLOWS` (plus the fixed runtime error key)
  and returns the tuple of (`locale`, `key`) pairs that fail to
  resolve.
- `src/aeat/application/wizard/test_wizard_translations_resolve.py`
  is the locale-parity gate test per ADR section I: it asserts the
  audit returns an empty tuple, i.e. every wizard key resolves in
  every locale.
- `tools/generate_wizard_locale_block.py` is the one-shot helper
  that built the wizard subtree per language. It's contributor-only
  and lives under `tools/` so the production code path does not
  import it.

## Gates cleared

- `uv run --no-sync pytest src/aeat/application/wizard/test_wizard_translations_resolve.py`
  is green; the audit returns `()`.
- `uv run --no-sync prek run --files <touched paths>` passes.

## Not in this Step

- The legacy `setup.wizard.*` / `cli.setup.*` / `cli.init.*` keys
  remain (W11 deletes them in the same change that drops the
  legacy code).
