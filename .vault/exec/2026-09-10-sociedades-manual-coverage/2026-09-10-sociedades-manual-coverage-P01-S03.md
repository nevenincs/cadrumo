---
tags:
  - '#exec'
  - '#sociedades-manual-coverage'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:3721df296a80273f95c12b40ccb11f2fb3ec28d7b03efcd70568bc64c8147365'
step_id: 'S03'
related:
  - "[[2026-09-10-sociedades-manual-coverage-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Carry annual-manual coverage state through the stable CLI output contract

## Scope

- `src/cadrumo/entrypoints/cli`

## Changes
- `M` `src/cadrumo/entrypoints/cli/_registry_corpus.py`
- `M` `src/cadrumo/entrypoints/cli/_registry_corpus_payloads.py`
- `M` `src/cadrumo/entrypoints/cli/tests/test_registry_corpus.py`
- `M` `src/cadrumo/core/redaction/rules.py`
- `verify:` `uv run pytest -n 0 -m "hex_entrypoint and integration" src/cadrumo/entrypoints/cli/tests/test_registry_corpus.py::test_manuals_list_emits_json_payload -q --disable-warnings --maxfail=1` -> `pass`
