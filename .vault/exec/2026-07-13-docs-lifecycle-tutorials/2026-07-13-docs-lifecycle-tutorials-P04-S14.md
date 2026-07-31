---
tags:
  - '#exec'
  - '#docs-lifecycle-tutorials'
date: '2026-07-13'
modified: '2026-07-13'
body_hash: 'sha256:ac62dfd2f838957a059b8fa638ad7e0bda905016daeb3c6d89fbe7126755517b'
step_id: 'S14'
related:
  - "[[2026-07-13-docs-lifecycle-tutorials-plan]]"
---

# Convert tutorials/index.md into a short index introducing the two lifecycle tutorials and the shared persona

## Scope

- `docs/tutorials/index.md`

## Description

- Rewrite `docs/tutorials/index.md` as the short tutorials index: the "This
  page covers the ..." opening, the shared-persona statement, two grid cards
  (the income-tax year, the IVA year), the tutorials-vs-quickstart
  differentiation sentence, and the toctree for the two lifecycle pages.
  The old single Modelo 130 walkthrough's content was absorbed into
  `irpf-lifecycle.md` stage 2 in P04.S12.
- Retarget `modelo-130.md`'s tutorial link to `irpf-lifecycle.md` and
  update `explanation/index.md`'s two "Tutorial" phrasings to "lifecycle
  tutorials".

## Outcome

Phase P04 complete: the Tutorial quadrant now holds the two chartered
lifecycle lessons behind a thin index, and the old walkthrough survives as
the IRPF tutorial's first-quarter stage rather than as a quickstart
duplicate.

## Notes

`docs/index.md`'s route-grid card still points at `tutorials/index` (valid
link); its card text updates with the landing-grid regroup in P05.S15.
