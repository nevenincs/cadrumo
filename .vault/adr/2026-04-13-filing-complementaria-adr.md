---
tags:
  - "#adr"
  - "#filing-complementaria"
date: 2026-04-13
modified: '2026-04-13'
title: Filing Complementaria / Amendment Engine — ADR
related:
  - "[[2026-04-13-filing-complementaria-research]]"
  - "[[2026-04-12-filing-draft-engine-adr]]"
  - "[[2026-04-12-modelo-303-390-adr]]"
  - "[[2026-04-12-submission-engine-adr]]"
issue: wgergely/aeat#93
---

# adr: filing complementaria

## context

The repository already supports original filing draft construction, dry-run-first
submission, justificante parsing, and synthetic historical filing fixtures, but
the correction path is missing. Issue #93 requires a strict amendment engine
that can compare a prior submitted filing with new casilla inputs, persist a
typed amendment record, and submit the correction through the existing
submission stack where legally and technically possible.

The legal surface is not uniform:

- `modelo 130` still exposes a complementaria path.
- `modelo 390` uses a sustitutiva path.
- `modelo 303` switched to `autoliquidación rectificativa` for monthly
  `2024-09+` and quarterly `2024Q3+`, so a generic complementaria flow is no
  longer legally correct for current periods.

## decisions

### D1: keep amendment state separate from `FilingDraft`

The feature introduces a separate strict schema rooted in
`FilingAmendment`, `CasillaDelta`, and `CasillaChange` under
`src/aeat/application/filing/_complementaria.py`. The amendment record references the
original filing and stores the delta as an audit-focused object, while the
existing `FilingDraft` remains the absolute-value representation used by the
builder and validator stack.

### D2: build amendments from absolute recomputation, then derive delta

`build_complementaria(original, updated_inputs)` will not try to mutate the
prior filing in place. Instead it will rebuild the target model with the
existing per-model builder, obtain the new absolute casilla values, and then
derive a `CasillaDelta` by comparing the recomputed result with the original
submitted filing's casilla values.

This keeps all arithmetic inside the existing builder logic and avoids
duplicating formula code in the amendment layer.

### D3: legal mode is determined by model and period

- `130` uses `AmendmentKind.COMPLEMENTARIA`.
- `390` uses `AmendmentKind.SUSTITUTIVA`.
- `303` is accepted only for periods before the IVA rectificativa cutover.
  Post-cutover periods raise a typed amendment validation error documenting that
  the legal path is `autoliquidación rectificativa`, which is outside #93.

### D4: complementaria monotonicity is a hard invariant

For `AmendmentKind.COMPLEMENTARIA`, the amendment engine rejects any delta that:

- reduces the payable liability, or
- increases a refund / compensation position.

The issue's "rectificación out of scope" note makes this a mandatory validation
gate rather than a warning.

### D5: submission persists through the existing file-backed substrate

The amendment submission path extends the existing file-backed persistence model
instead of introducing new SQLAlchemy repositories or migrations. The live
repository state already persists `SubmittedFiling` JSON records, and the
amendment flow will persist its own strict JSON records alongside them using
the existing settings-backed directories.

This keeps #93 aligned with what is actually on `main`.

### D6: transport gaps are first-class, typed, and non-blocking to the engine

The amendment engine ships even if the browser submitter cannot yet express the
AEAT complementaria controls safely. In that case the submission method returns
or raises a typed gap/error state after persisting the amendment attempt,
instead of pretending the form path exists.

This matches the issue's explicit scope note that the per-model AEAT form-field
mapping is not the primary deliverable.

### D7: audit-trail integration remains Protocol-based

Any provenance or audit callback uses a narrow local Protocol so #93 can record
amendment build/submission events without importing Track B audit internals from
issue #82.

## consequences

- The amendment layer is additive and does not destabilize the original draft
  engine.
- Liability validation is consistent because it compares fully recomputed
  results rather than raw user inputs.
- `303` support is explicitly bounded by period date, avoiding a legally
  incorrect "always complementaria" implementation.
- `390` can be represented cleanly as a delta-backed audit object while still
  surfacing the correct public amendment kind `sustitutiva`.
- Persistence remains simple, local, and testable, but a later storage issue may
  still want to normalize amendment records into the database.

## alternatives considered

- Overloading `FilingDraftStatus.AMENDED` onto `FilingDraft` itself. Rejected
  because it collapses "absolute draft" and "delta against prior filing" into a
  single type and makes submission/audit state ambiguous.
- Adding a new SQLAlchemy filing-history repository and migration in #93.
  Rejected because the current production filing history on `main` is file-based,
  and forcing a DB rewrite here would be scope creep.
- Treating all `303` amendments as complementarias. Rejected because BOE
  `2024-08-05` made `autoliquidación rectificativa` the applicable path for
  current periods.
- Blocking shipment until the browser submitter exposes a complete complementaria
  branch. Rejected because the issue explicitly allows stubbing that gap as long
  as the engine, delta computation, and CLI path ship.

## status

accepted
