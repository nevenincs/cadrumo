---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-07'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:2ce9558ca4db202f4af487b3e5635200e85ce81c60cfb120a2fa6f9a750f1a53'
step_id: 'S121'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the nine superseded symbols no importer reaches and pay both ratchets that recorded them

## Scope

- `dev/quality/unconsumed_export_ratchet.toml`

## Changes

- `M` `src/cadrumo/entrypoints/cli/_tty.py`
- `M` `src/cadrumo/domain/calculations/registry/modelo_localization.py`
- `M` `src/cadrumo/application/auth/certificate_sources.py`
- `M` `src/cadrumo/application/modelo/edit_models.py`
- `M` `src/cadrumo/application/user_profile/bundle.py`
- `M` `src/cadrumo/application/user_profile/commands.py`
- `M` `src/cadrumo/application/user_profile/login_session_port.py`
- `M` `dev/audit/reachability_classification.toml`
- `M` `dev/quality/unused_symbol_ratchet.toml`
- `M` `dev/quality/unconsumed_export_ratchet.toml`
- `verify:` `uv run --no-sync python -m pytest dev/audit/tests dev/quality/tests/test_orphan_test_records_agree.py -n0` -> `pass`
- `verify:` `uv run --no-sync python -m dev.quality.docstring_reference_ratchet` -> `pass`

## Notes

Triaging all twenty-one open superseded clusters by real importer counts split
them cleanly: six clusters had no importer anywhere, fifteen are still driven by
tests. The triage script itself was wrong on one of the six. It counted only
`from X import Y`, so it missed a whole test file exercising the locale
catalogue cache through `import ... as cc` and attribute access, and would have
deleted a tested cache. Nine symbols across five clusters were deletable.

Two ratchets recorded the same deletions in different files. Paying the symbol
ratchet alone left the unconsumed-export ratchet carrying three spent entries;
both are paid here.

`src/cadrumo/domain/calculations/registry/schema.py` carries a pre-existing
import-ordering finding and is another contributor's modified file. It was left
untouched rather than swept up by a tree-wide autofix.
