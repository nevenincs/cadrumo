---
tags:
  - '#exec'
  - '#audits-resolution'
date: '2026-05-13'
modified: '2026-05-13'
related:
  - "[[2026-05-13-audits-resolution-plan]]"
  - "[[2026-05-13-schema-driven-wizard-ux-audit]]"
---

# audits-resolution group-b step-4

## scope

Plan row B4: widen the locale-discovery regex to Unicode and add an
AST-based scanner that catches programmatic emissions and dynamic
namespaces.

## changes

`src/aeat/application/wizard/_translations.py`: `_CLI_KEY_PATTERN`
flips from the ASCII character class `[A-Za-z0-9_]+` to `\w+` with the
`re.UNICODE` flag so non-ASCII keys are discovered.

`src/aeat/locales/manager.py`: the regex used by
`LocaleManager.get_codebase_keys` is widened to `\w+` for the same
reason; the `AeatError` import is lifted to the top of the file so
`ruff` no longer flags E402; `get_codebase_keys` now unions its
regex output with the new AST scanner's findings.

`src/aeat/locales/_ast_scanner.py` (new): walks every `.py` module
under the source tree and emits three classes of finding:

- Positional / `message_key=` string literals passed to constructors
  whose class name ends in `Error` / `Exception`. Catches
  `WizardValidationError("wizard.errors.select_unknown")`.
- Every f-string whose leading segment matches the translation-key
  shape `^\w+(\.\w+)+$`. Emits a `<prefix>.*` namespace marker for
  later parity checks. Catches both `tr(f"…")` call sites and the
  assignment form (`key = f"wizard.errors.{reason}"`).
- `tr("<literal>" + x)` and `t("<literal>" + x)` concatenations
  whose left operand matches the key shape. Catches
  `tr("cli.registry.metrics." + key)` in
  `entrypoints/cli/registry.py`.

The translation-key shape is constrained by
`^\w+(\.\w+)+$ + re.UNICODE` so file paths, URLs, error messages
with embedded dots, and other noisy f-strings do not register as
namespace markers.

## unblock fixes (concurrent-stream territory)

Two pre-existing ty failures in concurrent-agent files blocked the
project-wide hook. Both are auth/review surface mismatches between
untracked operator helpers and the tracked package surface:

- `src/aeat/application/auth/_catalogue.py` gains the
  `implemented: bool = True` field that `_operator.py` references
  through `listing.implemented`.
- `src/aeat/application/auth/__init__.py` re-exports the auth
  operator helpers (`AuthClearResult`, `AuthConfigureResult`,
  `AuthProviderReservedError`, `AuthProvidersReport`,
  `AuthStatusResult`, `clear_operator_auth`,
  `configure_operator_auth`, `inspect_operator_auth`,
  `list_operator_auth_providers`, `test_operator_auth`).
- `src/aeat/application/review/__init__.py` re-exports
  `project_review_item` and `project_review_queue` from the
  untracked `_operator.py`.

## verification

`LocaleManager.get_codebase_keys()` now returns:

- `cli.filing.import.año_help` (Unicode key, previously dropped).
- `wizard.errors.*` namespace marker (programmatic emission from
  `_widgets._fail`).
- `cli.registry.metrics.*` namespace marker (concatenation pattern
  in `entrypoints/cli/registry.py:_emit_metric`).

`ruff check` on every touched file: green.
`ty check src/`: green.
