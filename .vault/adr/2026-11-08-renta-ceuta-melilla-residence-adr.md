---
tags:
  - '#adr'
  - '#renta-ceuta-melilla-residence'
date: '2026-11-08'
modified: '2026-11-08'
body_schema: 'body-v2'
body_hash: 'sha256:909c4a328995c30e62f2f66b59c98a2784945b88d8be73136277391cf1b8ad8d'
related:
  - "[[2026-07-04-renta-region-deductibility-adr]]"
  - "[[2026-07-04-autonomic-deduccion-framework-adr]]"
  - '[[2026-11-08-renta-ceuta-melilla-residence-research]]'
---

# `renta-ceuta-melilla-residence` adr: `Ceuta and Melilla as recorded IRPF residences` | (**status:** `accepted`)

Accepted 2026-11-08 by the coordinator session on the evidence cited below (operator unavailable; coordinator authority for this session's defect queue).

## Problem Statement

The profile residence axis `tax_residence.ccaa` offers only the 15 ordinary common-regime comunidades. The fact `renta-ccaa-tax-residence-catalogue` lists Ceuta and Melilla under `territory_exclusion` with classification `autonomous_city_unsupported`. A resident of either ciudad autónoma therefore cannot record residence (APP-QA defect D03, 2026-11-07). If such a token reached Renta, every consumer would refuse or hard-error:

- the escala and mínimo autonómico dispatch tables;
- the `ZCCAD` export converter;
- work creation (`parse_tax_region`);
- the profile schema write;
- the deadline profile build.

Ceuta and Melilla are territorio común for IRPF, file Modelo 100, and receive explicit statutory treatment, so they must be calculated rather than refused.

## Considerations

- The record design codes Ceuta and Melilla as `tipo_CCAA` 18 and 19 in every edition; see `2026-11-08-renta-ceuta-melilla-residence-research`.
- LIRPF DA 32 assigns the art. 65 scale, which is constant since 2015 across the whole envelope; same research.
- The autonomic mínimo falls back to the state art. 57 amounts, and the cities have no autonomic deducciones; same research.
- Art. 68.4 is already modelled on casillas 0560/0561.

## Considered options

- **Record and calculate (chosen).** Add both cities as catalogue members with their own codes, the art. 65 scale and the state mínimo. This matches the law and the design, and every consumer already dispatches through the catalogue.
- **Record but refuse calculation.** This keeps the profile honest but leaves a statutorily settled case unsupported, against the rule that settled tax behaviour is enforced. Rejected.
- **Keep the exclusion.** The resident cannot even state residence. Rejected; it is the defect.

## Constraints

- The CCAA token now means "common-regime IRPF residence territory". No current consumer distinguishes a comunidad from a ciudad autónoma, so the catalogue carries no territory-kind field. A future consumer that needs the distinction adds it to the catalogue fact; Python holds no token lists.
- The art. 65 parameter is authored once at the earliest Modelo 100 edition, and later editions inherit it (rule 14). Years come only from the registry envelope.
- Art. 68.4 eligibility stays operator-entered on casilla 0727. Tying it to residence (1.º against 2.º) is a separate change. The IVA/IPSI `ceuta_melilla` territorial scope is unaffected.
- This ruling amends the CCAA-scope statements in `2026-07-04-renta-region-deductibility-adr` and `2026-07-04-autonomic-deduccion-framework-adr`, which carried the exclusion forward from a retired `ccaa-in-profile` record.

## Implementation

We will make `ceuta` and `melilla` members of `renta-ccaa-tax-residence-catalogue`, ordered after `murcia`, and remove them from `territory_exclusion`. Alongside that:

- map them to `tipo_CCAA` 18 and 19 in `modelo-100-profile-form-codes`;
- add one parameter, `renta-escala-autonomica-ceuta-melilla-base-general`, holding the art. 65 table and citing art. 65 and DA 32;
- point every escala dispatch table at that parameter, and every mínimo-autonómico dispatch table at the state art. 57 parameters;
- add both tokens to the profile schema enum, with labels authored through `dev.locales` in all four locales.

Tests use the hand computation of the art. 65 scale (base 70.000 gives 8.950,75 + 10.000 × 22,5 % = 11.200,75) across every envelope year. The registry authority must be republished.

## Rationale

The official design and the statute both settle the treatment, so no operator choice remains. Catalogue membership routes every consumer through its existing dispatch instead of a new branch.

## Consequences

Residents of Ceuta and Melilla can record residence, export the correct `tipo_CCAA` and receive the statutory scale. Tests that pinned 15 members are rederived from the catalogue. Reconsider this ruling if a future law gives the cities their own escala or mínimo, or if the record design changes codes 18/19.
