---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:0dbf444e6ae8ded6d3daa297a48a31471673bd24a0078af924d5b75225111060'
step_id: 'S117'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Scrub runner hostnames from the CI control-plane document in favour of role names

## Scope

- `.github/ci-control-plane.md`

## Changes

- `M` `.github/ci-control-plane.md`
- `verify:` `uv run --no-sync python -m pytest dev/quality/tests/test_doc_privacy.py -n0` -> `pass`

## Notes

Scrubbed rather than allowlisted, on the operator's instruction: the hostnames
were not necessary in a tracked GitHub document and the recorded values were
wrong besides. The table now names the two hosts by role, and the document says
that `ci-fleet` is where machine identity is declared -- which it already
identified as the binding declaration, so this file was restating an identity it
does not own and was restating it incorrectly.

The shapes the pins are derived from are unchanged, because the shape is what
the document actually needs from a host.
