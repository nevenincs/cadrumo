---
tags:
  - '#exec'
  - '#casilla-schema'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:6ad719f7b8cdb8521e0d363686f66282de5b8f90612ce46a42aee54ec9249250'
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
- Resolve every finding message through canonical `tr(message_locale_key, **message_facts)` semantics and retain nullable `expectation_id` as its own registry-rule identity.
- Localize every authored header, summary label, and table heading in Catalan, English, Spanish, and Hungarian through `dev.locales set-batch`.
- Add real encrypted-repository and Textual-pilot tests for blocked, undefined, named-outlier, localized, responsive, focus, scroll, final-row, and theme behavior.
- Exclude `Input`, `Select`, `SelectionList`, `Checkbox`, `RadioSet`, and `Button` so S34 cannot acquire premature S35 filtering or mutation controls.

## Outcome

The TUI has one read-only review screen over the canonical application record. It owns no registry lookup, repository access, readiness mapping, blocker mapping, validation rule, write action, or filtering state. Canonical enum tokens and structured facts remain machine values; all authored presentation labels and finding messages resolve through `tr()`.

Commit `0c5fb5253d` landed the initial screen, tests, facade exports, and locale leaves. Commit `4e7de18d4b` separately landed the initial execution record and formal review audit. The formal review returned **CHANGES REQUESTED / FAIL** with four findings. Commit `bcc1c6bca0` then landed the curation audit, which resolved the critical placement finding as sanctioned transitional delivery under the accepted dependency sequence and preserved the other three findings for repair. The screen remains in place and is not relocated or duplicated; the later TUI architecture campaign owns its consumer-complete migration.

The valid findings are repaired: finding text is localized with typed facts and expectation identity is lossless; responsive pilots inspect the actual compositor frame, visibility, focus, horizontal travel, outer vertical scrolling, and access to the final canonical row; and the complete likely S35 control family is structurally absent.

Verification after repair:

- direct real-storage Textual pilots: 9 passed in 55.00 seconds during independent re-review;
- blocked M130 at `80x24`: named denominator, every casilla, a locale-fixture-resolved Spanish finding message, non-null validated expectation identity, blocker, attributed blocker, and absence of all six excluded control families;
- M720, M200 2024, M100 2024, M100 2025, and M349: every canonical registry casilla rendered;
- M100 2024 at `80x24`, `120x36`, and `160x48`: painted header/body frame, visible table, table focus, horizontal travel, outer vertical scroll, last-column cursor, and final canonical row access;
- M720 across Spanish, English, Catalan, and Hungarian at alternating narrow/wide sizes: localized frame title, visible frame/table, focus, and a compositor-observed dark-to-light theme change;
- M189 at `120x36`: undefined progress without a manufactured `0/0` denominator;
- focused Ruff format and check: passed after formatting the touched TUI facade;
- focused strict BasedPyright: zero errors, warnings, or notes;
- all literal screen keys resolve in all four supported languages; the real locale fixture proves dynamic finding-key interpolation with its supplied `casilla_id` fact;
- public-facade import and TUI package import smoke: passed;
- scoped `git diff --check`: passed.

## Notes

`dev.locales scaffold --check` remains red only on unrelated shared-worktree catalogue debt: four profile-schema keys are absent from every catalogue; the English dependencies-period help key is absent; retired verification and ledger keys remain extra; and the IVA-wallet decision-reason family exists only in Spanish. No S34-owned key is missing, extra, or inter-locale divergent.

The screen deliberately contains no faceted filtering. Filtering remains the separate W04.P10.S35 scope.

Atomicity truth: S34 was split across `0c5fb5253d`, `4e7de18d4b`, `bcc1c6bca0`, and the pending repair/closure commit. This violates the one-Step/one-atomic-commit convention. Shared history is not rewritten; the final closure commit is limited to the reviewed repairs, corrected execution narrative, final audit state, and plan checkbox.
