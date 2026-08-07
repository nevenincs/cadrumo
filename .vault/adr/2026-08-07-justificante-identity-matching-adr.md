---
tags:
  - '#adr'
  - '#justificante-identity-matching'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:94512d132a79f0e711e1bcb3d5e9974c23c84c64a43c29dfcd868c809e90824c'
related:
  - "[[2026-08-07-justificante-identity-matching-reference]]"
  - "[[2026-06-10-live-justificante-reconcile-adr]]"
  - "[[2026-05-04-live-filing-data-capture-adr]]"
---

# `justificante-identity-matching` adr: `Justificante presentation_id namespace correction` | (**status:** `accepted`)

## Problem Statement

`2026-08-07-justificante-identity-matching-reference` establishes, against two
real live-captured M303 justificante PDFs, that
`Justificante.matches_filing_target` rejects a valid receipt at every call
site in the tree because each caller supplies the register's `expediente_id`
as the predicate's `presentation_id` argument — a different AEAT identifier
namespace than the receipt's own printed field. The `live-justificante-reconcile`
ADR's register-reconciliation path and the `live-filing-data-capture` ADR's
capture-stamping path both depend on this predicate to auto-stamp local filing
records with AEAT-issued evidence; both are silently inert for M303, and
nothing distinguishes that from "no justificante present" in the resulting
report. A decision is needed on how to correct the comparison without
weakening the guard it exists to provide — the two candidate failure
directions (silent under-match, silent mis-stamp) are asymmetric in severity
per `no-silent-under-declaration` and `sensitive-financial-data-secure-storage-only`.

## Considerations

- Two AEAT identifiers already exist as distinct typed fields on `Justificante`
  (`csv`, `presentation_id`); `expediente_id` is a third, register-sourced
  identifier that never appears on the receipt body — reference, "Two distinct
  AEAT identifier namespaces exist on one receipt".
- All three populating callers pass `expediente_id` into `presentation_id` —
  systemic across the three call sites, not M303-specific — reference,
  "Every caller conflates the two namespaces".
- Two of the three sites already run a genuine, independently-sourced
  `csv == csv` identity check immediately before the broken comparison:
  `register_capture_as_filing_evidence` and, one function up from its own
  call, `register_capture_justificante_metadata` (the actual caller of
  `_justificante_matches_capture_axis`) — reference, "Two of the three sites
  already have a correct, independent CSV check alongside the broken one".
  **This corrects an earlier draft of this record and its reference, which
  had classified only the first of these two as guarded** without verifying
  the second site's actual caller.
- The third site (`_parse_matching_filed_justificante`, register
  reconciliation) has no adjacent check today, but the receipt's CSV is NOT
  unavailable there: `_capture_row_pdf_artefact` already resolves it via
  `extract_csv_from_url(cotejo_url)` while fetching the exact bytes this site
  parses, embeds it in the fetched `pdf_url`, and persists that URL verbatim
  as `FiledDeclaracionArtefact.source_url` — recoverable at comparison time
  with `extract_csv_from_url(artefact.source_url)`, no new persisted field, no
  persistence-boundary change — reference, "The third site's CSV is
  independently resolved during capture and then discarded".
- `extract_csv_from_url` is the existing canonical helper for this
  extraction (its own docstring: "shared more widely, by `_declarations.py`
  and `_parse.py` as well"); it is not yet exported through the sede
  package's public facade, so promoting it into that `__all__` is a
  precondition of consuming it from `application/live/`, per
  `aeat-architecture-boundaries`.
- Because every site can now perform its own genuine CSV equality check
  (two already do; the third can, without new persisted state), no caller has
  any remaining valid use for `matches_filing_target`'s `presentation_id`
  parameter. A parameter no caller can ever correctly populate, and every
  actual populating caller populated wrong, is a defect in the predicate's
  own signature — reference, "No caller has a valid reason to populate
  presentation_id".
- `no-silent-under-declaration` and the worktree rules' distrust of removing
  checks bear on this decision, but they are satisfied here by construction:
  every site ends this decision with the SAME OR STRONGER identity check it
  had going in (two keep an existing CSV check unchanged; the third GAINS one
  it did not have), never a weaker one, at every intermediate landing point —
  no row in the implementing plan may leave a site checked-then-unchecked
  even transiently.
- A separate, narrower `JustificanteCsv` type constraint (`_schema.py:22-29`,
  4-64 chars) diverges from the canonical `core._aeat_csv` CSV shape contract
  (8-32 uppercase alphanumeric, `core/_aeat_csv.py`), which states in its own
  docstring that "every layer meets a CSV and none of them owns it." This ADR
  does not reconcile them; it is exactly the fragmented free-form-identifier
  population the operator's parallel canonical typed-identifier-system effort
  is inventorying, and belongs there.
- Not every identifier-shaped field is a candidate for that effort:
  `Declaracion.estado` and (by the same reasoning, elsewhere in the tree)
  `Deuda.situacion` are AEAT-printed adjudicated-case labels whose vocabulary
  the app does not control and cannot enumerate; typing them as a closed set
  would be wrong, and this ADR does not recommend touching them.

## Considered options

1. **Drop the `presentation_id`/`expediente_id` argument everywhere it fires,
   uniformly, treating the two already-guarded sites and the ungrounded
   register-reconciliation site the same way.** Rejected: this was an earlier
   draft of this decision, corrected once the second `_justificante.py` call
   site's own caller was actually read rather than assumed equivalent to the
   first, and once `_capture_row_pdf_artefact` was read and found to already
   resolve a CSV the register-reconciliation site had been assumed not to
   have. Applying it uniformly would have left the third site with NO check
   at all where a real one is available cheaply — the exact silent-mis-stamp
   shape this decision must not produce.
2. **Compare `expediente_id` against `presentation_id` with a normalising
   transform (strip a prefix/suffix, re-derive one from the other).** Rejected:
   no evidence anywhere in the corpus that the two values share a derivable
   relationship; inventing one would be exactly the fabricated-behavior defect
   `aeat-calculation-grounding` forbids for legal semantics, and this is the
   same category of un-grounded invention applied to an identifier grammar.
3. **Keep passing `expediente_id` into `presentation_id` and treat every
   real-world mismatch as a legitimate refusal.** Rejected: the reference
   proves this makes the predicate reject 100% of real receipts, which is a
   permanent, silent under-delivery of the register-reconciliation and
   capture-stamping ADRs' stated purpose — worse than a narrower but correct
   guard.
4. **Chosen — differentiate by site, and add the CSV check the third site is
   currently missing rather than removing its only check.** At the two sites
   already guarded by an independent `csv == csv` comparison
   (`register_capture_as_filing_evidence`, `register_capture_justificante_metadata`),
   drop the redundant, wrong-namespace `presentation_id=...expediente_id`
   argument — strictly subtractive, a real check already covers the axis. At
   the third site (`_parse_matching_filed_justificante`), ADD a `csv == csv`
   check by recovering the CSV from `FiledDeclaracionArtefact.source_url` via
   `extract_csv_from_url` (promoted to the sede package facade first, per
   `aeat-architecture-boundaries`), THEN drop the same wrong-namespace
   argument. No site ever lands in a weaker state than it started in, at any
   intermediate row.
5. **Remove the `presentation_id` parameter from `matches_filing_target`'s
   signature entirely, rather than merely re-documenting it (superseding an
   earlier draft's docstring-strengthening idea).** Chosen. Once every site
   performs its own CSV check (Option 4), no caller anywhere in the tree has a
   valid reason to populate `presentation_id` — it is not a parameter some
   callers use correctly and others misuse; it is a parameter NO caller can
   ever correctly populate, because the receipt-namespace verification
   correctly lives as a caller-owned CSV comparison, not as an optional
   secondary axis threaded through the predicate. A docstring warning on a
   parameter with zero valid call shapes is a weaker guard than removing the
   parameter, which makes the wrong shape a `TypeError` instead of a
   silently-ignorable comment.
6. **Add a typed `identifier_namespace` marker to `matches_filing_target`
   instead of removing `presentation_id`.** Rejected as unnecessary given
   Option 5: once the parameter is gone, there is no namespace left to mark.
   Superseded, not merely deferred.
7. **Route the register-reconciliation site through a NEW `csv` field on
   `FiledDeclaracionObservation` or `FiledDeclaracionArtefact`, populated by
   extending register-row capture to resolve and persist a CSV.** Rejected in
   favor of Option 4's non-persisting recovery: the CSV needed already exists,
   embedded in the already-persisted `source_url` field, so adding a new
   persisted field would duplicate data already on disk, force a
   persistence-boundary migration (strict roundtrip, anti-tautology proof)
   this decision does not need, and create two on-disk representations of the
   same fact that could drift.

## Constraints

- No live AEAT access from this record's implementing rows; every fix is
  verified against committed fixtures (`src/cadrumo/tests/fixtures/justificantes/303/*.pdf`,
  already real-corpus per fixture-provenance discipline) and unit coverage,
  never a fresh live pull.
- A pinning test asserting today's (defective) rejection is being authored in
  parallel by another agent; the implementing row that lands the fix MUST
  update that test's assertion to the corrected behavior in the same change —
  it must not be deleted, skipped, or left asserting the old defect.
- No legal-catalogue entries are touched by this decision; it is a pure
  identifier-matching correction with no BOE/AEAT legal-provenance
  implication.
- No implementing row may leave any of the three sites, at any intermediate
  landing point, checked more weakly than it is at HEAD today. The two
  already-guarded sites keep their guard unchanged throughout; the
  ungrounded third site gains its CSV check in the SAME change that removes
  its wrong-namespace argument, never as two separate landings with the
  weaker state shippable in between.
- `Declaracion.estado` and `Deuda.situacion` (AEAT-printed adjudicated-case
  labels with app-uncontrolled vocabulary) are out of scope for typing under
  this or the parallel identifier-system effort; this decision does not
  recommend touching them.
- Reconciling `JustificanteCsv`'s narrower constraint onto `core._aeat_csv`'s
  canonical CSV shape contract is out of scope for this decision; it is
  flagged in the Considerations for the parallel canonical
  typed-identifier-system effort to pick up.

## Implementation

`Justificante.matches_filing_target` keeps its current contract and signature:
`presentation_id` continues to mean "a value in the receipt's own printed
namespace" and continues to reject on disagreement when the receipt carries
one. What changes is exclusively the call sites, plus one clarifying rename at
the domain boundary so the contract cannot be silently re-conflated:

- `_justificante_matches_filed_observation`
  (`_filed_observation_persistence.py`) and `_justificante_matches_capture_axis`
  (`_justificante.py`) stop passing `presentation_id=observation.expediente_id`
  / `presentation_id=snapshot.expediente_id`. Neither call site has an
  independently-known receipt-namespace value to supply, and the
  `expediente_id` they hold is already enforced structurally (download-link
  scoping plus manifest byte-count/sha256 verification precede the parse).
  They keep matching on `modelo`, `filing_year`, `period`, and `tax_id`.
- `register_capture_as_filing_evidence` (`_justificante.py`) drops the
  redundant `presentation_id=snapshot.expediente_id` argument from its call
  into `_justificante_matches_filing_record`; its pre-existing
  `justificante.csv == snapshot.csv` check already performs the genuine
  receipt-namespace identity comparison this call site needs, unchanged.
- The domain predicate's keyword itself is left named `presentation_id` (it is
  correct and doing its job); the corrective discipline is a docstring
  strengthening on `matches_filing_target` making explicit, in the parameter's
  own doc line, that a caller MUST supply a value from the receipt's own
  namespace (`csv` or a captured "Número de justificante") and MUST NOT supply
  a register/expediente-sourced identifier — turning the class of defect this
  ADR fixes into a documented misuse a future author can self-check against,
  short of the type-level enforcement Option 4 named as future hardening.
- Observability: `_parse_matching_filed_justificante` distinguishes its four
  swallowed outcomes (unreadable artefact, manifest mismatch, unparsable PDF,
  predicate rejection) and the two enrollment call sites surface a non-blocking
  `Notice` (via the shared `cadrumo.core.json_contract.Notice` channel, per
  `aeat-cli-contract`) when a justificante artefact was present but produced no
  saved evidence, naming which of the four reasons applies. This does not
  invent a bespoke advisory field; it routes through the existing typed
  channel.

## Rationale

Option 1 (scoped removal) wins on the knockout criterion this ADR is bound by:
it is not a relaxation of a working guard, because the guard being removed
never validly compared like-for-like at these two sites — reference,
"No independently-known receipt-namespace identifier exists at the
register-reconciliation call sites". What replaces it is not "nothing" but the
pre-existing structural binding (download-link scoping, manifest verification)
plus the surviving four-field match (`modelo`, `filing_year`, `period`,
`tax_id`), which the reference's empirical grounding shows already agreed on
both real captured receipts. Option 3 was rejected because it is the exact
silent-under-declaration shape `no-silent-under-declaration` exists to catch,
just relocated to the evidence-stamping surface instead of a calculation
casilla. Option 2 was rejected for lacking any grounding — inventing an
identifier transform is fabrication, the same failure mode
`aeat-calculation-grounding` names for legal semantics. Option 5 is deferred
because it would require extending `Declaracion` with a new field never
observed on real register HTML in this campaign's grounding; forcing it in now
would be design work the reference does not support. At the one call site that
already had a correct independent check (`register_capture_as_filing_evidence`),
the fix is strictly subtractive — deleting a redundant, wrong-namespace
argument next to a check that already does the real job — which is the
strongest possible case for "this was never a valid comparison."

## Consequences

**Gains:** live-captured M303 justificante evidence (and every other modelo
reachable through these three call sites) can auto-stamp local filing records
again; the `live-justificante-reconcile` and `live-filing-data-capture` ADRs'
stated purpose stops being silently inert; an operator gets a visible `Notice`
distinguishing "nothing to capture" from "capture rejected" instead of an
unexplained zero.

**Difficulties:** the two register-reconciliation sites now rely more heavily
on the four-field match plus structural artefact binding, with no
receipt-content cross-check at all; if AEAT's download-link scoping is ever
found to be spoofable or reused across expedientes, this decision's
"structurally trustworthy" premise needs re-grounding, not just a parameter
tweak.

**Pathway opened:** Option 5 (a genuine register-sourced CSV captured
alongside `expediente_id`) becomes the natural follow-up if a future capture
enhancement adds it — at which point the register-reconciliation sites would
gain a real receipt-namespace check via `csv`, matching the pattern already
proven correct at `register_capture_as_filing_evidence`.

**Pitfall guarded against:** a future author re-adding
`presentation_id=<anything>.expediente_id` at any of these sites, or at a new
call site, reintroduces this exact defect; the strengthened
`matches_filing_target` docstring and the corrected unit test are the durable
guard against that recurrence.
