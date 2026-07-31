---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
body_hash: 'sha256:4751dcd18b4a5c77919ee9548291e3152fec7ec12aaefe51322d9555c3f7797c'
step_id: 'S189'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Run self-referential CLI string conformance and reject every removed spelling

## Scope

- `src/cadrumo/entrypoints/cli/tests/test_self_referential_string_conformance.py`

## Description

Run self-referential CLI string conformance and reject every removed spelling.

## Outcome

SATISFIED.

Command: `uv run --no-sync pytest -q -rs -n0 -m "" -p no:cacheprovider
src/cadrumo/entrypoints/cli/tests/test_self_referential_string_conformance.py`.
Collected 8, 8 passed, exit line `8 passed in 4.61s`, exit code 0, at HEAD `1844ef2ea0`.

## Notes

No removed spelling survives in the self-referential string surface this suite scans. That
scan is narrower than the whole operator-facing surface: suggestion and next-action strings are
covered separately under S190, where a live defect was found. A green result here is not evidence
about that surface.

The semantic code index was degraded throughout this Phase: the service reported `Source code sections: 466` against 3982 tracked Python files while declaring its code generation succeeded. No absence recorded here rests on a semantic miss.

## Re-measurement at HEAD bc80aa2808

SATISFIED. Command: `uv run --no-sync pytest -m integration
src/cadrumo/entrypoints/cli/tests/test_self_referential_string_conformance.py`.
Collected 8, 8 passed, exit line `8 passed in 5.97s`, exit code 0, at HEAD `bc80aa2808`.
Same count as the original reading. All removed spellings remain absent.
