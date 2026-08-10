---
tags:
  - '#audit'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:399e6c44e1e52595fc71a1b2b6ac63c56bca911fd019c3368e33ccade9592722'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
  - "[[2026-06-13-m303-form-vs-semantic-casilla-dual-keying-adr]]"
  - "[[2026-07-01-modelo-303-regimen-simplificado-adr]]"
  - "[[2026-08-10-casilla-schema-canonical-derivations-adr]]"
---
# `aeat-export-fragment-generator-authority` audit: `S44 M303 semantic-home architecture reconciliation`

## Scope

Independently reviewed the amended accepted M303 dual-key ADR against the accepted cross-period-prorrata and casilla canonical-derivations decisions, the separate proposed simplified-regime ADR, the official-form coverage audit, S44 research, plan and execution record, the exact projection reference, and the live encrypted prorrata-register and sector substrates. This audit decides architecture and lifecycle consistency only. S45-S52 retain implementation, producer availability, value arrival, applicability, and five-epoch proof.

## Findings

### incorrect-simplified-regime-supersession | high | Resolved: the proposed calculation record was briefly superseded by the projection amendment

The first S44 curation pass incorrectly treated the proposed simplified-regime calculation-completeness decision as a sibling projection authority and superseded it. That collapsed two different grains: the accepted dual-key ADR owns semantic homes and fixed-slot projection, while the proposed record owns the still-unaccepted threshold for completing the simplified-regime calculation and promoting casilla 48.

Resolved through hash-guarded VaultSpec mutations. The reciprocal supersession metadata was removed, the simplified-regime H1 was restored to `proposed`, and the dual-key ADR, grounding research, and S44 execution record now state consistently that the proposed record remains separate and non-governing. This subsection preserves the reversal history; the mistaken supersession is not treated as if it never occurred.

### stale-simplified-revision-premise | medium | Resolved: the proposed record no longer names the retired spanning revision as current architecture

The independent pass found the proposed simplified-regime ADR still describing two coarse M303 revisions and the retired `2023-y-siguientes` revision. That contradicted the five explicit law-selected modern design bindings already established by S35, S36, and S39.

Resolved through a hash-guarded body amendment. The proposed ADR now separates per-year Orden parameter selection from law-selected M303 design selection, names the five explicit bindings, and denies any fallback to the retired spanning revision.

### prorrata-register-single-home | high | Pass: repeated prorrata and differentiated-sector rows do not create another store or calculation carrier

The five official activity rows are decided as typed children extending the sole encrypted `ProrrataRegister`, with stable activity identity and evidence. They do not copy the global prorrata scalar or create per-slot fields, selector lists, an export store, or a second persistence carrier. The two differentiated-sector rows project the register's existing `SectorDefinition` and `ProrrataRegisterEntry` state directly; they do not add another sector collection, repository, or deduction total. The live register and encrypted repository confirm that sector definitions and per-ejercicio sector entries already share one guarded singleton document.

### official-only-casilla-endpoint | medium | Pass: annual-summary values need no shadow semantic identifier

The amended decision permits an official numbered annual-summary casilla with no upstream semantic twin to be its own canonical endpoint. Existing upstream facts still project where present, and the exoneration flag plus every required endpoint form one applicability/completeness unit. This preserves one owner per fact without fabricating a parallel semantic id.

### classifier-and-delivery-boundary | high | Pass: declaration, implementation, value arrival, and applicability remain separately owned

`classify_official_boxes` remains the sole three-state slot-declaration classifier and is not widened into a producer or population authority. S45 owns producer vocabulary, S46 typed application producers, S47-S50 the four M303 projection families, S51 fail-closed applicability, and S52 exact-anchor and exactly-once proof. The ADR does not claim those later steps are implemented. Applicable missing authority remains a whole-export refusal.

### stale-stage-two-and-open-question-prose | medium | Pass: the governing decision is revision-neutral and closed

The amended accepted ADR contains no unresolved operator questions, conditional Box 37 choice, selective single-revision inventory, or stale Stage-2 implementation narrative. Its exact previously ratified numbered-box map remains historical reference material; the governing architecture is revision-neutral and assigns five-epoch implementation and proof to S45-S52.

## Verification

- Full-file review of the governing ADR, proposed simplified-regime ADR, accepted cross-period-prorrata and casilla derivation ADRs, S44 research, plan, execution record, durable audit history, and exact projection reference.
- Semantic VaultSpec RAG searches over the decision corpus and production code, followed by exact `rg` confirmation of status, supersession, revision, classifier, register, sector, and delivery language.
- Feature-scoped frontmatter, mandatory-body-section, ADR-status, body-link, schema, and execution-mapping checks returned zero diagnostics on the reviewed lifecycle surfaces.
- The simplified-regime ADR carries status `proposed` with no `superseded_by`; the accepted dual-key ADR carries no `supersedes` edge for it.
- The encrypted prorrata repository stores one strict `ProrrataRegister` singleton containing both entries and sector definitions; no second activity or sector store is authorised by S44.

## Recommendations

- S46 is complete; proceed to S45. S45-S52 must remain open until their named implementation and proof gates pass; this S44 PASS is not evidence that those surfaces already exist.
- At S52, import `classify_official_boxes` for declaration and keep value-arrival and applicability assertions in their owning gates.
- Re-run curation after S52 to confirm the planned migrations removed every header fallback, scalar-row surrogate, duplicate selector, and unsupported-as-filler path.

## Final verdict

PASS. No open critical, high, medium, or low S44 architecture or lifecycle findings remain on the reviewed snapshot. The initial simplified-regime supersession and stale revision premise are resolved and retained above as review history.
