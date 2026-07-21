---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S91'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

# Enforce locale scalar and placeholder parity in the production audit

## Scope

- `locale manager`
- `shared interpolation grammar`
- `and cohesive audit tests`

## Description

- Promote `extract_placeholders` as the single production interpolation
  grammar used by strict rendering, catalogue audit, and call-site parity
  tests.
- Add immutable manager-owned audit records for codebase drift, non-string
  scalar leaves, symmetric inter-locale key drift, and shared-key placeholder
  drift.
- Make the developer audit and scaffold check commands delegate validation to
  the manager and render its structured findings without duplicating policy.
- Exercise the validator against real temporary YAML catalogues, the production
  locale manager and CLI, and the four committed catalogues.
- Verify the focused and broader locale surfaces, formatting, lint, typing,
  live audit behavior, scaffold behavior, and the explicit-path diff.

## Outcome

- `LocaleManager.audit` now returns one immutable `LocaleAuditResult`. Its file
  records distinguish missing and extra codebase keys, keys absent from each
  locale relative to the union of every intended catalogue, and leaves whose
  runtime type is not exactly `str`. Placeholder mismatches carry every
  locale's set for the affected shared key, so no language is treated as the
  canonical comparison source.
- YAML booleans and nulls are rejected as `bool` and `NoneType` leaves rather
  than being stringified. Missing, renamed, and additional placeholders are
  rejected in both `%{name}` and `{name}` forms.
- `extract_placeholders` uses the production percent-token grammar followed by
  `string.Formatter` parsing. It retains conversions and format specifications,
  ignores escaped braces and brace-delimited prose that is not an identifier,
  and does not interpret positional braces as named placeholders. Strict
  extraction remains behind the existing test-only flag, preserving the
  production translation fast path.
- CLI failures identify `inter-locale missing`, `non-string leaf`, or
  `placeholder mismatch` together with the locale file, dotted key, runtime
  type, and complete placeholder variants. A failed structured report exits
  with status one; a clean report retains the established per-file `ok` output.
- Eight new real-filesystem audit tests cover bool and null leaves, symmetric
  key drift, missing, renamed, and extra placeholders in both syntaxes,
  conversions, escaped and literal braces, the live Typer rejection path, and
  successful validation of all committed catalogues. The pre-existing
  call-site parity tests now import the production extractor instead of owning
  mirrored regular expressions.
- The complete focused surface passed fifty-three tests: the core i18n suite,
  new audit suite, and complete parity module. An independent narrower rerun
  passed thirty-eight tests.
- Ruff check, Ruff format check, Ty, and `git diff --check` passed on all six
  Python paths. Under isolated CADRUMO state, both
  `python -m cadrumo.locales audit` and
  `python -m cadrumo.locales scaffold --check` reported `ca.yml`, `en.yml`,
  `es.yml`, and `hu.yml` as `ok`.
- The shared-branch feature-surface gate completed successfully. Its scoped
  `vault check all` returned zero errors; the eighty-six warnings are existing
  modified stamps, scaffold annotations, and feature-index drift outside S91's
  owned paths.
- Independent review commit `9b372bba` returned **FAIL** with two HIGH findings
  and one LOW evidence defect. The first HIGH found that extraction omitted
  attribute and indexed roots and nested format-specification fields. The second
  HIGH found that strict rendering could return an unresolved supported named
  token after the format pass failed. The LOW finding corrected this record's
  new-test count from eleven to eight.
- S91 is reopened pending independent re-review. S92 owns the two HIGH
  remediations; S67 remains required and open.

## Notes

- The first live developer-command probe inherited a retired `aeat.db` from
  the checkout's default state and was refused before locale command startup by
  the existing former-product safety guard. Re-running with isolated CADRUMO
  storage and database settings passed both commands; no state was migrated,
  read, or changed.
- One independent fifty-three-test invocation exceeded its initial 55-second
  shell bound under shared load. The identical command then passed all tests in
  61.86 seconds with a realistic bound; the delegated executor's prior run had
  also passed all fifty-three in 39.15 seconds.
- Supervisor review removed a remaining strict-mode regex duplication, guarded
  extraction behind the strict flag to avoid production help-screen overhead,
  and strengthened the valid temporary-catalogue case to prove the whole audit
  result is clean against a real discovered source key.
- No locale YAML, runtime command surface, documentation, packaging, or
  persistence file changed. Independent formal review follows this Step.
- The active plan was updated through the plan CLI before the current hold to
  reopen S91 and add S92. This execution-record lane made no plan hunk, and the
  plan remains frozen while the authority overlap is resolved.

## Final acceptance and closure

S91 was implemented in `ee4bb7f9ad9d772461b8ef7f7cd46a14fa70b6ed`.
Its independent audit, `9b372bba70172c8012d349a60a83bd06102fbfdf`,
failed with two HIGH findings—incorrect root and nested formatter extraction
and a strict-mode failed-format survivor—and one LOW correction reducing the
reported new-test count from eleven to eight. S92 remediation
`e513202907fec89a06cad8a0218db67c76e01243` fixed both HIGH defects;
independent S92 audit `ee4f25296afeb4cff2ba5a6401639478bca66dd6`
passed with no findings and confirmed both closed, without independently
authorizing S91 closure. S94 implementation
`132f9b5352877b9ec8e36c6c32b5373cefa529fb` and PASS audit
`1ab78e51764147b4e308ebec0b2206ab059b70d9` subsequently cleared the separate
authority and plan blocker while leaving reopened descendants open.

Renewed acceptance against the current tree confirmed that the production
`extract_placeholders` probe for
`{user.name} {items[0]} {amount:{width}.{precision}f}` returns exactly
`amount`, `items`, `precision`, `user`, and `width`. Focused production
formatter and real-filesystem manager and live-CLI audit coverage passed all
23 tests. The formatter cases cover clean attribute, index, and nested
rendering; missing root and nested arguments for all five placeholders; strict
rejection after JSON, prose, positional, and malformed format failures;
escaped-literal success; and non-strict fallback. The manager and CLI cases
cover boolean, null, key, root, and nested placeholder diagnostics and CLI
rejection. Ruff format check, Ruff check, and Ty also passed across the seven
S91 and S92 production and test Python paths.

The broader i18n, locales, and parity slice was not green: 69 tests passed and
six failed. All six failures are stale `Cadrumo` expectations—two in
`test_render_override.py` and four in `test_parity.py`—against the
authoritative `CADRUMO` product display; none is a locale-validator failure.
With fresh isolated valid CADRUMO state, live
`python -m cadrumo.locales audit` and
`python -m cadrumo.locales scaffold --check` runs both reported `ca.yml`,
`en.yml`, `es.yml`, and `hu.yml` as `ok`. Naming remains `CADRUMO` for product
display, `cadrumo` for Python imports, `aeat` as the sole human CLI, and `AEAT`
for the authority.

This renewed evidence accepts and closes S91 only. S62–S67, S25, the
S94-reopened descendants, and the feature remain open. No locale YAML or
production code changed for this closure.
