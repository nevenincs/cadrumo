---
tags:
  - '#audit'
  - '#cadrumo-product-rename-s92-formatter-remediation'
date: '2026-07-13'
modified: '2026-07-13'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

# `cadrumo-product-rename-s92-formatter-remediation` audit: `S92 formatter remediation review`

## Scope

- Independently review exact commit `e513202907fec89a06cad8a0218db67c76e01243`
  against the accepted rename ADR, the active plan, the failed S91 review, and
  the S91 and S92 execution records.
- Verify production formatter-root extraction, manager-level cross-locale
  drift, strict-renderer preconditions and postconditions, non-strict
  compatibility, real-behavior tests, execution evidence, plan state, live
  locale commands, static quality, vault integrity, and diff hygiene.
- Make no implementation fix and preserve concurrent shared-tree work; create
  and commit only this audit record.

## Findings

No critical, high, medium, or low findings were found. Verdict: **PASS**.

Both prior HIGH findings are closed. `extract_placeholders` retains
`string.Formatter.parse` as the valid-format authority, reduces attribute and
index fields to the kwargs consumed by runtime, and recursively parses nested
format specifications. The exact acceptance value
`{user.name} {items[0]} {amount:{width}.{precision}f}` reports `user`, `items`,
`amount`, `width`, and `precision`. Independent probes also confirm conversions,
escaped braces, empty and numeric positional fields, prose braces, JSON-like
braces, and recovery of valid supported fields around malformed syntax. The
manager consumes this production extractor directly, and its real-filesystem
test detects renamed roots and omitted nested fields across all four locales.

Strict rendering keeps the pre-interpolation missing-root check and now records
whether the all-or-nothing format pass completed. When JSON-like, prose,
positional, or malformed braces make that pass fail, supported named fields are
recovered from the unchanged value and `UnmatchedPlaceholderError` is raised
instead of returning an unresolved token. Direct probes with a supplied
`{name}` reproduce the raise for all four failure classes, including malformed
syntax before the named field. Complete attribute, index, and nested-spec
rendering succeeds; omitting each of the five required roots raises; escaped
literal braces render successfully. The ordinary non-strict interpolation
wrapper retains its established partially rendered fallback.

The tests import the public extractor, renderer, and manager, use real temporary
YAML catalogues and production strict-mode setup, and introduce no fake, mock,
stub, patch, monkeypatch, skip, xfail, mirrored parser, or test-owned business
logic. The two owned test modules pass all 23 tests. Ruff check, Ruff format
check, and Ty pass on all three owned Python files, and the exact commit passes
`git diff --check`.

The broader i18n, locale, and parity run reports 69 passed and six failures. All
six are the independently reproduced, out-of-scope `Cadrumo` versus `CADRUMO`
identity expectation failures disclosed in the S92 record; none exercises the
formatter remediation. With isolated unsecured state, live locale `audit` and
`scaffold --check` both report `ca.yml`, `en.yml`, `es.yml`, and `hu.yml` as
`ok`. Feature-scoped vault validation exits zero with only pre-existing modified
stamp, template-annotation, and stale-index warnings.

The exact commit changes only the shared renderer, its cohesive formatter test,
the locale audit test, the S91 and S92 execution records, and the S92 plan
checkbox. S91's evidence now truthfully says eight new tests and records its
failed review. The plan leaves S67 and S91 open and closes only S92, as required.

This PASS is strictly scoped to the S92 formatter remediation. The independent
S93 authority review at `ef9bbc64fe` reports a separate HIGH finding on thirteen
cross-committed plan closures that still encode the repudiated `Cadrumo` casing.
That authority defect blocks feature-level acceptance and is consistent with
the six broader-slice failures above; this audit does not close S91, S67, or the
rename feature.

## Recommendations

- Accept S92, in formatter scope only, as closing both formatter-related HIGH
  findings from the S91 review.
- Keep S91 open until its validator transaction receives renewed acceptance,
  and keep S67 open until the generated locale parity step is complete.
- Resolve the separately owned product-display casing expectation failures in
  their authority lane; they do not block this formatter repair.
