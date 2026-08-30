---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-30'
modified: '2026-08-30'
body_schema: 'body-v2'
body_hash: 'sha256:e77e7808f59747b8fdf2a05f8d92cc2260863372fa464e5cb303ff15f72a01fd'
step_id: 'S86'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# Retire the core observability facade: sixty-one names across eleven modules, with the replay canonicity gate's pinned module literal moved in the same change

## Scope

- `src/cadrumo/core/observability/`

## Changes

- `R` `src/cadrumo/core/observability/_capture.py -> capture.py`
- `R` `src/cadrumo/core/observability/_context.py -> context.py`
- `R` `src/cadrumo/core/observability/_fingerprint.py -> fingerprint.py`
- `R` `src/cadrumo/core/observability/_golden.py -> golden.py`
- `R` `src/cadrumo/core/observability/_models.py -> models.py`
- `R` `src/cadrumo/core/observability/_recorder.py -> recorder.py`
- `R` `src/cadrumo/core/observability/_redaction_rules.py -> redaction_rules.py`
- `R` `src/cadrumo/core/observability/_replay.py -> replay.py`
- `R` `src/cadrumo/core/observability/_sink.py -> sink.py`
- `R` `src/cadrumo/core/observability/_store.py -> store.py`
- `M` `src/cadrumo/core/observability/__init__.py`
- `M` `dev/registry/analysis/load_census_classification.py`
- `verify:` `pytest src/cadrumo/core/observability -n 0 -m ""` -> `pass`

## Notes

Two of the 130 tests fail on a peer's CLI verb rename (`workflow view` ->
`workflow show`) that this observability test's expectation has not caught up
with. The diff to `replay.py` is imports only, so the argv logic is untouched.
