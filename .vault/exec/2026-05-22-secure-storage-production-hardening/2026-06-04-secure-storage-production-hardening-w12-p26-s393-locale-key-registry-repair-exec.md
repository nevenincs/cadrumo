---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S393'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# W12.P26.S393 - Locale-key registry repair

Scope: repair the locale AST scanner closeout for `src/aeat/locales/_ast_scanner.py`
after the canonical locale audit surfaced live policy keys as orphaned catalogue
entries.

## Description

- Extended the AST scanner to collect dotted locale keys declared in explicit
  `*_LOCALE_KEY` and `*_LOCALE_KEYS` constants.
- Added a scanner regression test proving bounded locale-key registries are collected
  while ordinary dictionaries are not treated as translation declarations.
- Repaired the four locale catalogues through `python -m aeat.locales scaffold` and
  `python -m aeat.locales set`, restoring substantive stub-modelo refusal messages.
- Let the locale scaffold remove the stale `cli.app.modelo.work.relation_not_decimal`
  leaf after confirming it had no production reference.

## Outcome

The canonical locale audit now recognizes `STUB_MODELO_LOCALE_KEYS` as a live
operator-facing key registry. The locale catalogues are structurally clean and no
longer carry placeholder text for the stub-modelo refusal messages.

Validation passed:

- `uv run --no-sync ruff check src/aeat/locales/_ast_scanner.py src/aeat/locales/test_parity.py src/aeat/application/wizard/_prompter.py src/aeat/application/wizard/test_prompter.py src/aeat/application/wizard/test_setup_runtime.py src/aeat/application/wizard/test_questionary_smoke.py`
- `uv run --no-sync pytest -q src/aeat/locales/test_parity.py src/aeat/application/wizard/test_prompter.py src/aeat/application/wizard/test_setup_runtime.py src/aeat/application/wizard/test_questionary_smoke.py`
- `uv run --no-sync -q python -m aeat.locales audit`

## Notes

The repair was triggered while executing the S275 prompter closeout gate. The
underlying defect was locale-scanner enrollment, not prompter behavior.
