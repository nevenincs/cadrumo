---
tags:
  - '#plan'
  - '#modelo-347-fileability'
date: '2026-10-03'
tier: L2
related:
  - '[[2026-10-03-modelo-347-fileability-adr]]'
modified: '2026-10-03'
body_schema: body-v2
body_hash: 'sha256:41a8678fdbd77fb222a0c1817dcb070d85a7527eaa6543d4046ffb825420f6d2'
---

# `modelo-347-fileability` plan

## Description

Approved 2026-10-03. Basis: the operator instructed that Modelo 347 must be fileable from the data Cadrumo
holds, to assign Opus agents for discovery and implementation, to fix regressions and implement gaps
automatically, and to allow no reimplementation, duplicate code or drift.

Make Modelo 347 fileable for 2025 onwards from ledger invoices, profile facts and census data, keeping
2014-2024 advisory until its diseño is captured. Decision coverage: `2026-10-03-modelo-347-fileability-adr`
governs every Phase (type 1 totals via export fields, per-direction threshold buckets as dated registry data,
the shared applicability exclusion, art. 33.2 exclusions on the category catalogue, the goods import and
export refinement of the counterparty-residency ruling). Evidence: `2026-10-03-modelo-347-fileability-audit`.
Every Step extends the canonical mechanism its audit finding names and deletes the duplicate it replaces;
ambiguous law stays advisory.

## Steps

### Phase `P01` - Grounding and threshold model

Ground the 347 obligation in the BOE texts and compute the 3.005,06 floor per counterparty and direction bucket through the one existing threshold leaf.

- [x] `P01.S01` - Point rd-1065-2007:art-31 at the BOE consolidated article, add rd-1065-2007:art-32 and rd-1624-1992:art-62 legal entities with verbatim required text, cite art. 33 for the threshold fact users, and retire the stand-in split article; `src/cadrumo/_data/registry/aeat/legal/operaciones-terceros.toml, src/cadrumo/_data/registry/aeat/legal/iva-flow.toml, src/cadrumo/domain/calculations/registry/m347_threshold.py`.
- [ ] `P01.S02` - Compute the 347 floor per counterparty and direction bucket from a dated registry fact mapping claves to buckets, through one declarable-set function in m347_threshold.py delegating to _declarable_party_ids, used by both the row family and the declarante summary; `src/cadrumo/_data/registry/aeat/facts/, src/cadrumo/domain/calculations/registry/m347_threshold.py, src/cadrumo/domain/calculations/registry/invoice_bindings.py, src/cadrumo/domain/calculations/registry/_invoice_row_materialization.py`.

### Phase `P02` - Live declarado rows and export

Produce the type 2 rows on the live path through the existing row builder and render a byte-correct fichero: signed amounts, type 1 totals, per-row flags, inmueble and non-resident records.

- [x] `P02.S03` - Return the 347 type 2 rows on the live path through resolve_invoice_binding_row_values and the existing row_binding_values channel, route operator rows through the same channel, delete Modelo347ContraparteRow and validate_m347_threshold, and confine the 349 re-summing loop; `src/cadrumo/application/invoices/source_resolver.py, src/cadrumo/domain/modelos/row_models.py, src/cadrumo/application/modelo/calculate_input.py, src/cadrumo/application/modelo/_calculation_modelo_adjustments.py`.
- [ ] `P02.S04` - Render every 347 signed amount through the generalised signed_monetary_composite grammar, folding the m180-only composite branch into it, and regenerate both export editions; `dev/registry/pipeline/render_profile_rules.py, dev/registry/pipeline/render_profile_authority.py, dev/registry/render_profiles/modelo_347/, src/cadrumo/_data/registry/aeat/modelos/347/revisions/*/export/`.
- [ ] `P02.S05` - Feed type 1 positions 136-144 and 145-160 from export fields naming the existing summary bindings, delete the two manual casillas and move their consumers to the bindings; `dev/registry/mappings/modelo_347/, src/cadrumo/_data/registry/aeat/modelos/347/revisions/`.
- [ ] `P02.S06` - Extend the contraparte row builder key with typed per-row facts for metalico, criterio de caja, inversion del sujeto pasivo, seguro, arrendamiento and transmisiones, and render casilla fields per row; `src/cadrumo/domain/calculations/registry/_invoice_row_materialization.py, src/cadrumo/application/invoices/source_resolver.py, src/cadrumo/application/filing/`.
- [ ] `P02.S07` - Make the inmueble record repeat from the referencia catastral family and project non-resident and EU-operator rows as the diseno requires; `dev/registry/mappings/modelo_347/, src/cadrumo/domain/calculations/registry/detail_record_bindings.py, src/cadrumo/domain/calculations/registry/_invoice_row_materialization.py`.

### Phase `P03` - Operation scoping and exclusions

Apply art. 32.b operation scoping and the art. 33.2 exclusions at the single existing exclusion point via the category catalogue.

- [ ] `P03.S08` - Exclude art. 33.2 operations at the single exclusion point through IVA category catalogue exclusion keys: goods imports and exports, withheld received invoices, and the categorisable letters; `src/cadrumo/_data/registry/aeat/facts/0084-iva-category-component-catalogue.toml, src/cadrumo/domain/calculations/registry/iva_category_catalogue.py, src/cadrumo/application/invoices/source_resolver.py`.
- [ ] `P03.S09` - Scope 347 operations for estimacion objetiva filers per art. 32.b and resolve filer roles and regimes once per calculation context as of the filing period; `src/cadrumo/application/invoices/source_resolver.py, src/cadrumo/application/user_profile/projections.py`.

### Phase `P04` - Obligation, applicability and profile

Decide who must file from typed profile facts and the ledger per filing year, through the one shared applicability evaluator, and feed those facts from census data.

- [x] `P04.S10` - Add a typed exclusion list to applicability rules with its validator and evaluator step, and declare the 347 SII exclusion, the art. 31.1 activity gate and the clave C floor handling; `src/cadrumo/domain/calculations/registry/schema_revision_members.py, src/cadrumo/domain/calculations/registry/applicability.py, src/cadrumo/_data/registry/aeat/modelos/347/revisions/2011-2024/applicability/, src/cadrumo/_data/registry/aeat/facts/0139-modelo-payer-applicability-facts.toml`.
- [ ] `P04.S11` - Derive a per-year ledger 347 threshold signal from the resolver's own observations, read the profile answer per filing year, and keep any disagreement visible in applicability and the calendar; `src/cadrumo/application/overview/, src/cadrumo/entrypoints/overview_read_composition.py, src/cadrumo/domain/deadlines/`.
- [ ] `P04.S12` - Adopt SII, IVA regime, criterio de caja and estimation regime from census data, list the deciding facts in explain, and fix the threshold label and informal register in all locales; `src/cadrumo/application/user_profile/censo_sync.py, src/cadrumo/application/overview/explain.py, src/cadrumo/locales/`.

### Phase `P05` - Advisories and fileability acceptance

Surface the remaining ambiguities as advisories and prove fileability end to end on synthetic ledgers, with no new duplication.

- [ ] `P05.S13` - Surface advisories for ledger expenses without an invoice, received-invoice dating, the 2014-2024 edition grounding gap and tipo de soporte, and apply the weekend deadline shift without a holiday calendar; `src/cadrumo/application/invoices/source_resolver.py, src/cadrumo/_data/registry/aeat/modelos/347/revisions/2011-2024/revision.toml, src/cadrumo/domain/deadlines/festivos.py`.
- [ ] `P05.S14` - Prove 347 fileability end to end from synthetic ledgers to byte-checked ficheros for 2025, confirm no new duplication with audit-dead-weight, publish the authority and refresh affected goldens; `src/cadrumo/application/invoices/tests/, docs/_sequences/`.

## Parallelization

Registry source and the published authority are shared surfaces: S01, S02 (fact), S04, S05, S07, S08 (fact)
and S10 (rule data) change registry or generated export data and are validated with one candidate inspection
and one publication at Phase close; no Step publishes on its own. Ownership for concurrent work:
`m347_threshold.py` and `invoice_bindings.py` belong to S02; `source_resolver.py` belongs to S03, then S08, S09,
S06 and S13 in that order; the export generator, render profiles and 347 mappings belong to S04, S05 and S07 in
order; applicability and calendar code belong to S10 then S11; census, explain and locales belong to S12. P01
and P04 may run in parallel with each other; S03 may run alongside P01 once S02's function signature is
fixed. S06 waits until the concurrent renderer refactor in `src/cadrumo/application/filing/` is committed.
S14 runs last.

## Verification

- Each Step lands with focused tests through the real resolver and compiled registry, positive and negative
  cases, and a detector-teeth test for each new validator.
- `just audit-dead-weight` reports no new clone involving a touched file, compared with its run before the
  Step; the duplicates named in the ADR are deleted.
- Candidate inspection is publication-valid at each Phase close and the authority is published once per Phase.
- S14: a synthetic ledger with an above-threshold supplier, a 2,000 plus 2,000 customer, an 8,000 cash sale, a
  goods export, an SII filer and a módulos filer produces exactly the declarado records the law requires, and
  `export_draft` emits a fichero whose bytes match the 2025 diseño positions; CLI and TUI surface the same
  obligation verdict.
- Final integrated review passes against the ADR.
