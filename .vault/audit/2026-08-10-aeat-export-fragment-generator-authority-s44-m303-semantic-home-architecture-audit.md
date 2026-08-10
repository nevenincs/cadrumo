---
tags:
  - '#audit'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:47ed6e0c580f4503a6cfedf1def0c97c892e44afdae27c4d880d268577317254'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
  - "[[2026-06-13-m303-form-vs-semantic-casilla-dual-keying-adr]]"
  - "[[2026-07-01-modelo-303-regimen-simplificado-adr]]"
  - "[[2026-08-10-casilla-schema-canonical-derivations-adr]]"
---
# `aeat-export-fragment-generator-authority` audit: `S44 M303 semantic-home architecture reconciliation`

## Scope

Reconciled the accepted M303 dual-key ADR, the proposed simplified-regime ADR, the official-form coverage audit, the accepted casilla-schema canonical-derivations ADR, their grounding research, and the live profile, prorrata, sector, simplified-formula, filing-election, presenter, and account projection sites. The audit covers architecture and lifecycle status only; implementation remains in S45-S52.

## Findings

### fragmented-m303-projection-decision | high | The proposed simplified-regime record carried a sibling portion of the governing M303 projection decision

The accepted dual-key record already governed semantic-to-official projection, while the proposed simplified-regime record separately chose the one-formula/shared-Orden direction and retained scalar activity/module inputs. Leaving both live would fragment one M303 producer/projection decision and permit the fixed-slot implementation to choose between incompatible input grains.

Actioned: amended the accepted dual-key ADR in place to absorb the durable one-formula/shared-Orden constraint and decide a typed activity/module row collection; superseded the proposed simplified-regime ADR through the CLI so exactly one record governs.

### restated-grounding-in-governing-adr | medium | The accepted ADR mixed inventory evidence with the decision and its grounding bridge carried no substantive research

The previous ADR body repeated registry counts, labels, implementation observations, and execution history. Its related research was only a retrospective linkage bridge. This inverted the single-home boundary and made later amendment depend on stale evidence inside the decision.

Actioned: replaced the bridge with locator-grounded comparative research and reduced the ADR to options, constraints, ownership, projection rules, rationale, and consequences. The exact already-ratified numbered-box projection map remains linked through its reference and expressly remains binding.

### official-box-classifier-scope-preserved | medium | The casilla-schema classifier could have become a competing M303 semantic authority

The accepted casilla-schema ADR decides only whether a casilla is ADDRESSED, REPRESENTED_VIA_BINDING, or UNDEFINED. It does not choose a producer, row identity, applicability, or emitted value.

Actioned: the amended M303 ADR imports that classifier as the sole official-box classification dependency and explicitly denies it producer or population authority.

### application-projection-drift-remains | high | Current implementation still contains transport-derived producer semantics and scalar repeated-field shapes

The live export header composer derives presenter identity from taxpayer identity and assembles multiple lifetimes into a mutable string-key dictionary. The simplified formula consumes one epigraph and three scalar module slots. The annual-summary, five-row activity-prorrata, and two-row differentiated-sector official surfaces are not yet complete. These are decision-vs-code drift, expected until S45-S52 land, and are not rewritten in this architecture-only step.

## Recommendations

- Execute S45 first to establish the closed public producer vocabulary; every later semantic-map and application producer must import it.
- Execute S46-S50 as atomic canonical-home migrations that delete the replaced header fallbacks, presenter alias, scalar row surrogates, selectors, and plaintext paths in the same commits.
- Make S51 the fail-closed applicability boundary and S52 the exact-anchor census. A field that is applicable but lacks one canonical producer must remain a hard failure, never filler or blank.
- Re-run curation after S52 to close the decision-vs-code drift finding and confirm no sibling capability or redeclaration survived.
