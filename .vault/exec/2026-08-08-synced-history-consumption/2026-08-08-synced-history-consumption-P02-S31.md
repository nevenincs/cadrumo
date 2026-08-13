---
tags:
  - '#exec'
  - '#synced-history-consumption'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:f0330079eb8ab5729537887e6cc1f01f80f3e07616e5615be225c01753f0289c'
step_id: 'S31'
related:
  - "[[2026-08-08-synced-history-consumption-plan]]"
---

# Decide what an operator-facing surface should DO with a factual_evidence carry, which S17 deliberately left unscoped. S17 made the registry's declared treatment survive the requirement-to-value join, so a consumer can now tell a figure that settles the return from a fact to reconcile against, and nothing yet acts on the distinction. That was the row's scope and this is the remainder. The constraint is the ruling's and it is binding: SURFACE it, never WITHHOLD it. A taxpayer is entitled to a suffered retencion, and the over-declaration direction is the one nothing in this codebase watches, so the obvious implementation is the harmful one. Suppressing the value, blanking it, or refusing the draft on it would remove a figure the taxpayer is owed and would do so silently, which is worse than the indistinguishability S17 fixed. Flagging it is only safe if the flag cannot become a suppression later. What is genuinely open is what the operator sees and what they are asked to do: whether a factual_evidence carry is presented as a prefilled figure awaiting confirmation against the taxpayer's own document, whether it carries a distinct label in the casilla payload, and whether any surface distinguishes confirmed from unconfirmed. Gate: a factual_evidence carry reaches an operator-facing surface carrying its treatment and its provenance, no code path withholds or zeroes a value on the basis of its treatment, a test proves a value survives both classifications unchanged, and any confirmation affordance added is additive rather than a precondition for the value appearing at all

## Scope

- `src/cadrumo/application/modelo`
- `src/cadrumo/entrypoints/cli`

## Description

- Confirmed the exact remaining gap: the declared treatment already reached
  `PrefilledBinding` and `RelationValue` (prior work), but neither resolver
  join actually read it back off, and the domain-persisted provenance trace
  and the CLI JSON boundary carried no such field at all.
- Added `dependency_treatment` to `CalculationSourceProvenance` (the
  resolver-produced application provenance model) and to `CalculationSourceRef`
  (its domain-persisted projection on a calculation revision), both defaulting
  to the empty undeclared string.
- Threaded the real, already-available value through both resolver join
  sites: `PreviousFilingSourceResolver.resolve` and
  `RelationPrefillSourceResolver.resolve` now pass the resolved item's
  declared treatment into the provenance row they construct.
- Threaded the domain-boundary projection: the application-to-domain mapper
  that builds persisted `CalculationSourceRef` rows from resolved provenance
  now carries the treatment across, rather than dropping it the way the
  per-casilla legal and source refs are deliberately dropped there.
- Surfaced the pair at the operator-facing CLI JSON boundary: added a typed
  `SourceProvenancePayload` row and a `source_provenance` field on the shared
  calculation-revision projection mixin every calculate/revision/wizard
  command result subclasses, populated by the shared rendering function that
  every one of those commands already calls.
- Extended real, non-mocked coverage at every hop rather than adding a single
  synthetic unit test: the encrypted calculation-revision roundtrip (plus an
  anti-tautology field-drop proof distinct from the existing blank-`source_ref`
  proof, since this field is optional and defaults non-vacuously), the real
  M180-annual/M115-quarterly relation-prefill resolver test (a real registry
  dependency classification declares `direct_annual_settlement` for this
  fold-in), the real M303 self-referential previous-filing IVA-compensation
  carry test (a real classification declares `factual_evidence`), the live
  M180 calculate end-to-end test asserting the PERSISTED revision carries the
  treatment, and the CLI payload projection test. Every one of these also
  asserts the accompanying casilla value is unchanged by the treatment it
  carries.

## Outcome

COMPLETE against the row's gate. A `factual_evidence` carry (and a
`direct_annual_settlement` one, exercised side by side so neither is
special-cased) now reaches the operator-facing CLI JSON payload carrying both
its treatment and its provenance. No code path added by this row withholds,
blanks, or zeroes a value on the basis of its treatment; the treatment field
is additive everywhere it was added (a defaulted, optional field on already
optional/default-carrying tuples), so nothing existing regresses when it is
absent. No confirmation affordance was added, so there is nothing that could
gate the value's appearance on being acted upon.

While running the broader regression sweep, several pre-existing failures
unrelated to this row surfaced: a widespread `iva.m303_regime_composition
must be explicitly declared` profile error across roughly three dozen tests
under the calculations application tests, a stale core-struct docstring-link
gate failure naming unrelated registry and CLI modules, and the same M303
regimen-simplificado-scope failure already flagged during an earlier row in
this session. Each was confirmed unrelated by running it in isolation, by
checking that none of the implicated files were touched here, and by tracing
the failures to code this row never modified. None were fixed here; they are
out of this row's scope and appear tied to concurrent work elsewhere in this
shared tree.

## Notes

No new human-readable text line was added for the provenance/treatment pair;
only the typed JSON payload field. The CLI envelope's JSON list is the
canonical machine-consumable operator-facing contract for grounding-shaped
data per this project's established pattern (the same shape already used for
per-casilla legal and source refs), and the row's gate asks for reaching an
operator-facing surface, not a specific text rendering. A follow-up may add a
text-line summary if an operator workflow calls for one.

The row's open question about a confirmation affordance (whether a
`factual_evidence` carry should be presented as awaiting confirmation against
the taxpayer's own document) is left for a follow-up: today nothing consumes
`dependency_treatment` to gate or label anything beyond carrying it through to
the payload, which satisfies "additive rather than a precondition" trivially
by there being no consumer yet, not by a deliberately inert one.
