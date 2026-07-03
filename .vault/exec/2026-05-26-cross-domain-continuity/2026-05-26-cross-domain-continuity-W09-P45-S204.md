---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S204'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# fix 27 i18n SURPLUS kwargs surfaced by S32 parity validator

## Scope

- `either add placeholders to locale text or remove dead kwargs from tr call sites`
- `affected keys include application.auth.operator.errors.unreadable_active_profile cli.common.errors.invalid_iso_date cli.common.errors.period_unrecognised cli.diagnostics.summary.* cli.diagnostics.version.* cli.ledger.errors.filter_parse_error cli.operator_surface.errors.contract_not_accepted cli.operator_surface.landing.*`
- `src/aeat/`

## Description

- Ground the closure against the live implementation with `vaultspec-rag` over the S32 placeholder parity validator and its SURPLUS axis.
- Re-run the focused SURPLUS parity test for the production `tr()` call-site scan.
- Re-run the full placeholder parity module covering ORPHAN, SURPLUS, and SHADOW axes.
- Re-run the locale audit across all supported locale YAML files.
- Close the plan row as verification-only because the current worktree already satisfies the S204 acceptance condition.

## Outcome

- No production code changes were required for S204 in this pass.
- `uv run --no-sync pytest src/aeat/core/i18n/tests/test_placeholder_parity.py::test_no_surplus_kwargs -q` passed with 1 test.
- `uv run --no-sync pytest src/aeat/core/i18n/tests/test_placeholder_parity.py -q` passed with 3 tests.
- `uv run --no-sync python -m aeat.locales audit` reported `ca.yml`, `en.yml`, `es.yml`, and `hu.yml` as ok.
- The S32 parity validator now reports no remaining SURPLUS kwargs for the affected keys called out by S204.

## Notes

- This was a closure pass over fixes already present in the shared worktree. No code fixer was dispatched because the live parity gates were green before any S204 edits.
- Residual risk is limited to dynamic translation keys that the AST parity validator intentionally skips. That is the validator's documented boundary, not a scoped S204 regression.
