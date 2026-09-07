---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:40b506a40e51bb3e8458e7c6b750398bf9f0570ca7a1c663fca2560cd1a4f9bc'
step_id: 'S112'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Classify the censal review screen against the placeholder the product already shows, and ratchet the unrendered TUI interface set

## Scope

- `justfile`

## Changes

- `A` `dev/quality/tui_render_coverage_ratchet.py`
- `A` `dev/quality/tui_render_coverage_ratchet.toml`
- `A` `dev/quality/tests/test_tui_render_coverage_ratchet.py`
- `M` `dev/audit/reachability_classification.toml`
- `M` `justfile`
- `verify:` `just check-tui-render-coverage` -> `pass`
- `verify:` `uv run --no-sync python -m pytest dev/quality/tests/test_tui_render_coverage_ratchet.py -n0` -> `pass`
- `verify:` `uv run --no-sync python -m pytest dev/audit/tests -n0` -> `pass`

## Notes

The censal review screen was a wiring candidate on the same reasoning as the
journey shell and is not one. It takes five already-localized strings, and no
catalogue key or production caller supplies them, so a devtools fixture would
have to invent operator-facing copy -- which the harness's own form surface
warns produces findings about the harness rather than the product. The product
meanwhile declares the gap to the operator: the journey renders
`profile.journey.review.placeholder`, "Provenance and conflict review is not yet
available on this journey."

The ratchet is keyed by qualname rather than by count. A count accepts a swap:
one interface gaining a surface while another loses one nets to zero and reads
as no change. It is seeded at the 17 interfaces currently unrendered, which is
a recorded backlog, not an approved state.
