---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:fc4c6a6fceac548b68f96809809ff47d617188d8255c8660e2df5c568290ae90'
step_id: 'S318'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Remove embedded implementations and hardcoded owner strings from the CSV singularity gate

## Scope

- `AEAT CSV live singularity scan`
- `canonical CSV behavior`
- `exact reachability`
- `cadence reference`
- `and Step Record`

## Changes

- `M` `src/cadrumo/tests/test_aeat_csv_normalisation_singularity.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync pytest -q src/cadrumo/tests/test_aeat_csv_normalisation_singularity.py` -> `pass`
- `verify:` `uv run --no-sync pytest -q src/cadrumo/core/tests/test_aeat_csv_shape.py` -> `pass`
