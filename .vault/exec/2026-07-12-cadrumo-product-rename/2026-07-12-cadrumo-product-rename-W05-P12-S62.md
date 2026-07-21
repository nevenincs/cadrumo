---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S62'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

# Bind command-help invocations to `aeat` and product copy to CADRUMO while preserving AEAT counterparty language

## Scope

- `src/cadrumo entrypoint help authorities`

## Description

- Normalize stale `cadrumo` command prefixes to the canonical `aeat` executable
  at both live rendering and locale-maintenance boundaries.
- Normalize title-case product prose to the canonical `CADRUMO` display name
  without changing lowercase package and MCP identifiers.
- Preserve `AEAT` wherever locale prose names the Spanish tax authority.
- Exercise direct production rendering, folded YAML roundtrips, locale parity,
  catalogue audits, and isolated live help behavior.

## Outcome

The shared translation renderer now projects the binding identity while the
per-language catalogue migration remains open: title-case product copy renders
as `CADRUMO`, and stale command-leading `cadrumo` tokens render as `aeat`.
The matcher covers the command forms found in the catalogues, including folded
line breaks and `manual` guidance, without rewriting the `cadrumo` distribution,
`cadrumo-mcp`, `cadrumo://`, `CADRUMO_*`, or `AEAT`.

The locale manager and its developer command apply the same referent-aware
normalization when later Steps update catalogue leaves. No locale catalogue was
modified in this Step. All 34 focused renderer and parity tests passed, both
read-only locale catalogue gates reported every language healthy, scoped Ruff
passed, and an isolated real `aeat --help` rendered `CADRUMO`, retained `AEAT`,
used `aeat <comando> --help`, and exposed no title-case product name or
`cadrumo <comando>` guidance.

## Notes

The English, Spanish, Catalan, and Hungarian catalogue bytes intentionally still
contain stale product display and command copy. Steps S63 through S66 own those
mutations through the locale CLI, and S67 owns the resulting scaffold/parity
regeneration proof.

The first locale CLI probe inherited a local retired-state database and correctly
refused it; rerunning the same read-only gates with a fresh isolated CADRUMO state
root passed. The first PowerShell live-help assertion used case-insensitive
matching and therefore mistook `CADRUMO` for title-case `Cadrumo`; the corrected
case-sensitive assertion passed against the unchanged live output. No failure
was hidden or converted to a skip.

## Regression ancestry and remediation

The original S62 transaction at `7ff822cb0f` and its independent PASS audit
established the correct render and maintenance boundary. Commit `38894cae07`
later changed four parity expectations from `CADRUMO` to title-case `Cadrumo`
under a repudiated casing ruling, and `e097d0f8ea` changed the two renderer
expectations the same way. S90 restored the binding all-caps display authority;
S93 restored that authority again after the overlapping regression chain; and
S94 truthfully reopened S62 after S93's failed descendant-closure review. S95
then restored the same runtime tuple while preserving reciprocal ADR
supersession. Subsequent authority-graph remediation leaves the accepted
`cadrumo-cli-executable` ADR as the binding source: product output is
`CADRUMO`, the human command is `aeat`, and the remote authority is `AEAT`.

This corrective pass changes only the six stale output expectations introduced
by `38894cae07` and `e097d0f8ea`. The production renderer already substitutes
`PRODUCT_IDENTITY.display_name` and `PRODUCT_IDENTITY.cli_executable`; no
production defect was found and `_render.py` remains unchanged.

## Referent-aware hit classification

- Title-case `Cadrumo` remains in input fixtures where the test deliberately
  proves normalization of stale catalogue values. It is not accepted output.
- Lowercase command-leading `cadrumo` remains in input fixtures for the same
  reason. Expected operator guidance is exactly `aeat`.
- Lowercase `cadrumo`, `cadrumo-mcp`, and `cadrumo://` remain unchanged where
  they name the package, MCP executable, or resource scheme.
- `CADRUMO_OUTPUT_LANGUAGE` remains unchanged as a product environment name.
- `AEAT` remains unchanged where the text names the Spanish tax authority.
- Six expected-output assertions now require exact `CADRUMO`: two in the live
  renderer tests and four in locale-maintenance parity tests.

## Corrective verification

- The focused renderer, S92 formatter grammar, manager audit, and parity slice
  passed 60 tests.
- The broader `core/i18n`, `locales`, and parity slice passed 75 tests.
- Isolated live `aeat --language LANGUAGE --help` checks passed for English,
  Spanish, Catalan, and Hungarian. Every output contained `CADRUMO`, retained
  `AEAT`, and used `aeat` command guidance; none contained exact title-case
  `Cadrumo` or a command-leading lowercase `cadrumo` token.
- The developer locale CLI, invoked through `python -m cadrumo.locales`, reported
  all four catalogues healthy for both `audit` and `scaffold --check`. An initial
  `aeat locales audit` probe correctly showed that locale maintenance is not a
  human `aeat` subcommand; the documented module CLI was then used.
- Ruff lint and Ty passed on both changed test files. `git diff --check` passed.
  Ruff format check remains nonzero only because `test_parity.py` carries the
  pre-existing formatting drift already recorded and independently confirmed
  by S90; this narrowly scoped remediation does not mechanically reformat
  unrelated parity content.
- The plan check passed with the known `PLAN022` ordering warning. The dedicated
  feature check passed with one pre-existing stale-index warning. The broader
  shared-vault `check all` command remains nonzero on 319 unrelated legacy
  filename-structure errors; no repair or index regeneration was attempted.

Raw catalogue bytes remain intentionally outside S62. A read-only exact-case
scan reports 13 title-case occurrences in Catalan, 10 in English, 7 in Spanish,
and 6 in Hungarian. The command-leading lowercase `cadrumo` residue scan reports
no matches. S63 through S66 retain ownership of catalogue mutations through the
locale CLI, and S67 retains the final generated parity proof.

## Ratified authority correction

Authority Step S86 landed at `4cb1006b6e` and records the binding casing
convention in the accepted executable ADR's status note: sentence prose uses
`Cadrumo`, identity contexts may use `CADRUMO`, the sole human executable is
`aeat`, and the Spanish authority remains `AEAT`. This later ruling supersedes
the earlier all-caps sentence-prose claims retained above as historical
execution evidence.

This corrective S62 pass removed the blanket `Cadrumo`-to-`CADRUMO` rewrite
from both production normalization boundaries. The shared renderer and locale
manager now normalize only unambiguous command-leading stale `cadrumo` tokens
to `aeat`. They preserve sentence-case `Cadrumo`, intentional identity-context
`CADRUMO`, lowercase package and MCP identifiers, `CADRUMO_*` environment
names, and `AEAT` authority prose. The locale maintenance command description
now states that it normalizes stale command prefixes. No locale catalogue was
modified; S63 through S66 retain ownership of catalogue corrections.

Real-behavior verification passed 60 focused renderer, formatter-contract,
locale-audit, and parity tests. Ruff lint, Ruff format, and Ty passed for all
five changed Python files. The production locale CLI reported all four
catalogues healthy through both `audit` and `scaffold --check` using isolated
valid local state. An initial read-only locale CLI attempt used the invalid
secret-store value `local` and failed validation before catalogue access; the
correct `unsecured` value then passed. No failure was hidden, skipped, or
converted to an expected failure.
