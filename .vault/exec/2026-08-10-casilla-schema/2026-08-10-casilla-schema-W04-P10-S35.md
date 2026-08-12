---
tags:
  - '#exec'
  - '#casilla-schema'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:2b9d501b0d5ca5fcd21cba98dc592413814aa517dd35757e4373b65d6a8e4f1a'
step_id: 'S35'
related:
  - "[[2026-08-10-casilla-schema-plan]]"
---
# add faceted filtering over the record's closed axes

## Scope

- `src/cadrumo/adapters/inbound/tui/`

## Description

- Add one collapsed, localized filter disclosure above the canonical review tables so the existing narrow-screen frame remains useful before the operator opens the controls.
- Derive every enum option directly from the canonical enum members and represent nullable binding, formula, relation, origin-anomaly, and per-casilla-blocker facts with one closed present/absent choice.
- Filter casillas by declared `InputKind`, concrete `BindingSourceKind`, binding/formula/relation presence, realised `ModeloValueKind`, `ModeloWorkOriginAnomaly` and its presence, `OfficialBoxStatus`, and per-casilla `OperatorActionAxis` and its presence.
- Filter findings by canonical kind and severity, and record blocker rows by `OperatorActionAxis`.
- Keep filtering grain-local, conjunctive within each grain, stable in canonical row order, and entirely presentation-only over the frozen `ModeloWorkReview`.
- Preserve the unfiltered view, add localized zero-match states, and restore every selector and exact row identity through one reset action.
- Promote only the canonical review row, origin-anomaly, and blocker types through the public `application.modelo` facade so the adapter never reaches a private application module.
- Author every new Catalan, English, Spanish, and Hungarian label through `dev.locales`.

## Outcome

The review screen now exposes fourteen selectors and one reset action. The option vocabulary contains no adapter-authored domain classification: enum axes iterate their canonical members and presence axes carry only present/absent. Record lifecycle, progress, and verification are deliberately not facets because this screen presents exactly one record; selecting those values would hide the sole record rather than filter a repeatable grain. The record summary remains visible and unchanged.

Real encrypted-repository and Textual-pilot evidence:

- M100 2024: exact canonical row projections and exact reset for declared input, profile binding source, binding presence and absence, formula presence and absence, relation presence and absence, broken-chain anomaly, anomaly absence, and addressed official boxes; passed in 48.19 seconds.
- M130 2026 1T: a genuinely persisted mixed-origin calculation plus blocking verification proves literal realised values, operator-override anomaly, anomaly presence, per-casilla blocker axis and presence, finding kind and severity, record blocker axis, truthful zero-match states for all three tables, exact reset, and an unchanged frozen review; passed in 28.59 seconds.
- Named outlier preservation: M720, M200 2024, M100 2024, M100 2025, and M349 each still render every canonical casilla; five pilots passed in 35.63 seconds.
- Responsive preservation: M100 2024 remains focusable, horizontally traversable, vertically scrollable, and final-row reachable at 80x24, 120x36, and 160x48; passed in 31.19 seconds.
- The existing blocked real-storage pilot passed in 25.79 seconds with all canonical grains and no mutation controls.
- Exact option-totality test passed: every enum option tuple equals direct iteration of its canonical enum, and the presence tuple is exactly present/absent.
- Focused Ruff format/check passed; focused strict BasedPyright completed with zero errors, warnings, or notes.

## Notes

`dev.locales scaffold --check` remains red on unrelated shared-worktree catalogue debt: the four profile-schema leaves are absent from every catalogue, the English dependencies-period help leaf is absent, retired verification and ledger leaves remain extra, and the IVA-wallet decision-reason family exists only in Spanish. The command reports no missing, extra, or inter-locale divergence for any `flows.modelo_review.filter.*` leaf authored by S35.

The first focused pilot exposed that assigning Textual's internal blank sentinel is not a supported reset API. Production and tests now call the public `Select.clear()` method; the rerun passed. No production record, repository, registry, readiness mapping, or write path is mutated by a filter event.
