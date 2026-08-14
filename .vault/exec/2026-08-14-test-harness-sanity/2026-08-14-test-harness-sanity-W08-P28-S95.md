---
tags:
  - '#exec'
  - '#test-harness-sanity'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:3fa2f4c200f47b4742d04a65283375597d89e445a789ae4442bc1b5615cbc347'
step_id: 'S95'
related:
  - "[[2026-08-14-test-harness-sanity-plan]]"
---

# Run full first-party collection and retain complete status and errors

## Scope

- `pyproject.toml`

## Description

- Collect the complete first-party corpus in one pass with error tolerance enabled.
- Retain the full status rather than a pass or fail verdict.
- Identify every collection error rather than counting them.

## Outcome

Thirty-three thousand and sixty-eight tests were discovered across the three first-party roots, of which twenty-seven thousand eight hundred and thirty-one collected, five thousand two hundred and thirty-seven were deselected by the active marker expression, and twenty-one modules failed to import. The pass took seven minutes twenty-four seconds outer-serially.

The twenty-one failures are named individually and all trace to concurrent campaigns: a registry authority-grade transition that leaves a modelo revision pending review and refuses at snapshot build, and a registry schema mid-refactor whose symbol is not yet exported. They span agent evaluation, calculations, modelo, overview, contribuyente and llm test packages, which is consistent with a shared dependency failing rather than with twenty-one independent defects.

## Notes

The count is meaningful only because the corpus boundary was corrected first. The same collection run against the previous boundary would have walked a gitignored copy of the entire repository and reported roughly two thousand modules, a number large enough to be read either as catastrophe or as noise and useful as neither.

Retaining the deselected count alongside the collected one matters for the same reason the collector returns a tally at all: an errors-only reading cannot distinguish a clean corpus from a collection that never happened, and a run that collected nothing would otherwise present exactly like a run that collected everything cleanly.
