---
tags:
  - '#exec'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:e3fd80156964ce914d81841b2f37d3964ada0986cab100c134f412a571ce7e26'
step_id: 'S44'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---
# Adjudicate and approve the one M303 semantic-home and fixed-slot row-projection architecture for annual-summary, per-activity prorrata, differentiated-deduction, simplified-activity/module, taxpayer/profile, filing-election, presenter, payment, and secure-account fields

## Scope

- `.vault/adr/2026-06-13-m303-form-vs-semantic-casilla-dual-keying-adr.md`
- `.vault/adr/2026-07-01-modelo-303-regimen-simplificado-adr.md`
- `.vault/research/2026-06-04-m303-form-vs-semantic-casilla-dual-keying-research.md`
- `.vault/audit/2026-08-10-aeat-export-fragment-generator-authority-s44-m303-semantic-home-architecture-audit.md`

## Description

- Used bounded VaultSpec RAG and full corpus reads to reconcile the accepted dual-key, accepted cross-period-prorrata, accepted casilla canonical-derivations, and proposed simplified-regime decisions with the official-form audit and live producer surfaces.
- Amended the accepted dual-key ADR in place as the single semantic-home and fixed-slot projection decision; no sibling architecture record was created.
- Removed the incorrect supersession relation and restored the simplified-regime ADR to a separate proposed, non-governing calculation-completeness record.
- Assigned the five activity rows as typed children of the sole encrypted `ProrrataRegister` and the two differentiated rows as direct projections of its existing sector definitions and entries, forbidding a second store, row carrier, selector family, or export recomputation.
- Allowed official annual-summary casillas with no upstream semantic twin to be canonical endpoints, avoiding shadow identifiers.
- Preserved `classify_official_boxes` as declaration-only authority and left producer vocabulary, value arrival, applicability, implementation, and five-epoch proof to S45-S52.
- Removed stale single-revision and open-question framing from the governing decision and retained grounding in its research/audit homes.

## Outcome

One accepted ADR now decides M303 semantic homes and exact official projections without displacing calculation, persistence, security, or classifier authorities. Every field family must resolve to one canonical typed owner, an official-only canonical endpoint, or an exact source/transport fact. Applicable missing authority refuses before target creation or byte emission.

The sole encrypted `ProrrataRegister` remains the activity and sector substrate. The simplified-regime record remains proposed and separate; casilla 48 remains manual until a later accepted completeness decision. S45-S52 remain the exclusive implementation and proof owners.

## Validation

- Hash-guarded VaultSpec body writes completed for both amended ADRs.
- Feature-scoped frontmatter, body-section, ADR-status, schema, and Markdown checks returned zero diagnostics.
- Independent ADR/curation review and the durable S44 audit provide the final acceptance verdict.

## Notes

The shared tree and index carried unrelated peer work. No broad fix, cache reset, or peer-document mutation was performed. S44 document commits and plan closure are isolated from the shared index and accepted only after exact-parent and preimage checks.
