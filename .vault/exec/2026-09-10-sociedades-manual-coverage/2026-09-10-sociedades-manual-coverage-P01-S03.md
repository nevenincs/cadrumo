---
tags:
  - '#exec'
  - '#sociedades-manual-coverage'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:f9d2866e9fd8b0bd7df0659bb3d43d68da5c6702dbb95297910a8912183e5e2b'
step_id: 'S03'
related:
  - "[[2026-09-10-sociedades-manual-coverage-plan]]"
---

# Carry annual-manual coverage state through the stable CLI output contract

## Scope

- `src/cadrumo/entrypoints/cli`

## Changes
- `M` `src/cadrumo/entrypoints/cli/_registry_corpus.py`
- `M` `src/cadrumo/entrypoints/cli/_registry_corpus_payloads.py`
- `M` `src/cadrumo/entrypoints/cli/tests/test_registry_corpus.py`
- `M` `src/cadrumo/core/redaction/rules.py`
- `verify:` `uv run pytest -n 0 -m "hex_entrypoint and integration" src/cadrumo/entrypoints/cli/tests/test_registry_corpus.py::test_manuals_list_emits_json_payload -q --disable-warnings --maxfail=1` -> `pass`
