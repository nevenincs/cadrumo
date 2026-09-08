---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:bc31d365f6b141f1e628a2fc321497564b9dedc230c660ef28530f437416dadc'
step_id: 'S120'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Resolve two superseded symbols by deletion rather than leaving them classified, and separate the superseded clusters that tests still exercise

## Scope

- `dev/quality/unused_symbol_ratchet.toml`

## Changes

- `M` `src/cadrumo/application/modelo/result_disposition_resolution.py`
- `M` `src/cadrumo/application/user_profile/custody_ports.py`
- `M` `src/cadrumo/core/refund_election.py`
- `M` `dev/audit/reachability_classification.toml`
- `M` `dev/quality/unused_symbol_ratchet.toml`
- `verify:` `uv run --no-sync python -m pytest dev/audit/tests -n0` -> `pass`
- `verify:` `uv run --no-sync python -m dev.quality.docstring_reference_ratchet` -> `pass`
- `verify:` `uv run --no-sync python -m pytest src/cadrumo/application/user_profile/tests -n0` -> `fail`

## Notes

Twenty-three clusters stood classified `superseded` and open, which is a
contradiction worth acting on: superseded means something replaced it, and
`no-legacy-compatibility` requires a displaced surface to go while the
compatibility regime is pre-release, which `core/compatibility_lifecycle`
confirms it is. Classification was the interim record, not the resolution.

Six single-symbol clusters were examined and only two were deletable.
`write_cached_transcription` backs a consent-withdrawal test that writes a cache
entry and checks withdrawal purges it; `save_corpus_manifest` and
`load_default_filing_profile` are likewise exercised by tests. Production having
displaced a symbol does not make it dead when a suite still drives it, and
deleting those would remove coverage rather than debt.

The failures in `src/cadrumo/application/user_profile/tests` are peer-introduced
and unrelated: capsule-generation retryable codes, custody lock ordering, and a
`workbench_bootstrap` module absent from the declared public inventory, added by
`499ef90ee0`. Neither deleted symbol is referenced anywhere in the tree.
