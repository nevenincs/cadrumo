---
tags:
  - '#exec'
  - '#llm-evidence-classification'
date: '2026-06-13'
modified: '2026-07-17'
body_hash: 'sha256:1bb4413617196f961d81670e79e3425cefc38a952fd61c748781a6c5ba7a99f0'
step_id: 'S07'
related:
  - "[[2026-06-13-llm-evidence-classification-plan]]"
---

# Adversarially test evidence parsing (text-layer, in-memory rasterise, vision dispatch) against the corpus

## Scope

- `src/aeat/application/ledger/tests/test_evidence_corpus_parsing.py`

## Description

- Adversarially test evidence parsing (text-layer extraction, scan-only -> rasterise fallback, image load, malformed/empty raise) against the corpus.

## Outcome

- 8 corpus-parsing tests pass; parsers raise (never crash) on hostile input. Committed `1572036a8`.

## Notes
