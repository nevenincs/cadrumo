---
tags:
  - '#adr'
  - '#justificante-identity-matching'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:07fc95b6d231bedc273bc5f984395712a4e2af85f9bc8bd13d1f38acf6fb844d'
related:
  - "[[2026-08-07-justificante-identity-matching-reference]]"
  - "[[2026-06-10-live-justificante-reconcile-adr]]"
  - "[[2026-05-04-live-filing-data-capture-adr]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #adr) and one feature tag.
     Replace justificante-identity-matching with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     Status convention: the H1 status value is one of proposed, accepted,
     rejected, superseded, or deprecated. A new ADR starts as proposed; it
     moves to accepted or rejected when the decision is made; it becomes
     superseded when a later ADR replaces it (set by vault adr supersede,
     which also records superseded_by); and deprecated when it is retired
     without a direct successor.

     Amend vs supersede: refinements and concretization rewrite the accepted
     record's body in place (modified: carries the revision); a new ADR with
     supersession is only for a major pivot. One accepted record per
     decision.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `justificante-identity-matching` adr: `Justificante presentation_id namespace correction` | (**status:** `accepted`)

<!-- DOCUMENT BOUNDARY:
     This record owns the decision and only the decision. Grounding evidence
     lives in the related research/reference documents and is cited by stem
     (e.g. `2026-02-04-editor-demo-research`), never restated - a restated
     fact forks and goes stale. A fact this record needs but the grounding
     lacks is added to the grounding first, then cited. -->

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
- All three callers pass `expediente_id` into `presentation_id` — systemic
  across the three call sites, not M303-specific — reference, "Every caller
  conflates the two namespaces".
- One call site (`register_capture_as_filing_evidence`) already runs a
  genuine, independently-sourced `csv == csv` identity check before the
  broken comparison — reference, "Site 3 already has a correct, independent
  identity check".
- The two register-reconciliation call sites have no independently-known
  receipt-namespace value in scope to compare against; the artefact-to-
  observation pairing is already structurally bound by the register's own
  download-link scoping and a manifest byte-count/sha256 check — reference,
  "No independently-known receipt-namespace identifier exists at the
  register-reconciliation call sites".
- Removing a guard that never validly compares like-for-like is not the same
  action as relaxing a guard that does; `no-silent-under-declaration` and the
  worktree rules' distrust of removing checks apply to the latter, not
  automatically to the former, but the burden of proof stays on this record to
  show what still prevents a mis-stamp after the change.

## Considered options

1. **Drop the `presentation_id` check everywhere it fires on `expediente_id`
   (chosen, scoped).** Stop passing `expediente_id` where no receipt-namespace
   counterpart exists. Rejected as a blanket move, adopted only where the
   value being passed is provably wrong-namespace and a structural binding
   already substitutes for it (the two register-reconciliation sites).
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
4. **Add a typed `identifier_namespace` marker to `matches_filing_target` and
   require the caller to declare it, refusing at the type level when a
   register-namespace value is passed as `presentation_id`.** Deferred rather
   than adopted: it would touch the predicate's signature and every caller's
   call shape for a recurrence risk this decision instead closes with a
   docstring contract plus a corrected pinning test; kept here as the
   named future hardening if the docstring contract proves insufficient.
5. **Route the two register-reconciliation sites through `csv` instead of
   `presentation_id`, by capturing the register row's justificante-link CSV
   before parse.** Rejected for this decision: `Declaracion` has no `csv`
   field today and the link text captured (`justificante_link_text`) is not
   established as a CSV value; inventing that binding is out of scope here
   and belongs to a future ADR if the register surface is extended.

## Constraints

- No live AEAT access from this record's implementing rows; every fix is
  verified against the two already-captured encrypted PDF fixtures and unit
  coverage, never a fresh live pull.
- A pinning test asserting today's (defective) rejection is being authored in
  parallel by another agent; the implementing row that lands the fix MUST
  update that test's assertion to the corrected behavior in the same change —
  it must not be deleted, skipped, or left asserting the old defect.
- No legal-catalogue entries are touched by this decision; it is a pure
  identifier-matching correction with no BOE/AEAT legal-provenance
  implication.

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
