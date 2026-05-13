---
tags:
  - '#exec'
  - '#audits-resolution'
date: '2026-05-13'
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
reason; `get_codebase_keys` now unions its regex output with the new
AST scanner's findings.

`src/aeat/locales/_ast_scanner.py` (new): walks every `.py` module
under the source tree and emits three classes of finding:

- Positional / `message_key=` string literals passed to constructors
  whose class name ends in `Error` / `Exception`. Catches
  `WizardValidationError("wizard.errors.select_unknown")`.
- Every f-string whose leading segment matches the translation-key
  shape `^\w+(\.\w+)+$`. Emits a `<prefix>.*` namespace marker for
  later parity checks. Catches both `tr(f"…")` call sites and the
  assignment form (`key = f"wizard.errors.{reason}"`).
- `tr("<literal>" + x)` concatenations whose left operand matches
  the key shape. Catches the
  `tr("cli.registry.metrics." + key)` dynamic namespace in
  `entrypoints/cli/registry.py`.

The translation-key shape is constrained by
`^\w+(\.\w+)+$ + re.UNICODE` so file paths, URLs, error messages
with embedded dots, and other noisy f-strings do not register as
namespace markers.

## verification

`LocaleManager.get_codebase_keys()` now returns:

- `cli.filing.import.año_help` (Unicode key, previously dropped).
- `wizard.errors.*` namespace marker (programmatic emission from
  `_widgets._fail`).
- `cli.registry.metrics.*` namespace marker (concatenation pattern
  in `entrypoints/cli/registry.py:_emit_metric`).
- The other dotted namespace markers discovered organically:
  `cli.config.*`, `profile.keys.*`, `residence.ccaa.choices.*`,
  `wizard.demo.section.*`, `wizard.setup.*`,
  `filing.test_calculate.finding_.*`.

`audit_cli_translations()` now reports the missing-locale gaps for
the discovered keys — those gaps land in B5.

`ruff check src/aeat/locales/_ast_scanner.py` and
`ty check src/aeat/locales/` both green.
