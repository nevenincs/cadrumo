---
tags:
  - '#exec'
  - '#registry-generator'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:2c2dff6d4aaacae72c20eaebac1f8e9f60c4a711a2adac1ffb25c640e2220a97'
step_id: 'S75'
related:
  - "[[2026-09-09-registry-generator-plan]]"
---

# Recompute the root manifest aggregate from the per-modelo manifests without fetching, so the only repair path for a purely local number no longer runs across the network; the check exits 1 on `main` today recording 247 artefacts against 248 held and M270 as 1 against 2

## Scope

- `dev/corpus/sync_aeat_record_design_corpus.py`

## Changes

- `M` `dev/corpus/sync_aeat_record_design_corpus.py`
- `M` `dev/corpus/tests/test_record_design_support.py`
- `M` `src/cadrumo/_data/corpus/aeat_official/disenos_registro/manifest.json`
- `verify:` `uv run --no-sync python dev/corpus/sync_aeat_record_design_corpus.py` -> `pass`
- `verify:` `uv run --no-sync pytest dev/corpus/tests/test_record_design_support.py` -> `pass`
