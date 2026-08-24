---
tags:
  - '#audit'
  - '#tax-authority-reconciliation'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:6c3fdce0620f18b0c2c0d4c9f65b3e7d2fb82860a377ce3ce02f7348a1e5c7b6'
related: []
---

# `tax-authority-reconciliation` audit: filing-boundary and source-receipt reconciliation

## Scope

Audit the tax-authority reconciliation that limits design-span enforcement to
filing-grade revisions, consumes explicit layout-authority dependency receipts,
keeps detector anti-vacuity independent of support policy, encodes Modelo 720's
filing-year axis, and removes Modelo 200's unsafe filing claim.

## Findings

### modelo-200-filing-retirement | high | the grade downgrade hides a genuine supported relayout instead of completing the accepted split

`src/cadrumo/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/revision.toml:20`
changes Modelo 200 from `filing` to `calculation`.  That does make the public
filing snapshot boundary refuse, because `_check_snapshot_authority_grade`
rejects a calculation-grade revision when filing grade is requested.  It also
removes the only still-spanning revision from both filing-only span gates,
however, so those gates become green without the 2024/2025 record-set change
being repaired.  This is not the unsupported-model case described by the
operator: the accepted relayout decision and its implementing plan identify
Modelo 200 as a genuinely filing-supported modelo and require two layout-correct
epochs.  Existing production-facing tests also still request filing snapshots
for Modelo 200, for example
`src/cadrumo/application/filing/tests/test_export_implicit_decimal_slots.py:58`;
no exact Modelo-200 runtime-refusal test accompanies the retirement.  The
current dirty tree prevented exercising that refusal through the full authority
because an unrelated Modelo 190 deadline-window validation fails first, but the
authority-grade unit tests prove the same public boundary rejects calculation
grade for a filing request.

### span-progress-anti-vacuity | high | deleting the pinned progress gate makes policy narrowing indistinguishable from fixing the final relayout

`src/cadrumo/domain/calculations/registry/tests/test_revision_span_split_progress.py`
is deleted.  Its last pinned subject was Modelo 200, and it required the
filing-cohort detector to remain non-empty until that subject was actually
partitioned.  The replacement control in
`src/cadrumo/domain/calculations/registry/tests/test_mid_year_design_claim.py:59`
correctly proves the raw detector can still see Modelo 200 across all declared
revisions, but it does not prove that a supported filing claim still reaches the
filing gate.  With the simultaneous grade downgrade, the raw detector canary
passes while the filing gate silently stops judging the known defect.  The
replacement therefore preserves detector mechanics but loses the deleted
test's policy anti-vacuity and its protection against an unknown additional
filing span hiding inside an already-red cohort.

### layout-receipt-subject-coupling | medium | the new generic receipt proof is broader than the layout it purports to authorize

`_layout_authority_receipts` in
`src/cadrumo/domain/calculations/registry/tests/test_revision_span_matches_published_designs.py:955`
accepts every revision-level source carrying `evidence_tier =
"layout_authority"`.  `_source_epoch_proves_revision_span` then treats any such
source whose temporal selector covers the revision as proof, without requiring
that the selected export layout consumes that source or that the source belongs
to the same modelo.  The committed Modelo 100 data is sound in fact: each annual
revision cites bounded, exact-year AEAT dictionaries and XSDs, and its
`xml_dictionary` layout names the matching annual dictionary.  The helper does
not encode that coupling, so a future unrelated dictionary or XSD added to a
revision's broad `source_refs` can make the span pass while the actual export
layout remains unsupported.  Explicit dependency receipts should be followed
through the layout dependency, not accepted only by tier and date.

### modelo-720-filing-year-axis | low | the 2012 selector is grounded and resolves the calendar-year underhang honestly

The new `period_selector = { year_from = 2012, periods = ["0A"] }` on
`aeat-dr-720` is supported by the bundled Orden HAP/72/2013 corpus: its final
provision states that the order applies for the first time to the declaration
corresponding to ejercicio 2012, filed in 2013.  Giving the layout receipt an
explicit filing-year selector is preferable to interpreting its
`applies_from = 2013-02-01` calendar date as ejercicio coverage.  The revised
`_receipt_covers_year` correctly gives the typed period selector precedence.

## Recommendations

- Complete the accepted Modelo 200 2024/2025 split and retain filing grade only
  on the resulting layout-correct epochs.  If filing support is instead being
  withdrawn as a new product decision, record that decision explicitly, add an
  exact public-facade refusal test for both affected filing years, and reconcile
  every production-facing test and dependent Modelo 202 relation that still
  relies on Modelo 200 filing support; do not use a grade flip as the split's
  implementation.
- Restore a policy-level anti-vacuity assertion that names every known supported
  spanning revision until it is genuinely split.  Keep the new all-declared raw
  detector canary as a separate mechanical control, and derive unexpected
  filing spans so a new defect cannot hide behind an existing red row.
- For fixed-width layouts, derive accepted record-design receipts from the
  selected layout's `source_refs`; for XML dictionary layouts, require the
  `dictionary_source_ref` and XSD used by that layout.  Intersect those with the
  revision's declared dependency receipts and assert modelo/year identity before
  granting the source-epoch proof.  Retain the current M100 annual sources as
  positive fixtures and add a mutation using an unrelated layout-authority
  source to prove the gate bites.
- Keep the Modelo 720 filing-year selector and add a focused assertion tying its
  first included ejercicio to the bundled Orden's first-application clause, so
  later metadata edits cannot detach the receipt from that legal grounding.

## Resolution

The M200 filing claim remains withdrawn because no layout-correct 2024 export
exists and retaining filing grade would authorize known-wrong bytes. The gap is
now pinned separately from the filing cohort: the raw detector must continue to
name exactly M200 as an unsupported span, and an exact public snapshot test
proves a filing-grade request refuses with the prescribed attestation action.
This resolves the anti-vacuity and missing-refusal portions of the two high
findings while leaving the actual two-epoch authoring work visible rather than
misrepresenting it as complete.

Layout receipts are now modelo-coupled by their bundled corpus subtree in
addition to tier, citation, and temporal selector, preventing an unrelated
modelo's dictionary or design from proving a revision. M720's explicit 2012
filing-year axis is retained as reviewed.
