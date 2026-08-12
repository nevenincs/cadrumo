---
tags:
  - '#exec'
  - '#casilla-schema'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:88484d1418fac48ab936c70004192842678ee170042b82f308fb694ca5b06d49'
step_id: 'S35'
related:
  - "[[2026-08-10-casilla-schema-plan]]"
---
# add faceted filtering over the record's closed axes

## Scope

- `src/cadrumo/adapters/inbound/tui/`
- `src/cadrumo/locales/`
- `dev/locales/_fstring_registry.py`

## Description

- Add one collapsed, localized filter disclosure above the canonical review tables so the existing narrow-screen frame remains useful before the operator opens the controls.
- Derive every enum option directly from canonical enum members and every relation-channel option from the registry-owned `RelationConsumptionChannel` literal.
- Filter casillas by declared `InputKind`, concrete `BindingSourceKind`, binding presence and resolved state, formula and relation presence, relation consumption channel, realised `ModeloValueKind`, `ModeloWorkOriginAnomaly` and its presence, `OfficialBoxStatus`, and per-casilla `OperatorActionAxis` and its presence.
- Filter findings independently by canonical kind and severity, and record blocker rows by `OperatorActionAxis`.
- Keep filtering grain-local, conjunctive within each grain, stable in canonical row order, and entirely presentation-only over the frozen `ModeloWorkReview`.
- Preserve the unfiltered view, add localized zero-match states, and restore every selector and exact row identity through one reset action.
- Localize both facet labels and every visible option label through `dev.locales`, while retaining canonical enum, literal, and boolean values as selector payloads.

## Outcome

The review screen now exposes sixteen selectors and one reset action. Its option vocabulary contains no adapter-authored domain classification: enum axes iterate their canonical members, relation channels come from `get_args(RelationConsumptionChannel)`, and presence and resolved axes use only their closed values. Record lifecycle, progress, and verification are deliberately not facets because this screen presents exactly one record; selecting those values would hide the sole record rather than filter a repeatable grain. The record summary remains visible and unchanged.

Formal review at `82a5a5248d` recorded FAIL. The repair promotes the relation-channel literal and public review binding/relation types through `dc0e89c413` (building on facade promotion `ffe78a57a9`), adds binding-resolution and relation-channel facets, registers the bounded option namespace in the locale f-string registry, localizes every visible option in Catalan, English, Spanish, and Hungarian, and strengthens real encrypted/Textual proof. The second review resolved those findings but retained FAIL for one redundant conjunction proof; the follow-up replaces it with a strict-against-both real-record intersection. Final re-review remains pending.

Verification after repair:

- The complete S35 TUI test module passed: 12 tests in 106.55 seconds.
- The follow-up exact M100 pilot passed in 56.56 seconds. It derives the `InputKind.MANUAL` and `OfficialBoxStatus.ADDRESSED` row sets from the canonical review, proves their intersection is non-empty and a proper subset of each, and asserts exact ordered table identities for each individual filter and their conjunction. Clearing the input-kind filter restores the strictly larger addressed set, so removing either matcher makes the proof fail.
- M100 also proves binding resolved false, primary relation channel, exact reset rows, every selector blank after reset, and an unchanged canonical record.
- M130 persists two legitimate findings through the encrypted `VerificationReport` repository and proves finding kind independently from severity, binding resolved true, casilla and record blocker facets, truthful zero-match panels, exact reset rows, and every selector blank after reset.
- M720 runs at 80x24 in every supported locale with the disclosure opened, verifies a mounted localized long option rather than its canonical token, traverses the focus chain to the visible reset action, collapses back to the table, and toggles appearance.
- Exact option-totality proof passed for canonical enums, the relation-channel literal, presence, and boolean resolution values.
- Focused Ruff format/check passed. Focused strict BasedPyright completed with zero errors, warnings, or notes. The scoped S35 diff check passed.

## Notes

`dev.locales scaffold --check` remains red only on unrelated shared-worktree catalogue debt: four profile-schema leaves are absent from every catalogue, the English dependencies-period help leaf is absent, retired verification and ledger leaves remain extra, and the IVA-wallet decision-reason family exists only in Spanish. It reports no missing, extra, or inter-locale divergence for `flows.modelo_review.filter.*`.

The dynamic-prefix coverage gate no longer reports `flows.modelo_review.filter.option`; it remains red on the pre-existing unrelated `errors.context_labels` and `errors.prefix` namespaces. The constant-key naming gate passes. The shared audit now contains the second-review FAIL and has not been edited by this execution repair; a final fresh review is still required to change that verdict. No production record, repository, registry data, readiness mapping, or write path is mutated by a filter event.
