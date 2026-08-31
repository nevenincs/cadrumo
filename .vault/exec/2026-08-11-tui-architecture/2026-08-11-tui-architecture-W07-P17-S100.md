---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-28'
modified: '2026-08-28'
body_schema: 'body-v2'
body_hash: 'sha256:e997eb4b5d49541a4de7d81ab9862e0c2efc41442ca783e61f7aa0721c1ccc40'
step_id: 'S100'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Verify profile, secret, flow, and operation surfaces at narrow, normal, and wide terminal sizes

## Scope

- `src/cadrumo/entrypoints/tui/tests/test_terminal_sizes.py`

## Changes

- `M` `src/cadrumo/entrypoints/tui/tests/test_terminal_sizes.py`
- `verify:` `uv run --no-sync pytest src/cadrumo/entrypoints/tui/tests/test_terminal_sizes.py -m integration -n0` -> `fail`

## Notes

Eleven of twelve cases pass. The profile, secret and guided-flow surfaces are
contained at 80, 120 and 200 columns; the operation modal is contained at 120
and 200 and overflows at 80.

The failure is the finding, not a defect in the check. The modal's five-button
action row leaves the detach control clipped at column 82 and the close
control wholly off-screen from 84 to 100, so on an 80-column terminal neither
is reachable. These surfaces carry no horizontal scroll affordance, and the
modal refuses to close for operations whose close policy demands a cancel
request, so an operator in that combination has no in-interface way out. The
production repair is tracked separately.

The check asserts horizontal containment only. Content taller than the
viewport is what the surfaces' scroll containers exist to carry, so a vertical
assertion would red on correct layouts. Each case first asserts the surface
rendered at least one reachable control, so a surface that failed to compose
cannot pass by having nothing to measure.

Gate proven by mutation: forcing one credential field to a fixed 150 columns
reds at 80 and 120 and stays green at 200, so the check discriminates by size
rather than failing bluntly.

Discovery for this Step ran against the local fallback index rather than the
live semantic-search service, which was down.
