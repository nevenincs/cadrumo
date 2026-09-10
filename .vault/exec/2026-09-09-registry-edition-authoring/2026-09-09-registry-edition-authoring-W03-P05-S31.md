---
tags:
  - '#exec'
  - '#registry-edition-authoring'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:295049919cb695648ec733c75ea94f992cec037819ecbc8ed09d67662e941943'
step_id: 'S31'
related:
  - "[[2026-09-09-registry-edition-authoring-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# [M | opus-medium] Give the materialised edition a reader, so a person can see a complete edition without reconstructing it mentally from a delta. Without this the tree is harder to work with, not easier. Proof: the reader renders a migrated edition identically to its pre-migration files.

## Scope

- `src/cadrumo/entrypoints/cli`

## Changes

- `A` `src/cadrumo/application/registry/edition.py`
- `M` `src/cadrumo/application/registry/errors.py`
- `M` `src/cadrumo/application/registry/tests/test_terminal_preconditions.py`
- `M` `src/cadrumo/core/toml.py`
- `M` `src/cadrumo/core/tests/test_toml.py`
- `M` `src/cadrumo/entrypoints/cli/registry.py`
- `A` `src/cadrumo/entrypoints/cli/_registry_edition_payloads.py`
- `M` `src/cadrumo/entrypoints/cli/_registry_command_specs.py`
- `M` `src/cadrumo/entrypoints/cli/_bootstrap_exempt.py`
- `A` `src/cadrumo/entrypoints/cli/tests/test_registry_view_edition_cli.py`
- `M` `src/cadrumo/entrypoints/cli/tests/test_registry_command_specs.py`
- `M` `src/cadrumo/locales/en/cli.yml`
- `M` `src/cadrumo/locales/es/cli.yml`
- `M` `src/cadrumo/locales/ca/cli.yml`
- `M` `src/cadrumo/locales/hu/cli.yml`
- `M` `src/cadrumo/locales/en/application.yml`
- `M` `src/cadrumo/locales/es/application.yml`
- `M` `src/cadrumo/locales/ca/application.yml`
- `M` `src/cadrumo/locales/hu/application.yml`
- `verify:` `pytest -m integration test_registry_view_edition_cli.py` -> `pass`
- `verify:` `pytest test_toml.py test_registry_command_specs.py test_terminal_preconditions.py` (new tests) -> `pass`
- `verify:` `aeat app registry verify` -> `pass`
- `verify:` `ruff check`, `ruff format --check`, `ty check` on every touched Python file -> `pass`
- `verify:` `python -m dev.locales audit` -> `fail` (pre-existing findings only, none on the new keys)

## Notes

- `dev.locales` is unimportable at HEAD (`_registry_scanner.py` imports the removed `profile_schema_locale_keys`). The new keys were written through `dev.locales set-batch` and audited, from a scratch runner that restores the removed function in memory only. The tool itself was not repaired.
- Pre-existing failures, all outside the touched surfaces: inspect/diff CLI strict tuple validation, `_modelo_discovery_cli` facade import, modelo legacy selector calls, corpus refusal contract, `flows.*` surplus kwargs, output-language and `tr`-binding gates, and OS-keychain refusals in the `app ledger` subprocess tests. The first six also fail on a detached HEAD worktree.
- The reviewer persona could not be launched from this session, so the review is still outstanding.

- The reviewer persona could not be launched. The orchestrating session reviewed the diff against the CLI contract and the ADR. The command extends `aeat app registry`, with positional subjects and one application service, and the service reads only through `materialise_edition`. The bootstrap exemption entry classifies the command as read-only; it is not a suppression. Locale keys are added in all four locales. Re-run: the reader, TOML, command-spec and precondition tests pass except `test_corpus_refusals_classify_selection_and_missing_extraction_state`, which this Step did not touch and which fails on clean HEAD. `registry verify` exit 0; ruff and ty clean.
