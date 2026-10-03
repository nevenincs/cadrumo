---
tags:
  - '#adr'
  - '#modelo-347-fileability'
date: '2026-10-03'
modified: '2026-10-03'
body_schema: 'body-v2'
body_hash: 'sha256:7a79183a2108acdfb1ecc4a3415c1b136f56be924860dd6a2192406853a1bea4'
related:
  - "[[2026-10-03-modelo-347-fileability-audit]]"
  - "[[2026-08-27-tui-architecture-modelo-347-counterparty-residency-scope-adr]]"
---

# `modelo-347-fileability` adr: `Modelo 347 fileability` | (**status:** `accepted`)

## Problem Statement

Modelo 347 must be fileable from the ledger and profile data Cadrumo holds. The audit
`2026-10-03-modelo-347-fileability-audit` shows it is not: the live path produces no declarado rows, the export
refuses the signed amounts, the threshold over-declares, art. 32 exemptions and art. 33.2 exclusions are
missing, and the obligation rests on an undated boolean never compared with the ledger. Several repairs change
registry schema or shared mechanisms, so the choices are fixed here before implementation.

## Considerations

- RGAT art. 33.1: "se computarán de forma separada las entregas y las adquisiciones de bienes y servicios".
- RGAT art. 32.e and RIVA art. 62.6: SII filers are not obliged; art. 32.b scopes operations for módulos filers.
- RGAT art. 33.2.g: "Las importaciones y exportaciones de mercancías" are not declared.
- 347 is genuinely informative: `validate_informative_class_invariant` and the class/domain coherence gate must hold.
- Operator directive: no reimplementation, no duplicate code, no drift; extend canonical mechanisms only.

## Considered options

- Type 1 totals: reclassify 347 (refused by the coherence gate); relax the informative invariant (affects 17
  modelos); or point the type 1 export fields at the existing summary bindings (supported by
  `BindingConsumerKind.EXPORT_FIELD`, precedent 232).
- Threshold: hard-code clave groups in Python; or a dated registry mapping from clave to threshold bucket
  resolved by the existing `m347_threshold.py` leaf.
- Art. 32 exemptions: a 347-specific branch in the calendar; or a typed exclusion on the shared
  `ApplicabilityRuleDefinition`, evaluated by the one `derive_modelo_applicability` every surface uses.
- Art. 33.2 exclusions: ad-hoc checks in the resolver; or exclusion keys on the existing IVA category catalogue
  (fact `0084`), applied at the single exclusion point that already removes 349 operations.

## Constraints

- One row builder (`_build_contraparte_clave_rows`), one threshold comparison (`_declarable_party_ids`), one
  applicability evaluator, one renderer, one signed-composite render rule; duplicates named in the audit are
  deleted in the change that replaces them (`validate_m347_threshold`'s comparison, `Modelo347ContraparteRow`,
  the 349 re-summing loop where it duplicates the generic rows, the m180-only composite branch).
- Refines `2026-08-27-tui-architecture-modelo-347-counterparty-residency-scope-adr`: its ruling that
  non-resident counterparties are declarable stands; goods imports and exports are excluded under art. 33.2.g
  regardless of residency, and services with non-residents remain declarable.
- Ambiguous law stays advisory, never guessed: clave D bucket separation, clave E floor for 2014-2024, the
  withheld party's side of art. 33.2.i, partial-year SII membership, negative net rows, and the 2014-2024
  edition until its diseño is captured.

## Implementation

We will make Modelo 347 fileable by extending existing mechanisms only:

- Wire the live resolver's `row_binding_values` through `resolve_invoice_binding_row_values`; route operator
  rows through the same channel and delete `Modelo347ContraparteRow`.
- Compute the threshold per (counterparty, bucket) from a dated registry fact mapping claves to buckets
  (entregas B+F, adquisiciones A+G, C with the 300,51 floor, D separate, E without floor from 2025), resolved in
  `m347_threshold.py`; every caller delegates to it.
- Render every 347 signed amount through the generalised `signed_monetary_composite` grammar.
- Feed type 1 pos. 136-144 and 145-160 from export fields naming the existing summary bindings; delete the two
  manual casillas and move their consumers to the bindings.
- Add a typed exclusion list to `ApplicabilityRuleDefinition` with its validator and evaluator step; declare the
  347 SII exclusion with art. 32 and RIVA art. 62.6 grounding; add the art. 31.1 activity gate; derive a per-year
  ledger threshold signal from the resolver's own observations and compare it with the profile answer, keeping
  disagreements visible.
- Apply art. 32.b operation scoping and the art. 33.2 exclusions (g, i for withholding, and the categorisable
  letters) at the existing single exclusion point via the category catalogue.
- Extend the row builder key with the per-row flags (metálico, criterio de caja, inversión del sujeto pasivo,
  seguro, arrendamiento, transmisiones) from typed observation facts; make the inmueble record repeat from the
  referencia catastral family; project non-resident rows per the design.
- Correct the legal registry (art. 31 to the BOE text, new art. 32 and RIVA art. 62 entities).

## Rationale

Each option chosen keeps one canonical mechanism per concern and puts legal variation in typed registry data,
which the architecture and calculation-grounding rules require; the rejected options either break gates that
are correct for other modelos or add a second path that would drift.

## Consequences

347 becomes fileable for 2025 onwards and advisory for 2014-2024 until that diseño is captured. The applicability
exclusion and the category exclusion keys become available to every modelo. Tests asserting the combined
threshold and the declared goods export change. Reconsider if AEAT publishes guidance resolving the clave D or E
ambiguities, or a new diseño changes the record grammar. Accepted on the operator's authorization of
2026-10-03 to make Modelo 347 fileable, fix regressions and implement the gaps without duplicating capability.

**Amendment (2026-10-03).** Discovery during S07 showed the referencia catastral family serves the modelo
184 attribution members and modelo 180's tenant side, not a landlord's leased premises, so it cannot feed the
347 inmueble record (RGAT art. 34.1.d). We will emit no inmueble record when no lease data exists, advise
landlords with business-premises leases, and add a landlord-lease data family on issued rental invoices as a
follow-on Step that feeds the repeating inmueble record and type 1 positions 161 and 170.

**Amendment (2026-10-03, review).** Clave E carries no floor from 2014-01-01, when consolidated RGAT art. 33.3
("cualquiera que sea su importe", RD 828/2013 wording) took effect, not from 2025; filing years 2014-2024 keep an
advisory because the 2011 diseño still describes E as "superiores a 3.005,06".
