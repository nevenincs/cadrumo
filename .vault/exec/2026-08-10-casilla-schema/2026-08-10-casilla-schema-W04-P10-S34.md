---
tags:
  - '#exec'
  - '#casilla-schema'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:6f94935871e2d4a010cfc08ce3669f66e3292a90b38eb3c4fec918f20b6b3dc0'
step_id: 'S34'
related:
  - "[[2026-08-10-casilla-schema-plan]]"
---

# build the TUI review screen consuming the review record through the application modelo facade

## Scope

- `src/cadrumo/adapters/inbound/tui/`

## Description

- Add a read-only `ModeloWorkReviewScreen` and standalone `ModeloWorkReviewApp` under the existing TUI adapter.
- Consume `ModeloWorkReview` and `ModeloWorkProgressDenominator` only through the public `application.modelo` facade.
- Render target identity, lifecycle, verification outcome, and named-manifest progress without revalidating or reclassifying application state.
- Render every casilla's schema, official representation, declared origin, concrete origin, realised value, grounding, and attributed blockers directly from the canonical record.
- Render record-level findings and blockers as separate tables, omitting healthy empty panels.
- Localize every authored header, summary label, and table heading in Catalan, English, Spanish, and Hungarian through `dev.locales set-batch`.
- Add real encrypted-repository and Textual-pilot tests for blocked, undefined, and named-outlier review records.

## Outcome

The TUI now has one read-only review screen over the canonical application record. It owns no registry lookup, repository access, readiness mapping, blocker mapping, validation rule, write action, or filtering state. Canonical enum tokens and structured facts remain machine values; all authored presentation labels resolve through `tr()`.

Verification:

- direct real-storage Textual pilots: 7 passed in 33.34 seconds;
- blocked M130 at `80x24`: the named denominator, every casilla, finding, blocker, and attributed blocker rendered with no input or filter control;
- M720, M200 2024, M100 2024, M100 2025, and M349 at `160x48`: every canonical registry casilla rendered;
- M189 at `120x36`: undefined progress rendered without a manufactured `0/0` denominator;
- focused Ruff check: passed;
- focused strict BasedPyright: zero errors, warnings, or notes;
- all 22 screen translation keys resolved in each of the four supported languages;
- public-facade import and TUI package import smoke: passed;
- scoped `git diff --check`: passed.

## Notes

`dev.locales scaffold --check` remains red only on unrelated shared-worktree catalogue debt: four profile-schema keys are absent from every catalogue; the English dependencies-period help key is absent; retired verification and ledger keys remain extra; and the IVA-wallet decision-reason family exists only in Spanish. No `flows.modelo_review.*` key is missing, extra, or inter-locale divergent.

The screen deliberately contains no faceted filtering. Filtering remains the separate W04.P10.S35 scope.
