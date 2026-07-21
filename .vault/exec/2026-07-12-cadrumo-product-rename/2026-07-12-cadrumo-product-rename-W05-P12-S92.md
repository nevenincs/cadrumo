---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S92'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

# Remediate formatter-field extraction and strict interpolation postconditions

## Scope

- `shared i18n grammar`
- `locale audit`
- `cohesive renderer and audit tests`

## Description

- Delegate the S91 review remediation across the production formatter grammar
  and real-behavior tests.
- Keep `string.Formatter.parse` as the runtime-aligned parsing authority. Extract
  attribute and indexed field roots, recurse through nested format
  specifications, and recover supported roots around malformed braces without
  claiming complete parsing.
- Restore strict interpolation's postcondition. A failed format pass must raise
  when it would otherwise return an unresolved supported named token, while the
  existing missing-root precondition remains intact.
- Limit implementation scope to `src/cadrumo/core/i18n/_render.py`,
  `src/cadrumo/core/i18n/tests/test_formatter_contract.py`, and
  `src/cadrumo/locales/tests/test_audit.py`.
- Leave the locale manager and CLI unchanged. Both consume the shared production
  extractor, so the corrected root and nested-field grammar flows through their
  existing audit path without duplicated policy.

## Outcome

- The delegated implementation covers root kwargs for attribute and indexed
  fields and recursively discovers named fields inside format specifications.
  Malformed inputs use safe recovery, and strict mode preserves both missing-root
  detection and the unresolved-token postcondition after format failure.
- The final focused formatter and audit surface passed 24 tests. The broader
  pre-final locale slice passed 109 tests.
- The final broader run collected 110 tests: 104 passed, and six failed on
  unrelated concurrent stale `Cadrumo` versus `CADRUMO` expectations.
- The feature-surface gate passed Ruff format check, Ruff check, and Ty check on
  all three owned files. The two owned test modules passed 23 tests, and
  `git diff --check` passed.
- Feature-scoped `vault check all --feature cadrumo-product-rename` exited zero.
  Structure, frontmatter, Markdown, links, dangling references, body links,
  placeholders, orphans, integrity, references, schema, architecture decision
  records, and encoding were clean.
- The feature-scoped vault check reported 87 pre-existing warnings outside the
  S92 repair: 26 modified stamps, 60 template annotations, and one stale feature
  index.
- With valid isolated unsecured state, live locale audit and scaffold checks
  reported `ca.yml`, `en.yml`, `es.yml`, and `hu.yml` as `ok`.
- No manager or CLI diagnostic code changed. The manager and CLI receive the
  corrected behavior through the shared extractor.
- The S92 implementation is complete against authority baseline `9ea3b77f24`.
  S92 was closed through the plan CLI; independent review remains pending.

## Notes

- The first live locale probe encountered the retired `aeat.db` guard before
  command startup. Subsequent attempts with an invalid memory-backend setting
  also failed configuration validation. The valid isolated unsecured
  environment then passed both live commands without reading or migrating the
  retired database.
- Authority repair landed at baseline `9ea3b77f24` before S92 closure. The exact
  S92 plan hunk changes only the S92 checkbox through the plan CLI. S91 and the
  known-required S67 remain open pending their respective completion and review.
- No product-casing documentation, locale YAML, catalogue, packaging, manager,
  or CLI file changed in this remediation lane.
