---
tags:
  - '#plan'
  - '#iva-service-localisation'
date: '2026-08-12'
modified: '2026-08-12'
body_hash: 'sha256:09594257d2f19c3e313053488e659018d60577fdceea2fb7edb2a18bce4bdc44'
tier: L1
related:
  - '[[2026-08-12-iva-service-localisation-adr]]'
  - '[[2026-08-12-iva-service-localisation-reference]]'
---

# `iva-service-localisation` plan

## Description

## Steps

- [x] `S01` - Make the statutory-citation gate anchor-aware: a corpus_ref may name an anchor, and when it does the gate resolves that single unit from the extraction sidecar and reads its rubric and text rather than the whole file. Land the mutation proof in the same change - a row pointed at an anchor whose article names the other limb must red - because an anchor-aware reader that silently fell back to the whole file would pass every existing row and prove nothing. Do NOT fetch per-article files for arts 68-70, because the consolidated text is already bundled and the module's own prose warns against duplicating it; `src/cadrumo/domain/iva/_supply_nature.py, src/cadrumo/domain/iva/tests/test_supply_nature.py`.
- [x] `S02` - Add citation rows for LIVA arts 68 (goods), 69 and 70 (services), each pinned to its anchor in the consolidated law. Verify through the gate rather than by assertion: each row's claim must survive reading the article's own rubric. The disconfirming observation: if any category turns out to cite art 68 alongside 69 or 70 the join now reports CONTRADICTED for it, which would be a real finding about the component table rather than a reason to drop a row - stop and report it; `src/cadrumo/domain/iva/_supply_nature.py, src/cadrumo/domain/iva/tests/test_supply_nature.py`.
- [x] `S03` - Prove the two SERVICE categories now derive SERVICES through supply_nature_implied_by_category, and that the goods categories still derive GOODS. Assert the property per category from the shipped component table, never a total count of deriving categories - a count encodes this moment and goes stale the next time an article is bundled. Correct the module docstring that states the two SERVICE members derive nothing and names the gap as the citation table's; `src/cadrumo/domain/iva/_supply_nature.py, src/cadrumo/domain/iva/tests/test_supply_nature.py`.
- [x] `S04` - Fork the outbound services classification on the customer's condition per LIVA art 69: the B2B limb keeps not-subject under 69.Uno.1 for a recipient that is an empresario o profesional established outside the Comunidad, and the B2C limb resolves to a SUBJECT domestic outcome under 69.Uno.2 because the supplier is established in the TAI. UNKNOWN and PUBLIC_ADMINISTRATION reach neither limb. Declare the customer tax status on the row's consumed party facts so the operator is asked for it on this branch and only on it; `src/cadrumo/domain/iva/_classification.py`.
- [x] `S05` - Gate both under-declarations the fork closes, each as a mutation proof that reds against the pre-change row: a B2C service to a third-country consumer, and a B2C service to a consumer in Canarias, Ceuta or Melilla, which art 69.Dos expressly carves back out of its own exception by naming those territories. Keep a positive control on the B2B limb through the same territories so the case cannot pass by refusing everything, and assert the outcomes rather than any localised message text; `src/cadrumo/domain/iva/tests/`.
- [ ] `S06` - Sweep the consumers of the outbound services row for the widened outcome: any caller, projection, advisory or Modelo 303 routing that assumed an ES-to-outside-the-Comunidad service is always not-subject. Run the full IVA and ledger suites sequentially and triage owner failures from peer churn before closing. Record the art 69.Dos list as a named carry-forward in the exec record - its population is over-taxed by default, which is the direction nothing in the apparatus watches; `src/cadrumo/domain/iva/, src/cadrumo/application/`.

## Parallelization

## Verification
