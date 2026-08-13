---
tags:
  - '#exec'
  - '#registry-suite-red-at-head'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:f2273562a3b643c44ac57d7c2b24a9b2b36b8fa8d7fe368d4d6fb2f139017abe'
step_id: 'S04'
related:
  - "[[2026-08-13-registry-suite-red-at-head-plan]]"
---
# Make registry verification scope explicit in operator output

## Scope

- `src/cadrumo/application/registry/__init__.py`
- `src/cadrumo/entrypoints/cli/registry.py`
- `src/cadrumo/entrypoints/cli/_registry_payloads.py`
- `src/cadrumo/entrypoints/cli/tests/test_registry_cli.py`
- `src/cadrumo/locales/`

## Description

Extended the canonical registry report and strict CLI payload with explicit
verified and unverified invariant-family tuples. The verify command now states
that catalogue/corpus integrity, revision-section contracts, and relation source
coordinate coverage ran, while export-layout population and published-design
span attribution remain outside its scope. Both lists render in human output
through localized metric labels and remain typed in JSON.

## Outcome

The real `aeat --format json app registry verify` command exits zero and emits
the exact two lists. Its focused CLI test passes through the real registry and
corpus. Ruff is clean; the changed application, payload, and test surfaces have
zero BasedPyright diagnostics; all four locale scaffold checks pass; scoped
diff-check is clean.

## Notes

The command does not pretend that layout absence is universally invalid: many
real revisions intentionally have no filing-grade layout. Enumerating that
unverified family is therefore more truthful than adding a blanket population
rule. The production registry validator already owns relation coordinate
coverage, including offset years and split revisions, so that family is named
as verified rather than reimplemented in the CLI.
