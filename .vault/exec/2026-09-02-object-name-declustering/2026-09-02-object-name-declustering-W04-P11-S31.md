---
tags:
  - '#exec'
  - '#object-name-declustering'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:3c55f969c9c0f030c0469ff6090f410207e4924c1481121330c91b28162771e3'
step_id: 'S31'
related:
  - "[[2026-09-02-object-name-declustering-plan]]"
---

# State the teardown invariant in the accepted record and enforce it at both verified-copy removal sites, distinguishing an artefact that is evidence from one that is litter, since a WinError 145 raised from a finally converted an apply whose six gates had all passed into a rolled-back failure (Sol architecture)

## Scope

- `.vault/adr/`
- `dev/quality/object_name_replay.py`

## Changes

- `M` `.vault/adr/2026-09-02-object-name-declustering-adr.md`
- `M` `dev/quality/tests/test_object_name_replay.py`
- `A` `.vault/audit/2026-09-07-object-name-declustering-s31-teardown-authority-review-audit.md`
- `verify:` `uv run --no-sync pytest dev/quality/tests/test_object_name_replay.py -q` -> `pass`
- `verify:` `temporary generator-copy bare-rmtree mutation; generator cleanup detector` -> `pass`
- `verify:` `uv run --no-sync ruff check dev/quality/tests/test_object_name_replay.py` -> `pass`
- `verify:` `uv run --no-sync ruff format --check dev/quality/tests/test_object_name_replay.py` -> `pass`
- `verify:` `uv run --no-sync basedpyright dev/quality/tests/test_object_name_replay.py` -> `pass`
- `verify:` `uv run --no-sync ty check dev/quality/tests/test_object_name_replay.py` -> `pass`
- `verify:` `uv run --no-sync python -m py_compile dev/quality/tests/test_object_name_replay.py` -> `pass`
