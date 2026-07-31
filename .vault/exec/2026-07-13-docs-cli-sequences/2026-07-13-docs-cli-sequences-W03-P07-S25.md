---
tags:
  - '#exec'
  - '#docs-cli-sequences'
date: '2026-07-13'
modified: '2026-07-13'
body_hash: 'sha256:27d0ae8c613b809d5e6ccffb4ef5f0c1837183b03d1fb66e8f349e5bcc1f46f8'
step_id: 'S25'
related:
  - "[[2026-07-13-docs-cli-sequences-plan]]"
---

# Write directive and tokeniser tests asserting the payload shape, token classification, and no-JS static frame HTML

## Scope

- `dev/docs/tests/test_sequence_directive.py`

## Description

- Add a two-tier gate for the directive and tokeniser with no mocks or skips.
- Pure-function tier: assert the tokeniser classifies verbs, options, option values, and `{name}` placeholders against the live tree and carries the space-joined command-path key; assert the payload shape and that the static HTML renders from the one payload with the inline JSON parsing equal to the computed payload; assert a stale golden (frame-count mismatch) is refused.
- Real-build tier: build a minimal in-process MyST Sphinx site with the directive registered and a committed golden fixture, and assert the rendered `index.html` carries the server-side static frames (the no-JS transcript), the tokenised spans, and one well-formed inline payload matching the four frames.
- Assert a directive whose golden is absent fails the build with an instructive message naming the exact refresh invocation and renders no sequence container.
- Pin an isolated Cadrumo storage root and English output for the CLI-tree walk via a fixture, and redirect the directive at the fixture golden tree through the Sphinx config value.

## Outcome

- Six tests pass, including the two real Sphinx builds; the directive and tokeniser are proven end to end through a genuine build, not a stubbed render.
- Ruff and ty are clean.

## Notes

- The golden fixtures are constructed through the strict `SequenceGolden` model (schema-valid by construction) in a temp tree, not hand-edited committed goldens, so the CLI-owned golden discipline is preserved.
