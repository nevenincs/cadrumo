---
tags:
  - '#exec'
  - '#cli-root-verb-homes'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:307f039cffc7f3753c4f6b5f7ae45b654155462eee46596807c776b9c9b90c86'
step_id: 'S28'
related:
  - "[[2026-08-26-cli-root-verb-homes-plan]]"
---

# Land the spelling gate over declared locus with path-and-function keyed exemptions and a staleness ratchet

## Scope

- `src/cadrumo/entrypoints/cli/tests/`

## Changes

- `A` `src/cadrumo/entrypoints/cli/tests/test_local_path_spelling.py`
- `M` `src/cadrumo/entrypoints/cli/_app_ledger_evidence_command_specs.py`
- `M` `src/cadrumo/entrypoints/cli/tests/test_transport_locus_declared.py`
- `verify:` `pytest test_local_path_spelling.py` -> `pass`

## Notes

The spelling census corrected a declaration made in W01: `app ledger evidence
batch --file` was declared auxiliary beside a positional directory, but the
verb's own help says either input combines with or replaces the other. Both are
primary, and the one-primary invariant is re-keyed on (locus, shape) rather than
direction alone.
