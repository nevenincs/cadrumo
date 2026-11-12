---
tags:
  - '#adr'
  - '#renta-rental-income-source'
date: '2026-11-12'
modified: '2026-11-12'
body_schema: 'body-v2'
body_hash: 'sha256:689196f4ce82c2366422f426db15e1a09daa7c6c2b0dd63528a284b44048d756'
related:
  - "[[2026-11-11-renta-rental-income-source-adr]]"
  - "[[2026-11-08-prior-carry-attestation-adr]]"
  - "[[2026-11-11-cross-period-filing-clean-state-out-of-envelope-attestation-adr]]"
  - "[[2026-08-14-registry-temporal-coverage-adr]]"
  - '[[2026-11-08-prior-carry-attestation-reference]]'
---

# `renta-rental-income-source` adr: `applied amortisation rate and anexo C.1 pending-expense carries` | (**status:** `proposed`)

Amends `2026-11-11-renta-rental-income-source-adr`. CADRUMO-PRIME accepted both rulings in substance at 21:22 on 2026-11-12 under the operator's delegation of ADR acceptance, pending this written text; the heading moves to `accepted` once PRIME approves the wording.

## Problem Statement

Two points of the rental decision are unsettled in code. The net chain applies the registry ceiling as the amortisation rate (`src/cadrumo/application/aggregation/renta_inmueble_net.py:243`, rate read at `src/cadrumo/application/aggregation/renta_inmueble_resolver.py:281`), although the 2025 manual states that the deductible amortisation is any rate between 1 and 3 per cent. And anexo C.1 (casillas 1211 to 1223) has no source: only 1224 is bound (`src/cadrumo/_data/registry/aeat/modelos/100/revisions/2022/bindings/0001-declarations.toml:1694-1697`), so a property with a pending excess from earlier years reaches export with 0103 and 0104 unsupported by their per-origin-year detail.

## Considerations

- Ceiling. RIRPF art. 14.2.a: amortisation is effective "cuando, en cada año, no excedan del resultado de aplicar el 3 por ciento sobre el mayor de" the acquisition cost or the cadastral value, excluding land (`src/cadrumo/_data/corpus/normatives/html/rd-439-2007-art-14.html.extracted.md:5`). The ceiling is already the parameter `renta-rental-amortizacion-rate` = 0.03, declared at the 2020 edition (`src/cadrumo/_data/registry/aeat/modelos/100/revisions/2020/parameters/0001-declarations.toml:1037`).
- Floor. The Manual práctico Renta 2025, Parte 1, p. 278, quoting STS 1502/2025 (ROJ STS 5416/2025), concludes that the taxpayer "podrá deducir en concepto de amortización la que resulte de aplicar un % entre el 1 por 100 (mínimo) y el 3 por 100 (máximo)" (`src/cadrumo/_data/corpus/manuals/renta/2025/part1/source.pdf.extracted.md:11868-11879`). No earlier bundled manual states the floor.
- The rate applied is a historical fact of each ejercicio: it fixes the amortisation later subtracted from the acquisition value on transmission (same lines, 11877-11879). It is not a treatment the application chooses.
- Pending excess. Interest and financing expenses plus repair and conservation may not exceed the gross income of each property; the excess is deductible in the four following years, applied before the year's own amounts, in 0104, with the year's own excess in 0108 (LIRPF art. 23.1.a.1º; RIRPF art. 13.a; manual 2025 pp. 274-275, `src/cadrumo/_data/corpus/manuals/renta/2025/part1/source.pdf.extracted.md:11654` and `:11706-11727`; manual 2024 p. 273, `src/cadrumo/_data/corpus/manuals/renta/2024/part1/source.pdf.extracted.md:11473`).
- The 2025 dictionary labels 0103 "Importe pendiente de deducir de los ejercicios 2021, 2022, 2023 y 2024 (Cumplimente el anexo C.1)" and nests C.1 per `Inmueble`: 1211 titular, 1212 referencia catastral, and per origin year "Pendiente de aplicación al principio del periodo", "Aplicado en esta declaración" and "Pendiente de aplicación en ejercicios futuros" (1213 to 1223), then 1224 for the ejercicio's own excess (`src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_100/files/01-100-diccionario-declaracion-individual-ejercicio-2025-actualizado-14-04-2026-416-kb-otros-fi.properties:211`, `:2177-2190`).
- The opening pending amount per origin year is a fact of earlier returns, so it falls under `2026-11-08-prior-carry-attestation-adr`, whose 2026-11-11 amendment already admits the row-grain family `renta_capital_inmobiliario_gastos_pendientes` keyed by property row identity; a stated amount uses `attest_prior_value` (`2026-11-11-cross-period-filing-clean-state-out-of-envelope-attestation-adr`).

## Considered options

- Keep a fixed 3 per cent. Rejected: it misstates the amortisation of a taxpayer who applied less, and with it the later gain.
- A per-property rate preference applied to every year. Rejected: the rate is a fact of each ejercicio, and a standing preference would overwrite history.
- Per-property, per-ejercicio stated rate within registry bounds, defaulting to the ceiling with visible provenance: chosen.
- Infer C.1 opening amounts from the 0108 of the current year or from ledger history. Rejected: the carry depends on earlier returns' own limits and applications; inference is forbidden for prior carries.
- Leave C.1 manual. Rejected: a non-zero 0103 or 0104 without its detail is an incomplete return the export would emit.

## Constraints

- No year literal in code, keys or ids; the floor is declared once, at the 2025 edition, and later editions inherit it (registry delta rule; `2026-08-14-registry-temporal-coverage-adr`).
- Projection never promotes grade. A rate below the ceiling for an ejercicio whose edition lacks the floor parameter is admitted at calculation grade only.
- A carry is never inferred or zeroed by default; absent, attested-absent and stated stay distinct.
- Supersedes, in `2026-11-11-renta-rental-income-source-adr`, the Considerations line "Amortisation rule. 3 per cent of the greater of…" as far as it fixes the rate at 3 per cent, the "3 per cent ceiling" judgement in its 2026-11-11 amendment, and its Consequences condition about the 1 to 3 per cent reading, which this record settles. The base, the land split, the cumulative cap and the worked-example oracle stand.

## Implementation

We will (1) source the amortisation rate from a stated per-property, per-ejercicio fact bounded by registry parameters, and (2) source anexo C.1 as a prior-carry family under the accepted attestation decision.

Applied amortisation rate:

- The `renta_inmueble` record gains an effective-dated fact "applied amortisation rate" keyed by ejercicio.
- The ceiling is `renta-rental-amortizacion-rate` (0.03). A new floor parameter of 0.01 is declared at the 2025 edition with a source citation to the manual text above.
- Unstated: the ceiling applies, the provenance shows that the default was used, and the grade does not change.
- Stated outside floor and ceiling: refused with a registered reason and the property door.
- Stated below the ceiling where the edition resolved for the ejercicio declares no floor: admitted at calculation grade only, with a structured finding naming the missing grounding; filing grade needs the floor in that edition.
- The net chain reads the stated rate at `renta_inmueble_net.py:243`; the cumulative cap (`:210-230`) uses the same rate.

Anexo C.1:

- Opening pending amount per origin year (1213, 1215, 1218, 1221) is read from the matching property occurrence of the previous Modelo 100 held in the profile, or stated through the attestation door of family `renta_capital_inmobiliario_gastos_pendientes` (absence or amount per origin year). Never inferred.
- Applied this year and pending for future years (1214, 1216, 1217, 1219, 1220, 1222, 1223) are computed by the net chain: oldest origin year first, before the year's own amounts, within the art. 23.1.a cap; an origin year past its fourth following year carries nothing forward. 0103 and 0104 are the sums. 1211 and 1212 come from the property record.
- When 0103 or 0104 is non-zero, or could be, and an origin year's opening amount is neither read nor stated, the occurrence raises a blocking structured finding that serves the attestation door.
- Hypotheses: field names, finding code, and whether the per-origin-year columns are one row-field family or several.

Sequencing: (2) runs as a P01 Step that ACCEPTANCE adds to the CALC-RENTA plan after S50 and S45 land; (1) waits for P02 of that plan. No separate plan.

## Rationale

The manual is the only bundled official text that grounds a rate below 3 per cent, so the floor is keyed where it first appears and earlier years stay at calculation grade, as projection requires. Treating the rate as a stated historical fact keeps the transmission gain consistent with what was deducted. C.1 opening amounts are carries of earlier returns, which the accepted attestation decision already governs; reusing it adds no new mechanism.

## Consequences

- A landlord who applied less than 3 per cent can file 2025 at filing grade and earlier years at calculation grade.
- Every returning landlord with a pending excess must hold the earlier return or state the per-origin-year carry before export; a first year in the app is blocked until stated.
- Reconsider if a later official text moves the floor, or if an edition before 2025 is found to state it, which would key the floor earlier.
