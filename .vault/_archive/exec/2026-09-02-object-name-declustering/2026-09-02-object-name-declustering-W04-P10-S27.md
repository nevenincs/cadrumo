---
tags:
  - '#exec'
  - '#object-name-declustering'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:512c8b1a6c99e5f3555ec8219c105e28e1298c11704ee94cb7f46a7f51ca2c2d'
step_id: 'S27'
related:
  - "[[2026-09-02-object-name-declustering-plan]]"
---

# Carry the S23 distinction through rehearsal: require the copied inventory to equal the supplied current inventory, record that current digest in the receipt, and leave the authored inventory value bound only through the exact manifest digest, since the receipt currently records the manifest value and refuses at the next mandatory phase whatever the validator tolerated (Terra xhigh fixes and refactors)

## Scope

- `dev/quality/object_name_rehearsal.py`
- `dev/quality/object_name_replay.py`

## Changes

- `M` `dev/quality/object_name_rehearsal.py`
- `M` `dev/quality/tests/test_object_name_rehearsal.py`
- `A` `.vault/audit/2026-09-07-object-name-declustering-s27-implementation-review-audit.md`
- `verify:` `uv run --no-sync pytest dev/quality/tests/test_object_name_rehearsal.py -q` -> `pass`
- `verify:` `uv run --no-sync ruff check dev/quality/object_name_rehearsal.py dev/quality/tests/test_object_name_rehearsal.py` -> `pass`
- `verify:` `uv run --no-sync ruff format --check dev/quality/object_name_rehearsal.py dev/quality/tests/test_object_name_rehearsal.py` -> `pass`
- `verify:` `uv run --no-sync basedpyright dev/quality/object_name_rehearsal.py dev/quality/tests/test_object_name_rehearsal.py` -> `pass`

## Notes

- `uv run --no-sync ty check dev/quality/object_name_rehearsal.py dev/quality/tests/test_object_name_rehearsal.py` remains blocked by three out-of-scope diagnostics: one pre-existing source diagnostic and two in a peer-owned test hunk.
