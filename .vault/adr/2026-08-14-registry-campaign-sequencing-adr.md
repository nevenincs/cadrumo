---
tags:
  - '#adr'
  - '#registry-campaign-sequencing'
date: '2026-08-14'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:cdd56cfd070161ee652d3df7e7ba2aeb427ab6e1922fc55a0a95199b8aa39b49'
related:
  - "[[2026-08-14-registry-campaign-sequencing-audit]]"
  - "[[2026-08-14-registry-campaign-sequencing-operator-attestation-ledger-audit]]"
---

# `registry-campaign-sequencing` adr: `export layout withdrawal is deleted; registry build refuses any revision with no export layout` | (**status:** `accepted`)

## Problem Statement

The registry currently lets a revision declare zero export layout while
still passing every build and validation gate, provided it carries a
`support_removal_decisions` entry recording the absence as a deliberate
withdrawal. Nine modelo revisions do this today: 111, 115, 123, 130, 200,
202, 232, 303, 390. Only six of the registry's seventy-three modelos declare
a real export layout at all (100, 131, 145, 180, 349, 720); the remaining
fifty-eight declare neither a layout nor a withdrawal.
`2026-08-14-registry-campaign-sequencing-audit` and its companion ledger
audit show every individual withdrawal is defensible on its own terms — each
genuinely avoids shipping a partial, silently under-declaring fixed-width
layout. What was never asked is the question that matters once the
withdrawals are summed: does the application, taken as a whole, still do the
thing it exists to do. It does not. Modelo 303 (IVA) and Modelo 200
(Impuesto sobre Sociedades) are both withdrawn, so the application cannot
currently produce a filing artifact for either of the two taxes its own
scope names, and the registry build is green about it.

This decision closes that gap: it deletes the mechanism that makes a
permanent absence acceptable to the build gates, and replaces it with an
unconditional build-time refusal, so the tree cannot stay green while a
revision cannot file.

## Considerations

- Every count and date below was independently re-verified against the tree
  at authoring time (`git log`, direct file reads) rather than copied from
  either audit. 6 of 73 modelo directories under
  `src/cadrumo/_data/registry/aeat/modelos/` carry a real
  `export_layouts`/`export` directory (100, 131, 145, 180, 349, 720); 9
  carry a `support_removal_decisions` fragment declaring
  `decision = "remove_from_filing_grade"` (111, 115, 123, 130, 200, 202,
  232, 303, 390); the remaining 58 declare neither.
- All nine withdrawal fragments trace to first-add commits dated the same
  day, 2026-08-11: `9d5d72b997` (111), `85efb1b757` (115), `bde8985d43`
  (123), `de4c8360e3` (130), `b57cebf353` (200), `8dacf12906` (202),
  `4416c7b223` (232), `df49c5206a` (303), `713f89b2f4` (390), each carrying
  the generic message shape `Registry work: <modelo>`. This is not nine
  campaigns narrowing their own scope independently over months and never
  summing the result — it is one coordinated sweep that made nine absences
  explicit on a single day, and nobody then asked what nine simultaneous
  withdrawals meant for the application's purpose.
- Modelo 303 and Modelo 390 both had real export layouts in git history
  before that sweep, confirmed by direct history search rather than
  inferred from their current absence. Modelo 303's
  `export/0001-export-layout.toml` and siblings existed under revision
  `2009-y-siguientes` from the earliest recorded history and were deleted
  in the same commit (`df49c5206a`) that added the withdrawal fragment.
  Modelo 390's `export_layouts/` existed under `2010-y-siguientes` from the
  earliest recorded history and was withdrawn the same day (`713f89b2f4`),
  three days before today's Modelo 390 annual-epoch split (`f9f3f77704`).
  The split did not remove a live export layout; it retired the
  already-withdrawn `2010-y-siguientes` revision and copied the SAME
  standing withdrawal into each of the four new revision directories
  (2022, 2023, 2024, 2025) rather than making a fresh decision.
- `2026-04-22-aeat-fichero-boe-export-adr`, still `accepted`, already rules
  that Modelo 130 and Modelo 303 fichero-BOE export support is REQUIRED.
  The 2026-08-11 sweep withdrew Modelo 303's export layout without amending
  or superseding that record. This decision does not conflict with that
  ADR; it enforces, at build time, the requirement that ADR already states.
- The historical layouts recoverable from git are not directly restorable
  by revert. The recovered Modelo 390 layout declares
  `source_refs = ["aeat-dr-390-2025"]` on every field while its pre-split
  revision claimed 2010 onward, and its own record boundaries do not hold
  across every epoch that revision claimed (`page_02` closes at four
  different offsets and box 47 sits at three different offsets across the
  epochs measured). A straight revert of the withdrawal commits would
  reintroduce exactly the defect `aeat-design-relayout-boundary` exists to
  close: one measured layout applied outside the epoch it was measured
  against. Restoration is per-epoch re-derivation against each epoch's own
  bundled design, never a wholesale revert.
- Every `support_removal_decisions` consumer in `src/cadrumo` is
  descriptive, not gating: id-uniqueness (`_validate_revision_identity.py`),
  id-map construction (`_validate_revision_context.py`), reference
  integrity (`_validate_references.py`, `_validate_reference_checker.py`),
  closure (`_validate_revision_closure.py`), and two count-only reporting
  sites (`application/registry/_conformance.py`, `_registry_payloads.py`).
  None of them gates, suppresses, or short-circuits an export path. The
  actual guard against emitting an incomplete filing artifact is the export
  completeness gate inside `export_draft`, which raises `FilingExportError`
  on any required casilla lacking a value; this decision does not touch it.
- `2026-08-14-registry-campaign-sequencing-operator-attestation-ledger-audit`
  records that five registry campaigns are in flight and depend on the
  registry loading. This decision makes the registry fail to load for every
  one of them until every revision in the tree can emit, and that cost is
  intended, not incidental.

## Considered options

- **Keep the withdrawal mechanism and track "cannot file" as a separate
  worklist (rejected).** This is the status quo the sweep produced. It
  leaves the tree green while nine modelos, including the two the
  application's own name references (IVA, Sociedades), cannot file. A
  worklist nobody is forced to consult is not different in kind from silent
  under-declaration; it is the same failure at one remove.
- **Add an allowlist or a staged rollout while generator campaigns land
  their layouts (rejected).** Considered as a softer transition so the tree
  could stay green during the migration. Rejected because an allowlist is
  exactly the shape this project's other rules already treat as a mute
  button: it would let a tenth withdrawal slip in quietly the same way the
  first nine did, defeating the point of the decision. No allowlist, no
  exemption, no per-modelo carve-out.
- **Delete the mechanism outright and refuse any revision declaring no
  export layout, unconditionally (chosen).** The registry fails to load
  until every revision emits. This is the only option with no sanctioned
  shape for "revision with no layout, tree still green," so it cannot
  silently regress to the status quo.

## Constraints

- The registry will not load at all, for every consumer, until each of the
  nine currently-withdrawn revisions — and any revision among the 58
  undeclared modelos this check is later asked to cover — has a real
  export layout. This blocks all five in-flight registry campaigns named
  in `registry-campaign-sequencing-audit` from producing verifiable
  evidence against a warm registry load until their owned trees emit.
- Recovered pre-withdrawal layouts (Modelo 303, Modelo 390) are historical
  artefacts only, not drop-in replacements: they must be re-derived per
  epoch against that epoch's own bundled AEAT design, following the same
  discipline `aeat-design-relayout-boundary` already established for the
  sub-year epoch split, never reverted wholesale.
- This decision does not itself build any filing capability; it only
  removes the mechanism that let the tree stay green without one. Every
  other accepted decision governing HOW an export layout is authored
  (`aeat-fichero-boe-export-adr`, `modelo-registry-fragment-architecture-adr`,
  the export-fragment-generator campaign) is unaffected and remains the
  authority once this decision requires a layout to exist.

## Implementation

Delete the `support_removal_decisions` section outright: the TOML fragments
under every modelo's `support_removal_decisions/` directories, its compiled
schema field, and its seven descriptive-only consumers named in
Considerations (retiring or repointing each one's now-dead
`support_removal_decision_count` reporting as appropriate; none requires a
redesign, since none gated behaviour).

Add one unconditional build-time check to registry revision validation: a
revision that declares zero export layout fragments raises a hard
`RegistryLoadError` (or the equivalent revision-closure validation
failure) naming the modelo and revision id, with no allowlist and no
`support_removal_decisions`-shaped escape hatch of any kind. This sits
alongside the existing revision-closure validators
(`_validate_revision_closure.py`) rather than replacing them.

The nine currently-withdrawn revisions — and the fifty-eight modelos that
declare neither an export layout nor a withdrawal, for any that are later
brought under a revision this check reaches — become the accumulated
capability worklist: the registry's own refusal message, enumerating every
non-emitting revision, is that list. No separate tracking document
duplicates it.

## Rationale

The knockout is that every softer option reproduces the exact failure mode
this decision exists to close. An allowlist, a staged rollout, or a
track-it-separately posture all keep the tree green while a revision cannot
file, which is indistinguishable, at the level that matters to a taxpayer,
from the silent under-declaration the withdrawal mechanism was invented to
prevent. The withdrawal mechanism did not fail because any single decision
inside it was wrong — `2026-08-14-registry-campaign-sequencing-audit`
confirms each was individually defensible — it failed because "green"
stopped meaning "can file" for nine modelos at once, on one day, and
nothing forced that question to be asked afterward. Only an unconditional
build-time refusal makes that question unavoidable on every subsequent
load, for every campaign, forever, which is the property no allowlisted or
staged variant has.

## Consequences

The registry fails to load, hard, starting now, and stays failing until
every revision emits a real export layout. This is intended, not a
regression to walk back. Every one of the five in-flight registry
campaigns loses the ability to produce verifiable evidence against a warm
load until their owned trees close this gap;
`registry-campaign-sequencing-audit`'s Tier 1 (export-fragment generator)
and Tier 2 (relayout) sequencing become the critical path to green rather
than optional cleanup.

What this decision does NOT lower: the export completeness gate inside
`export_draft` still refuses to emit a filing artifact missing a required
casilla value, unchanged. Filing GRADE — whether a produced artifact is fit
to actually submit — remains an operator attestation, unchanged. This
decision only makes the ABSENCE of a layout loud instead of silent; it does
not relax any bar on what may be emitted once a layout exists.

The reversal condition: this refusal stops firing, modelo by modelo and
revision by revision, exactly when that revision declares an export layout
grounded in its OWN epoch's bundled AEAT design — never by reintroducing
the deleted `support_removal_decisions` mechanism in any form, and never by
reverting the withdrawal commits wholesale, since the recovered historical
layouts do not hold across every epoch the pre-split revisions claimed. The
registry as a whole is green again only when every revision in the tree —
today's nine withdrawn ones, plus any of the fifty-eight undeclared modelos
this check is later asked to cover — has cleared that bar.
