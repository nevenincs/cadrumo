---
tags:
  - '#exec'
  - '#locale-informal-register'
date: '2026-10-02'
modified: '2026-10-02'
body_schema: 'body-v2'
body_hash: 'sha256:72dea7f85a1fb1347f18a6ada9b694ad34199b3fc3412f60fd8c959efe6dbf24'
related:
  - "[[2026-10-02-locale-informal-register-plan]]"
---

# `locale-informal-register` ledger

## Changes

- `S01` `M` `src/cadrumo/locales/ca/adapters.yml`
- `S01` `M` `src/cadrumo/locales/ca/application.yml`
- `S01` `M` `src/cadrumo/locales/ca/cli.yml`
- `S01` `M` `src/cadrumo/locales/ca/common.yml`
- `S01` `M` `src/cadrumo/locales/ca/docs.yml`
- `S01` `M` `src/cadrumo/locales/ca/errors.yml`
- `S01` `M` `src/cadrumo/locales/ca/profile.yml`
- `S01` `M` `src/cadrumo/locales/ca/wizard.yml`
- `S01` `M` `src/cadrumo/locales/es/application.yml`
- `S01` `M` `src/cadrumo/locales/es/cli.yml`
- `S01` `M` `src/cadrumo/locales/es/common.yml`
- `S01` `M` `src/cadrumo/locales/es/docs.yml`
- `S01` `M` `src/cadrumo/locales/es/errors.yml`
- `S01` `M` `src/cadrumo/locales/es/profile.yml`
- `S01` `M` `src/cadrumo/locales/es/wizard.yml`
- `S01` `verify:` `uv run --no-sync python -m scratch_locale_tone.fleet verify` -> `pass`
- `S01` `by:` `Luna Max fleet; parent review`
- `S02` `M` `src/cadrumo/locales/hu/cli.yml`
- `S02` `M` `src/cadrumo/locales/hu/errors.yml`
- `S02` `M` `src/cadrumo/locales/hu/wizard.yml`
- `S02` `verify:` `uv run --no-sync python -m scratch_locale_tone.fleet verify` -> `pass`
- `S02` `by:` `Luna Max fleet; parent review`
- `S03` `M` `src/cadrumo/locales/hu/adapters.yml`
- `S03` `M` `src/cadrumo/locales/hu/application.yml`
- `S03` `M` `src/cadrumo/locales/hu/common.yml`
- `S03` `M` `src/cadrumo/locales/hu/docs.yml`
- `S03` `M` `src/cadrumo/locales/hu/flows.yml`
- `S03` `M` `src/cadrumo/locales/hu/profile.yml`
- `S03` `verify:` `uv run --no-sync python -m scratch_locale_tone.fleet verify` -> `pass`
- `S03` `by:` `Luna Max fleet; parent review`
- `S04` `M` `scratch_locale_tone/convergence.py`
- `S04` `M` `scratch_locale_tone/fleet.py`
- `S04` `A` `scratch_locale_tone/review.py`
- `S04` `A` `scratch_locale_tone/provenance.py`
- `S04` `A` `scratch_locale_tone/capture_merge.py`
- `S04` `M` `scratch_locale_tone/tests/test_convergence.py`
- `S04` `verify:` `uv run --no-sync python -m scratch_locale_tone.convergence` -> `pass`
- `S04` `verify:` `uv run --no-sync pytest -n 0 -p no:randomly scratch_locale_tone/tests/test_convergence.py` -> `pass`
- `S04` `by:` `parent independent review`
- `S05` `M` `dev/locales/tests/test_parity.py`
- `S05` `M` `src/cadrumo/core/i18n/tests/test_hu_error_diacritics.py`
- `S05` `M` `src/cadrumo/locales/en/common.yml`
- `S05` `M` `.vaultspec/rules/aeat-locales-cli.md`
- `S05` `M` `.codex/rules/aeat-locales-cli.md`
- `S05` `M` `.agents/rules/aeat-locales-cli.md`
- `S05` `M` `.claude/rules/aeat-locales-cli.md`
- `S05` `M` `.gemini/rules/aeat-locales-cli.md`
- `S05` `A` `.vault/audit/2026-10-02-locale-informal-register-audit.md`
- `S05` `A` `scratch_locale_tone/FLEET_REPORT.md`
- `S05` `A` `scratch_locale_tone/metrics.py`
- `S05` `verify:` `uv run --no-sync pytest -n 0 -p no:randomly -m "unit or integration" dev/locales/tests/test_parity.py dev/locales/tests/test_locale_translation_honesty.py dev/locales/tests/test_wizard_translations_resolve.py dev/locales/tests/test_reserved_translation_tokens.py src/cadrumo/core/i18n/tests src/cadrumo/entrypoints/cli/tests/test_language_flag_override.py src/cadrumo/entrypoints/cli/tests/test_output_language_parity.py src/cadrumo/entrypoints/cli/tests/test_config_descendiente_help_parity.py src/cadrumo/entrypoints/cli/tests/test_meses_trabajo_help_states_both_limbs.py src/cadrumo/entrypoints/cli/tests/test_review_work_create_language_render.py src/cadrumo/entrypoints/tui/tests/test_profile_password_locale_parity.py` -> `pass`
- `S05` `verify:` `uv run --no-sync ruff check scratch_locale_tone dev/locales/tests/test_parity.py src/cadrumo/core/i18n/tests/test_hu_error_diacritics.py` -> `pass`
- `S05` `verify:` `uv run --no-sync ruff format --check scratch_locale_tone dev/locales/tests/test_parity.py src/cadrumo/core/i18n/tests/test_hu_error_diacritics.py` -> `pass`
- `S05` `by:` `parent integrated review`
- `S05` `A` `.vault/index/locale-informal-register.index.md`
- `S05` `verify:` `uv run --no-sync vaultspec-core vault check features --feature locale-informal-register --json` -> `pass`

## Notes

- `S01` Parent repaired a Catalan child-subject semantic error; concurrent Modelo naming corrections excluded from fleet totals.
- `S02` Dependent formal forms discovered after initial batches were returned to the owner and repaired.
- `S03` HU common ownership was explicitly handed off; parent repaired two prorrata meaning defects before acceptance.
- `S04` Concurrent merge changed 68 authority shards and 21 application contracts. Exact committed provenance accepted separately; frozen baselines retained. Incoming runtime keys joined the same queue.
- `S05` Initial broad run found two failures: formal expected-string pin and stale locale shortcut. Both repaired; applicable final run passed 188 tests. Detector fixtures passed two tests; integrated review PASS.
- `S05` Feature index verb lacks --dry-run; inspected its exact scoped output in an isolated copy before applying. Final fresh-process feature check has zero diagnostics; earlier MCP warning described the old two-link index.
