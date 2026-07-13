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
- Eleven new real-filesystem audit tests cover bool and null leaves, symmetric
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
