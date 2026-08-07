---
tags:
  - '#audit'
  - '#invoice-canonical-structure'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:9f771071ff74cca2f2b1f5c3afeab79dbb575d129bc6406c4d3a3a8277dd457a'
related:
  - "[[2026-08-06-invoice-canonical-structure-adr]]"
  - "[[2026-08-06-invoice-canonical-structure-plan]]"
  - "[[2026-08-07-invoice-canonical-structure-close-honesty-review-audit]]"
---

# `invoice-canonical-structure` audit: `Decision-to-Step coverage: all 21 ADR decisions checked against the tree`

## Scope

## Findings

## Recommendations

## Context

The plan closed at 38/38 with no decision-to-step map, so `100%` meant every Step ran and nothing showed whether every decision was discharged. This is that map. Each decision was checked against the tree at HEAD rather than against the plan, because a Step can run and still leave its decision undelivered.

The headline: **every decision is discharged**, one by a better mechanism than the ADR specified, and the check surfaced one live defect that no Step owned.

## Discharged as decided

| Decision | Evidence at HEAD |
| --- | --- |
| D-A canonical aggregate, slim retired | The slim type returns nothing across source, dev and docs |
| D-B one CRUD surface | Seven verbs, no sub-apps |
| D-C coverage proven before deletion | Two proofs pinned to fixture-derived literals |
| D-D double-count closed by construction | One store feeds both informativas |
| D-E writer reaches the canonical fields | Class, series, rectifies and recargo are real parameters |
| D-F retencion NOT on the extraction draft | Zero references; the negative holds |
| D-G mixed rates fixed at the writer end | The writer takes a line set |
| D-H the importing module deleted, not routed | Gone, with its tests and stub |
| D-I M303 blind spots closed, M390 screened | Both screens generalised onto one binding table |
| D-J the line category field renamed | Now `spending_category_id` |
| D-K plausibility gate at the confirm boundary | The printed-total discrepancy, with its own suite |
| D-L override set mirrors the writer | Confirm carries recargo, class, series and rectifies |
| D-M recargo slot on the draft | Landed by the sibling campaign, per the agreed partition |
| D-N source jurisdiction named and scoped out | A documented scope-out; correctly no code |
| D-P observation source kind loses its default | The field is required, with a coercing validator |
| D-Q duplicate direction types retired | The slim direction enum is gone; the core taxonomy is the one home |
| D-R capability conservation is governing law | Held: every retired test was repointed or its capability re-proven |
| D-S custody roundtrip strengthened | The canonical namespace is structured-custody and carries a store case |
| D-T writer parity before the fold | The four regime axes are writable, so a rectificativa is representable |
| D-U decomposition keeps functioning | Its suite is green against the folded population |

## Discharged by a better mechanism than the ADR specified

**D-O.** The decision required three fields to migrate onto the canonical aggregate before the slim store was deleted, and named `eu_iva_id` a **hard precondition** because the slim resolver preferred it as the declared Modelo 349 party id and derived the country prefix from it, including the Greek `EL` to `GR` mapping.

`created_at` and `updated_at` did migrate. **`eu_iva_id` did not, and does not exist on the canonical model.** On the ADR's own terms that reads as an unmet hard precondition.

It is not one, and the campaign's own test argues why: the canonical model couples `counterparty_country` to `counterparty_tax_id`, so a non-Spanish country forces the tax id to BE that country's NIF-IVA. There is only ever one party identity on the record, so there is nothing for a second field to disagree with. Adding `eu_iva_id` would install a SECOND party-identity authority on exactly the axis where disagreement is a mis-declared intra-community operator.

The Greek case was measured rather than assumed, since it is the one where the VAT prefix and the ISO code genuinely differ:

    country GR + EL123456789  -> accepted
    country GR + GR123456789  -> refused: expected EL + 9 digits
    country DE + DE345678901  -> accepted

So the mapping survives, in the core identity layer, and the wrong prefix is refused with an instructive message naming the expected form. The capability is conserved and the mechanism is stronger than the one D-O specified.

What is missing is the record of that. D-O still reads as a hard precondition, and a reader checking it against the tree finds an absent field and no explanation. **The ADR needs an amendment saying the precondition was discharged by the coupling rather than by the migration.** That is the one piece of paperwork this map leaves open.

## What the map found that no Step owned

Checking D-L led into the confirm boundary, where `counterparty_country` defaulted to `"ES"` on both the application function and its CLI verb -- while the option's own help string read "Required: it routes both informativas, so it is never assumed".

No Step covered it. The collapse required the country on `invoice add`, and the note behind that Step said explicitly that converting a derive-or-raise into a silent assumption was the hazard. Confirm was simply not swept with it, which left the one path that mints an invoice from a PARSED document as the one still guessing -- and the extraction draft carries no country field, so nothing downstream could correct the guess.

It failed loudly rather than mis-declaring, because the same country-to-tax-id coupling that makes `eu_iva_id` unnecessary refuses a German VAT id stamped `ES`. So the exposure was a confusing NIF error on a correct document, not a silent Modelo 347 or 349 mis-declaration. Fixed: both defaults removed, and the eighteen tests that were riding the default now state the country explicitly.

That is the argument for building this map. The defect sat between a Step that fixed one verb and a decision that governed another, which is exactly where step-by-step verification does not look.

## Mutation results, and the duplication they exposed

The close review recorded that zero-capability-loss was verified but not proven: the repointed tests were green, which shows the canonical path gives the right answer, not that a test would redden if it stopped. Two capabilities were mutation-tested to close that.

**The country-to-tax-id coupling — guarded.** Disabling the non-Spanish branch of the invoice model's validation reddens `test_canonical_invoice_refuses_the_tax_id_country_mismatch_slim_permits`. That matters because D-O's amendment rests entirely on this coupling: it is the reason `eu_iva_id` is unnecessary rather than missing. The mechanism the amendment cites is genuinely held by a test.

The declarable-coverage proofs stayed green under that mutation, correctly — they use matching country and tax-id pairs, so the coupling is not on their path. They guard a different property.

**The Modelo 347 declaration floor — NOT guarded, and the reason was a duplication.** Flipping the counterpart aggregation's comparison from `>` to `>=` left the invoice resolver's Modelo 347 test green. The earlier claim that this test was sharp because its control invoice sits exactly ON the floor was wrong: the control is placed correctly, but the test exercises a DIFFERENT copy of the comparison.

The threshold was written out four times in production: byte-identical lines in the counterpart and invoice binding families, again in the aggregation preview, and inverted in the row-model validator. Two of those are sibling modules in the same package.

The two binding families now share one predicate in a leaf module — a leaf because `_counterpart_bindings` already imports from `_invoice_bindings`, so either family owning it would make the dependency circular, and because neither family owns a regulation. Each keeps its own summation; only the comparison is shared.

Re-running the same mutation against the single home now reddens the invoice test: the counterparty sitting exactly on the floor is counted and the declarante count goes from 1 to 2. The capability moved from unguarded to guarded, and the proof is the mutation, not the green run.

**Left for adjudication, not swept.** The aggregation preview and the row-model validator still carry their own copies. They cite art. 33.1 where the bindings cite art. 31, and one is an inverse check, so whether they are the same rule or two related rules is a legal-grounding question rather than a refactor. Merging them on shape alone would be exactly the constraint-shape mistake the substitutability pre-filter exists to prevent.

The general lesson is the one this map was built to test: a duplicated rule reports as covered because each copy has its own green test. Only a mutation asks whether the test is watching the code that runs.
