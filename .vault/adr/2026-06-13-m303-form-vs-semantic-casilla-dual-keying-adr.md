---
tags:
  - '#adr'
  - '#m303-form-vs-semantic-casilla-dual-keying'
date: '2026-06-13'
related:
  - '[[2026-06-09-modelo-iva-routing-carry-adr]]'
  - '[[2026-04-17-modelo-303-formulas-adr]]'
  - '[[2026-06-10-calculation-aggregation-taxonomy-adr]]'
  - '[[2026-06-04-m303-form-vs-semantic-casilla-dual-keying-research]]'
  - '[[2026-06-01-m303-iva-resultado-semantic-casilla-mismatch-research]]'
  - '[[2026-08-07-official-form-coverage-audit]]'
  - '[[2026-08-10-casilla-schema-canonical-derivations-adr]]'
  - '[[2026-07-01-modelo-303-regimen-simplificado-adr]]'
  - '[[2026-07-05-cross-period-prorrata-adr]]'
  - '[[2026-06-13-m303-form-vs-semantic-casilla-dual-keying-reference]]'
  - '[[2026-07-07-prorrata-sectores-diferenciados-adr]]'
supersedes:
  - '2026-07-01-modelo-303-regimen-simplificado-adr'
modified: '2026-08-10'
body_hash: 'sha256:9915aa048a672b0140a49d666ce9430f049f743ee450df9eee82f608aaa2d624'
---
# `m303-form-vs-semantic-casilla-dual-keying` adr: `M303 semantic homes and exact fixed-slot official projection` | (**status:** `accepted`)

## Problem Statement

Modelo 303 has one official fixed record but several legitimate semantic grains. Treating every official field as a casilla, header string, or parser-owned value would create parallel authorities; treating every repeated block as copies of existing global scalars would fabricate detail. This amendment decides one producer and one projection rule for every S44 field family while retaining the accepted dual-key rule.

## Considerations

- The missing annual, activity-prorrata, and differentiated-sector blocks and their row shapes are grounded by `2026-08-07-official-form-coverage-audit` and `2026-06-04-m303-form-vs-semantic-casilla-dual-keying-research`.
- Existing profile, filing, prorrata, sector, and simplified-formula owners are inventoried in `2026-06-04-m303-form-vs-semantic-casilla-dual-keying-research`.
- `2026-08-10-casilla-schema-canonical-derivations-adr` owns official-box classification only; this record must not duplicate it.

## Considered options

- **One untyped export-header or parser-field authority** -- rejected: it collapses persistence, calculation, security, applicability, and transport into one mutable string surface.
- **Official casilla or scalar per fixed source slot** -- rejected for repeated blocks: it redeclares row identity and invites a second calculation path.
- **One typed canonical owner per semantic grain, followed by exact fixed-slot projection** -- chosen: it preserves established calculation owners while making every source anchor classifiable exactly once.
- **A sibling M303 projection ADR** -- rejected: the accepted dual-key ADR already governs this decision and is amended in place.

## Constraints

- Semantic `casilla.id` remains the calculation key. Official numbered casillas are downstream projection endpoints and never an independent aggregation surface.
- The reviewed semantic map joins one exact parser anchor to one canonical producer. It may classify constants and reserves literally but may not invent a producer, infer by number or label, fall back to a header default, or consult a legacy layout.
- `classify_official_boxes` is the sole official-box classifier. It answers addressability, not producer ownership, semantic identity, completeness, or value arrival.
- Applicability is typed and fail-closed. Blank is legal only when the canonical applicability decision is not-applicable. An applicable incomplete block or missing value refuses the complete export.
- No compatibility aliases, scalar bridges, duplicate selectors, direct header fallbacks, plaintext account paths, or legacy read tolerance survive consumer retargeting.

## Implementation

### Existing exact numbered-box projections remain binding

The already-ratified boxes `03`, `06`, `09`, `11`, `13`, `27`, `29`, `33`, `37`, and `45` remain computed single-leaf projections from their exact semantic casilla sources recorded in `2026-06-13-m303-form-vs-semantic-casilla-dual-keying-reference`. They carry the official box grounding and equality consistency gate. They never gain a ledger binding, relation, previous-filing carry, or second calculation. This amendment broadens the ownership contract; it does not reopen or weaken those mappings.

### Canonical ownership matrix

| Official field family | Canonical semantic home | Fixed-record projection rule |
| --- | --- | --- |
| Calculated and operator-entered tax amounts | The selected revision's semantic casilla graph: binding, formula, or explicitly manual casilla according to its declared input kind | Project through the official numbered casilla endpoint when one exists; otherwise map the exact source anchor directly to the same semantic casilla. Never aggregate again for export. |
| Annual-summary block for the exonerated-390 population | Official annual-summary numbered casillas in the selected M303 revision, populated by the existing semantic calculation/binding owners they summarize; the exoneration election is a stable typed profile fact | Project every required endpoint only when the profile says the block applies. The flag and every required endpoint form one completeness unit; partial emission refuses. |
| Five per-activity prorrata rows, official boxes 500-524 | One typed M303 filing-row collection keyed by stable activity identity and explicit slot, carrying CNAE, operation volume, deduction-right volume, prorrata regime/type, percentage, legal refs, and source refs | Exact slot 1-5 and column projection. Do not copy the global prorrata scalar into five rows. Existing whole-entity prorrata computation remains authoritative for the global result; a row may reference it only when identity and grain match, and reconciliation is a gate rather than another computation. Applicable collections must be complete and have unique slots. |
| Two differentiated-deduction sector rows, official boxes 700-735 | Existing sector identity, `ProrrataSector` inputs, sectoral prorrata result, and sector-aware ledger aggregation, exposed through one typed M303 sector-row projection carrying identity, totals, legal refs, and source refs | Exact slot 1-2 and column projection from the canonical sector calculation. No export-specific deduction sum, parallel sector selector, or copied scalar path. Applicable sector filings require both law-required rows and totals. |
| Simplified-regime activities and modules | One typed collection of activity rows keyed by IAE activity identity, each carrying typed module-quantity entries and the filing-year annual-Orden/IAE parameter identity | Exact official activity/module slot projection from the collection. The existing registry formula mechanism remains the sole calculation owner and consumes the collection; no second resolver or per-slot scalar authority. Official box 48 remains manual with blocking/advisory protection until complete accepted coverage permits a later explicit promotion. |
| Stable taxpayer and IVA-profile facts | Persisted typed `TaxpayerProfile` / `ModeloIVAProfile` fields | Direct typed projection; no export-header-owned defaults or string-key redeclarations. |
| Refund, payment, amendment, and prior-domiciliation elections | Typed immutable filing-instance state after workflow validation | Project the resolved election/evidence; no profile default or result-shape inference may replace an absent required election. |
| Presenter identity | A dedicated typed filing-instance presenter value, distinct from taxpayer identity | Project the presenter value. Never default presenter NIF/name to taxpayer NIF/name. |
| Charge and refund account fields | Typed charge/refund account records in secure profile storage, selected by the resolved disposition | Read only at the secure application boundary and project only the selected account fields. Never persist plaintext in registry, casilla, semantic-map, execution, or audit artifacts. Missing required account data refuses. |
| Constants, record markers, and reserved bytes | Hash-verified parser IR and source-bound render profile | Emit the exact source-declared literal or reserve policy. They have no application producer and cannot be reclassified as filler for an unsupported semantic field. |

The public registry/export schema owns the closed producer vocabulary used by semantic maps. Application producers return typed values keyed by that vocabulary; the renderer formats but does not derive them. Consumer migrations delete every replaced key list, selector, scalar row surrogate, and fallback in the same landing.

## Rationale

This option is the only one that gives each official anchor exactly one producer without merging unlike lifetimes or duplicating calculations. It extends the accepted dual-key direction rather than replacing it: semantic values remain authoritative, official positions remain projections, and repeated official structures gain typed row identity instead of scalar copies. It also composes cleanly with the separate casilla-schema classifier.

The proposed simplified-regime ADR's durable one-formula and shared annual-Orden direction is absorbed here. Its scalar support shape is replaced by the typed activity/module collection, so the proposed record is superseded by this amended governing record rather than accepted alongside it.

## Consequences

- Every M303 source anchor can be censused against one canonical producer or a parser-owned literal, with duplicate and unsupported classifications refused.
- Annual, activity, sector, simplified, profile, election, presenter, payment, and account completeness become explicit applicability gates.
- Repeated blocks require new typed projection models, but they do not create new IVA calculations.
- Existing global prorrata, sector deduction, and simplified formula authorities remain load-bearing; export-specific copies are deleted.
- Presenter identity and secure accounts can no longer ride on convenient taxpayer/header fallbacks, so callers must supply the correct typed filing facts.
