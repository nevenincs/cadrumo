---
tags:
  - '#research'
  - '#modelo-232-related-party-operations'
date: '2026-11-12'
modified: '2026-11-12'
body_schema: 'body-v2'
body_hash: 'sha256:d96e183eaa0546198e0d0851a3b71bbe069037b5946fa5befdd90d62856ece07'
related: []
---
# `modelo-232-related-party-operations` research: `Modelo 232 filing grounds and applicability`

## Findings

- **Orden HFP/816/2017 art. 2 sets five grounds for filing Modelo 232, and none of them is "being a company".**
  - 2.1.a: operations with the same related person or entity whose combined consideration exceeds 250.000 euros at market value.
  - 2.1.b: specific operations whose combined amount of each type exceeds 100.000 euros.
  - 2.2: exclusions, including operations within one tax consolidation group, AIE and UTE operations, and public offers.
  - 2.3: operations of the same type and valuation method above 50% of turnover, whatever the amount per person.
  - 2.4: the LIS art. 23 intangibles reduction on income from related persons.
  - 2.5: operations or securities in a tax haven, "independientemente de su importe".
  - Locator: `src/cadrumo/_data/corpus/normatives/html/orden-hfp-816-2017-art-2.html`, legal ref `orden-hfp-816-2017:art-2`.
- **The order applies from the first tax periods of 2016.** Final provision two: "será de aplicación para las declaraciones correspondientes a los períodos impositivos iniciados a partir del 1 de enero de 2016". Locator: `src/cadrumo/_data/corpus/normatives/html/orden-hfp-816-2017.html`.
- **RIS art. 13.3.d and 13.4 frame the same 250.000-euro per-person bound and route the information to the declaration.** Locator: `src/cadrumo/_data/corpus/normatives/html/rd-634-2015-art-13.html`, legal ref `rd-634-2015:art-13`.
- **The AEAT instrucciones print the three thresholds as a decision table.** The lines read "> 250.000 € de operaciones por entidad vinculada", "> 100.000 € en operaciones específicas del mismo tipo" and "> 50 % de la cifra de negocio". Locator: `src/cadrumo/_data/corpus/aeat_official/instructions/modelo_232/files/Instrucciones_Modelo_232.pdf.extracted.md:16-23`, source `aeat-modelo-232-human-form-instructions`.
- **Before the 2026-11-12 change the 232 rule tested only the entity type.** Locator: `src/cadrumo/_data/registry/aeat/modelos/232/revisions/2016-2017/applicability/0001-declarations.toml:1-6`, `applicable_entity_types = ["legal_entity"]`. The 2018 edition declared one parameter of 100.000 euros, described as a related-party threshold and cited only to the procedure page; nothing read it.
- **The applicability engine already expresses an undecided obligation and three-state payer facts.**
  - An exclusion with `outcome = "incomplete"` gives an INCOMPLETE verdict with its own reason (`src/cadrumo/domain/calculations/registry/applicability_models.py:197`).
  - The calendar gives rows only to APPLICABLE verdicts.
  - Dated payer facts in fact 0139 may be declared or derived from stored records (`src/cadrumo/_data/registry/aeat/facts/0139-modelo-payer-applicability-facts.toml:33-40`).

## Sources

- BOE-A-2017-10042, Orden HFP/816/2017, arts. 1-2 and final provision two (bundled HTML above).
- BOE-A-2015-7771, Real Decreto 634/2015 (RIS), art. 13 (bundled HTML above).
- AEAT, Instrucciones Modelo 232 (bundled PDF extract above).
