---
tags:
  - '#exec'
  - '#locale-po-informal-register'
date: '2026-10-02'
modified: '2026-10-02'
body_schema: 'body-v2'
body_hash: 'sha256:80831ad57d0e83f4cd61825680cdc359aec2b8764b910cfac18ac2cea2e56d7c'
related:
  - "[[2026-10-02-locale-po-informal-register-plan]]"
---

# `locale-po-informal-register` ledger

## Changes

- `S01` `M` `src/cadrumo/locales`
- `S01` `M` `dev/locales/tests/test_parity.py`
- `S01` `M` `src/cadrumo/core/i18n/tests/test_hu_error_diacritics.py`
- `S01` `M` `.vaultspec/rules/aeat-locales-cli.md`
- `S01` `A` `.vault/plan/2026-10-02-locale-informal-register-plan.md`
- `S01` `A` `.vault/audit/2026-10-02-locale-informal-register-audit.md`
- `S01` `verify:` `uv run --no-sync python -m scratch_locale_tone.convergence gate` -> `pass`
- `S01` `verify:` `uv run --no-sync pytest -n 0 -p no:randomly -m "unit or integration" <188-test runtime localization selection>` -> `pass`
- `S01` `by:` `root`
- `S02` `M` `docs/locales/ca/LC_MESSAGES/how-to/review-calculation-values.po`
- `S02` `verify:` `uv run --no-sync python -m scratch_locale_tone.po_review seal parent_ca_adjudications.json` -> `pass`
- `S02` `verify:` `uv run --no-sync pytest -q -n 0 -p no:randomly -m unit dev/docs/tests/test_docs_build_localized_ca.py dev/docs/tests/test_docs_build_localized_es.py` -> `pass`
- `S02` `by:` `root; Luna Max discovery; independent contextual adjudication`
- `S02` `verify:` `uv run --no-sync python -m scratch_locale_tone.po_review seal parent_ca_adj_01.json --adjudications` -> `pass`
- `S02` `verify:` `uv run --no-sync pytest -q -n 0 -m integration dev/docs/tests/test_docs_catalogue_drift.py` -> `pass`
- `S03` `M` `docs/locales/es/LC_MESSAGES/how-to/review-calculation-values.po`
- `S03` `verify:` `uv run --no-sync pytest -q -n 0 -p no:randomly -m unit dev/docs/tests/test_docs_build_localized_ca.py dev/docs/tests/test_docs_build_localized_es.py` -> `pass`
- `S03` `verify:` `uv run --no-sync pytest -q -n 0 -m integration dev/docs/tests/test_docs_catalogue_drift.py` -> `pass`
- `S03` `by:` `root; Luna Max discovery; independent contextual adjudication`
- `S04` `M` `docs/locales/hu/LC_MESSAGES/disclaimer.po`
- `S04` `M` `docs/locales/hu/LC_MESSAGES/download.po`
- `S04` `M` `docs/locales/hu/LC_MESSAGES/explanation/building-on-earlier-filings.po`
- `S04` `M` `docs/locales/hu/LC_MESSAGES/explanation/editing-and-verifying.po`
- `S04` `M` `docs/locales/hu/LC_MESSAGES/explanation/from-records-to-figures.po`
- `S04` `M` `docs/locales/hu/LC_MESSAGES/explanation/how-renta-is-assembled.po`
- `S04` `M` `docs/locales/hu/LC_MESSAGES/explanation/index.po`
- `S04` `M` `docs/locales/hu/LC_MESSAGES/explanation/recording-a-filing-and-the-boundary.po`
- `S04` `M` `docs/locales/hu/LC_MESSAGES/explanation/reviewing-and-exporting.po`
- `S04` `M` `docs/locales/hu/LC_MESSAGES/how-to/authenticate-with-aeat.po`
- `S04` `M` `docs/locales/hu/LC_MESSAGES/how-to/calculation-summary.po`
- `S04` `M` `docs/locales/hu/LC_MESSAGES/how-to/censo-update.po`
- `S04` `M` `docs/locales/hu/LC_MESSAGES/how-to/check-aeat-notifications.po`
- `S04` `M` `docs/locales/hu/LC_MESSAGES/how-to/choose-modelo.po`
- `S04` `M` `docs/locales/hu/LC_MESSAGES/how-to/classify-transactions.po`
- `S04` `M` `docs/locales/hu/LC_MESSAGES/how-to/classify-with-llm.po`
- `S04` `M` `docs/locales/hu/LC_MESSAGES/how-to/connect-an-agent.po`
- `S04` `M` `docs/locales/hu/LC_MESSAGES/how-to/correct-ledger-entries.po`
- `S04` `M` `docs/locales/hu/LC_MESSAGES/how-to/file-at-aeat.po`
- `S04` `M` `docs/locales/hu/LC_MESSAGES/how-to/filing-calendar.po`
- `S04` `M` `docs/locales/hu/LC_MESSAGES/how-to/filing-readiness.po`
- `S04` `M` `docs/locales/hu/LC_MESSAGES/how-to/filing-spine.po`
- `S04` `M` `docs/locales/hu/LC_MESSAGES/how-to/fill-in-and-file-in-the-workbench.po`
- `S04` `M` `docs/locales/hu/LC_MESSAGES/how-to/first-quarterly-filing.po`
- `S04` `M` `docs/locales/hu/LC_MESSAGES/how-to/import-bank-statements.po`
- `S04` `M` `docs/locales/hu/LC_MESSAGES/how-to/index.po`
- `S04` `M` `docs/locales/hu/LC_MESSAGES/how-to/irpf-lifecycle.po`
- `S04` `M` `docs/locales/hu/LC_MESSAGES/how-to/iva-lifecycle.po`
- `S04` `M` `docs/locales/hu/LC_MESSAGES/how-to/ledger-evidence.po`
- `S04` `M` `docs/locales/hu/LC_MESSAGES/how-to/manage-invoices.po`
- `S04` `M` `docs/locales/hu/LC_MESSAGES/how-to/modelo-036.po`
- `S04` `M` `docs/locales/hu/LC_MESSAGES/how-to/modelo-100.po`
- `S04` `M` `docs/locales/hu/LC_MESSAGES/how-to/modelo-130.po`
- `S04` `M` `docs/locales/hu/LC_MESSAGES/how-to/modelo-303.po`
- `S04` `M` `docs/locales/hu/LC_MESSAGES/how-to/modelo-349.po`
- `S04` `M` `docs/locales/hu/LC_MESSAGES/how-to/modelo-390.po`
- `S04` `M` `docs/locales/hu/LC_MESSAGES/how-to/onboarding.po`
- `S04` `M` `docs/locales/hu/LC_MESSAGES/how-to/profile-setup.po`
- `S04` `M` `docs/locales/hu/LC_MESSAGES/how-to/prorrata.po`
- `S04` `M` `docs/locales/hu/LC_MESSAGES/how-to/protect-data-access.po`
- `S04` `M` `docs/locales/hu/LC_MESSAGES/how-to/quickstart.po`
- `S04` `M` `docs/locales/hu/LC_MESSAGES/how-to/reconcile.po`
- `S04` `M` `docs/locales/hu/LC_MESSAGES/how-to/review-calculation-values.po`
- `S04` `M` `docs/locales/hu/LC_MESSAGES/how-to/review-with-google-sheets.po`
- `S04` `M` `docs/locales/hu/LC_MESSAGES/how-to/troubleshooting.po`
- `S04` `M` `docs/locales/hu/LC_MESSAGES/how-to/verification-reports.po`
- `S04` `M` `docs/locales/hu/LC_MESSAGES/index.po`
- `S04` `M` `docs/locales/hu/LC_MESSAGES/reference/commands-and-configuration.po`
- `S04` `M` `docs/locales/hu/LC_MESSAGES/reference/filesystem-state-and-safety.po`
- `S04` `M` `docs/locales/hu/LC_MESSAGES/reference/import-export-and-evidence.po`
- `S04` `M` `docs/locales/hu/LC_MESSAGES/reference/index.po`
- `S04` `verify:` `uv run --no-sync python -m scratch_locale_tone.po gate` -> `pass`
- `S04` `by:` `root; independent source-meaning and informal-register review`
- `S04` `verify:` `uv run --no-sync pytest -q -n 0 -p no:randomly -m unit dev/docs/tests/test_docs_build_localized_hu.py` -> `pass`
- `S04` `by:` `root`

## Notes

- `S01` Four corrected Hungarian strings use keys absent from HEAD and remain with concurrent uncommitted TUI caller work; they are excluded from the isolated runtime commit. The original 18-pilot/1371-fleet immutable baselines and accepted official-corpus update receipts remain intact.
- `S02` Correction to the earlier S02 verification label: `parent_ca_adjudications.json` was a misrecorded filename. The actual independently reviewed exact-span packet is `parent_ca_adj_01.json,` and its owning seal command with --adjudications passes.
