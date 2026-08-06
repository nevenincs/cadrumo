---
tags:
  - '#exec'
  - '#docs-cli-sequences'
date: '2026-07-13'
modified: '2026-07-13'
body_hash: 'sha256:a375c84a137299036fa38a0a639382c439a22c28571ed98e43eb9018aa76666c'
step_id: 'S28'
related:
  - "[[2026-07-13-docs-cli-sequences-plan]]"
---

# Verify the docs build check surface and the pytest gate both red on an injected golden divergence and both pass green on clean goldens

## Scope

- `dev/docs/tests/test_sequence_goldens.py`

## Description

- Add `TestBothSurfacesRedOnDivergence` plus isolated-fixture helpers to `dev/docs/tests/test_sequence_goldens.py`: write a tmp docs tree with one `cli-sequence` page, refresh its correct golden, then inject a divergence by rewriting frame 0's exit code to a value live never emits.
- Build surface: build the fixture page in-process through a fixture Sphinx conf that registers the directive and connects the SAME `check_sequence_goldens` gate the real `docs/conf.py` wires; assert `SphinxError` naming the divergence and the `python -m dev.docs.sequences refresh` remedy.
- Pytest surface: assert the engine `check_sequences` reds on the same fixture, and the CLI `check` mode exits 1 printing the divergence and the refresh remedy to stderr.
- Green control: with the correct golden, assert `check_sequences` is clean AND a real Sphinx build succeeds and renders the sequence container.

## Outcome

Both gate surfaces are proven to red on an injected golden divergence and pass green on clean goldens, over one shared execution path. The build-surface test drives the production `check_sequence_goldens` hook (not a copy), and the pytest surface exercises both the `check_sequences` function the S27 gate uses and the CLI check mode CI runs without a full docs build. The fixture tree is fully isolated under tmp; the committed `docs/` tree is never mutated. All 9 tests in the module pass (`-m "integration and docs"`) in ~11.5s; ruff and ty clean.

## Notes

The divergence is injected as a non-masked field (frame exit code) so the real compare path reports it deterministically rather than being hidden by `GOLDEN_MASK_FIELDS`. The build surface halts at `builder-inited` (before the read phase), so a value-divergent golden reds via the executing check hook even though the directive itself only renders from the golden without executing.
