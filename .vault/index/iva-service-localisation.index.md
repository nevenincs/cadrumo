---
generated: true
tags:
  - '#index'
  - '#iva-service-localisation'
date: '2026-08-16'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:fe13fc08cf9aae87a15eb3c1f60cc2abd2ef3bf403a65281281281cfb9c647b2'
related:
  - '[[2026-08-12-iva-service-localisation-adr]]'
  - '[[2026-08-12-iva-service-localisation-plan]]'
  - '[[2026-08-12-iva-service-localisation-reference]]'
---

# `iva-service-localisation` feature index

Auto-generated index of all documents tagged with `#iva-service-localisation`.

## Documents

### adr

- `2026-08-12-iva-service-localisation-adr` - `iva-service-localisation` adr: `the services limb is located by the recipient's condition, and grounded at the anchor` | (**status:** `accepted`)

### exec

- `2026-08-12-iva-service-localisation-S01` - Make the statutory-citation gate anchor-aware: a corpus_ref may name an anchor, and when it does the gate resolves that single unit from the extraction sidecar and reads its rubric and text rather than the whole file. Land the mutation proof in the same change - a row pointed at an anchor whose article names the other limb must red - because an anchor-aware reader that silently fell back to the whole file would pass every existing row and prove nothing. Do NOT fetch per-article files for arts 68-70, because the consolidated text is already bundled and the module's own prose warns against duplicating it
- `2026-08-12-iva-service-localisation-S02` - Add citation rows for LIVA arts 68 (goods), 69 and 70 (services), each pinned to its anchor in the consolidated law. Verify through the gate rather than by assertion: each row's claim must survive reading the article's own rubric. The disconfirming observation: if any category turns out to cite art 68 alongside 69 or 70 the join now reports CONTRADICTED for it, which would be a real finding about the component table rather than a reason to drop a row - stop and report it
- `2026-08-12-iva-service-localisation-S03` - Prove the two SERVICE categories now derive SERVICES through supply_nature_implied_by_category, and that the goods categories still derive GOODS. Assert the property per category from the shipped component table, never a total count of deriving categories - a count encodes this moment and goes stale the next time an article is bundled. Correct the module docstring that states the two SERVICE members derive nothing and names the gap as the citation table's
- `2026-08-12-iva-service-localisation-S04` - Fork the outbound services classification on the customer's condition per LIVA art 69: the B2B limb keeps not-subject under 69.Uno.1 for a recipient that is an empresario o profesional established outside the Comunidad, and the B2C limb resolves to a SUBJECT domestic outcome under 69.Uno.2 because the supplier is established in the TAI. UNKNOWN and PUBLIC_ADMINISTRATION reach neither limb. Declare the customer tax status on the row's consumed party facts so the operator is asked for it on this branch and only on it
- `2026-08-12-iva-service-localisation-S05` - Gate both under-declarations the fork closes, each as a mutation proof that reds against the pre-change row: a B2C service to a third-country consumer, and a B2C service to a consumer in Canarias, Ceuta or Melilla, which art 69.Dos expressly carves back out of its own exception by naming those territories. Keep a positive control on the B2B limb through the same territories so the case cannot pass by refusing everything, and assert the outcomes rather than any localised message text
- `2026-08-12-iva-service-localisation-S06` - Sweep the consumers of the outbound services row for the widened outcome: any caller, projection, advisory or Modelo 303 routing that assumed an ES-to-outside-the-Comunidad service is always not-subject. Run the full IVA and ledger suites sequentially and triage owner failures from peer churn before closing. Record the art 69.Dos list as a named carry-forward in the exec record - its population is over-taxed by default, which is the direction nothing in the apparatus watches

### plan

- `2026-08-12-iva-service-localisation-plan` - `iva-service-localisation` plan

### reference

- `2026-08-12-iva-service-localisation-reference` - `iva-service-localisation` reference: `what the services limb reads today, and where it stops`
