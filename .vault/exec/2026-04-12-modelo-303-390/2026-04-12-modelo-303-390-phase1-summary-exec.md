---
name: modelo-303-390-phase1-summary
description: Phase summary for Modelo 303 + Modelo 390 IVA builder delivery (#62)
type: exec
tags:
  - "#exec"
  - "#modelo-303-390"
date: 2026-04-12
modified: '2026-04-12'
related:
  - "[[2026-04-12-modelo-303-390-plan]]"
  - "[[2026-04-12-modelo-303-390-adr]]"
  - "[[2026-04-12-modelo-303-390-research]]"
  - "[[2026-04-12-modelo-303-390-phase1-task1-exec]]"
  - "[[2026-04-12-modelo-303-390-phase1-review-exec]]"
---

# modelo-303-390 phase1 summary

Issue: wgergely/aeat#62
Branch: `feature/62-modelo-303-390`
Pipeline: research → ADR → plan → task execution → code review
→ commit → PR.

## Delivered

- Two new concrete `FilingBuilder` subclasses —
  `Modelo303Builder` (quarterly IVA) and `Modelo390Builder`
  (annual IVA summary) — registered with `aeat.application.filing.build_draft`.
- Two hand-curated casilla schemas sourced from the Manual
  práctico IVA 2025 (AEAT) chapters on modelo 303 / 390,
  cited in the ADR.
- Validator extension that reconciles the annual 390 draft
  against its four quarterly 303 drafts and emits ERROR
  findings on mismatch or 303 self-consistency failure, with
  trilingual (`es`/`en`/`hu`) messages.
- 21 colocated pytest `@pytest.mark.unit` tests covering
  builders, validators, cross-validation, JSON round-trip,
  stable hash.

## Artefacts

- Research: `[[2026-04-12-modelo-303-390-research]]`
- ADR: `[[2026-04-12-modelo-303-390-adr]]`
- Plan: `[[2026-04-12-modelo-303-390-plan]]`
- Exec step: `[[2026-04-12-modelo-303-390-phase1-task1-exec]]`
- Code review: `[[2026-04-12-modelo-303-390-phase1-review-exec]]`

## Gates (Windows, local)

| Gate | Result |
| ---- | ------ |
| `just lint` | green |
| `just typecheck` | green |
| `just test` | 586 passed / 1 skipped / 18 deselected |
| `just hooks` | green |

## Follow-ups (not in scope for this PR)

- Migrate the hand-curated 303/390 schemas to the casilla DB
  once #23 lands on `main`.
- Replace the reserved `_quarterly_303` inputs key with a
  typed facade once the workflow engine #59 is merged.
- Ship builders for 036/037, 111/115/180/190, 100, 349, 720
  per the issue's "after this lands" note — one per modelo.
