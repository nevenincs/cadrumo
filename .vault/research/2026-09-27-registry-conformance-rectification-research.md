---
tags:
  - '#research'
  - '#registry-conformance-rectification'
date: '2026-09-27'
modified: '2026-09-27'
body_schema: 'body-v2'
body_hash: 'sha256:24bb0941e47aef8313f29bbc21a26289b0aa270d7aab1d8c666087500283b9f3'
related:
  - "[[2026-09-27-registry-conformance-rectification-plan]]"
---

# `registry-conformance-rectification` research: `2022 baseline per-year grounding`

Three accepted decisions bound tax year 2025 as the only filing-grade year for activity-asset amortization, asset claim projections and withholding recognition. The rectification brief directs a 2022 baseline keyed only by real yearly differences. This record gathers, per supported year, what the official sources state for those three surfaces. The picture: the amortization tables, thresholds and general methods are unchanged from 2022 to 2025; the free-depreciation incentives differ only by enactment year; the recognition provisions are unamended since before the floor; and every Modelo 193 record design prints the same pending-payment disclosure.

## Findings

### The amortization tables and thresholds are unchanged from 2022 to 2025

The LIS art. 12.1.a linear table and the RIRPF art. 30.1.a simplified table print the same rows in the Renta manual of every year from 2022 to 2025, checked row by row; the machinery row reads `Maquinaria 12 por 100 18 años` in each edition (`src/cadrumo/_data/manual_corpus_text/manuals/renta/2022/part1/source.pdf.corpus_text.json` through `.../2025/part1/...`). Intangibles with no reliable useful life (5%), goodwill (5%), low-value free depreciation (300 EUR per unit, 25.000 EUR per year), the constant-percentage factors (1,5, 2, 2,5 with 5- and 8-year thresholds, 11% floor), the used-asset multiplier, the reduced-size multipliers and the R&D building period are the same in the four editions. The reduced-size turnover threshold (10.000.000 EUR) is unchanged, but each manual names its own prior year. The simplified table's source is the Orden de 27 de marzo de 1998; no manual from 2022 to 2025 cites Orden HAC/1164/2005.

### Free depreciation for renewables and electric vehicles differs by enactment year

Renewable self-consumption free depreciation (LIS DA 17, added by art. 22 RDL 18/2022, in force 2022-10-20) admits installations entering service in 2023; the 2024 period follows from DA 17.1 letter b (art. 18 RDL 8/2023) and the 2025 period from art. 17 RDL 16/2025. The 2023, 2024 and 2025 manuals print "Libertad de amortización en inversiones que utilicen energía", and the 2022 manual does not. Entry into service must fall in the tax year, so each year's first and last admitted year equals that year. The availability boundary of 2022-10-19/20 is a transaction-date condition that carries unchanged.

Electric-vehicle and charging-point free depreciation is LIS DA 18, not DA 16 (the expired 2020-2021 regime). DA 18 starts 2023-01-01 (art. 69 Ley 31/2022) as accelerated depreciation at twice the maximum coefficient (art. 190 RDL 5/2023), and becomes free depreciation from 2024 (art. 4.1 RDL 4/2024). The 2024 and 2025 manuals print "Libertad de amortización en determinados vehículos"; the 2023 manual describes only the accelerated regime; the 2022 manual has neither. The accelerated 2023 regime is not in the method enum. Taxpayers who died before 2024-06-28 keep it in 2024.

### The withholding recognition provisions are unamended since before the floor

RIRPF art. 78.1 fixes the general trigger at payment or crediting and routes movable capital and IIC transfers to arts. 94 and 98; art. 94.1 recognizes movable-capital income at exigibility or earlier payment; art. 98 recognizes IIC transfers at formalization (`src/cadrumo/_data/corpus/normatives/html/rd-439-2007.html.extracted.md`). The consolidated text's amendment notes show art. 78 apartados 1 and 2 and art. 94 apartados 1 and 2 in their original 2007 redaction (only art. 78.3, by RD 1074/2017, and art. 94.3, by RD 1003/2014, were added) and no amendment of art. 98. RIS art. 65 carries no amendment note, but corporate recipients are refused by the recognition code, so it grounds nothing that runs.

### Every Modelo 193 record design prints the same pending-payment disclosure

Position 117 of the type-2 record is the pending field for keys A, B and D in every bundled design, from the 2019 edition to the 2025 one, with the same wording and the same `999 999 999` / `VALORES PENDIENTE DE ABONO` perceptor (`src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_193/files/*.extracted.md`, e.g. line 851 of the 2025 design and line 862 of the 2023 one). The Modelo 193 registry declares the field as `payee_pendiente_flag` from its 2022 edition (`src/cadrumo/_data/registry/aeat/modelos/193/revisions/2022/casillas/0001-declarations.toml:350`).

### Destination casillas keep their meaning in every supported edition

Modelo 100 casillas 0208 and 0227 carry the material and intangible amortization roles, and Modelo 130 casilla 02 the gastos role, in every edition selected for 2022 through 2026; Modelo 130 has one edition, `2019-y-siguientes`.

Not investigated: the 2026 status of LIS DA 17 under RDL 7/2026, which the catalogue note on DA 17 mentions, because no 2026 Modelo 100 edition is authored.

## Sources

- `src/cadrumo/_data/manual_corpus_text/manuals/renta/2022/part1/source.pdf.corpus_text.json`
- `src/cadrumo/_data/manual_corpus_text/manuals/renta/2023/part1/source.pdf.corpus_text.json`
- `src/cadrumo/_data/manual_corpus_text/manuals/renta/2024/part1/source.pdf.corpus_text.json`
- `src/cadrumo/_data/manual_corpus_text/manuals/renta/2025/part1/source.pdf.corpus_text.json`
- `src/cadrumo/_data/corpus/normatives/html/rd-439-2007.html.extracted.md`
- `src/cadrumo/_data/corpus/normatives/html/rd-634-2015.html.extracted.md`
- `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_193/files/01-193-orden-eha-3377-2011-actualizado-por-orden-hac-1430-2025-de-3-de-diciembre-357-kb-pdf.pdf.extracted.md:851`
- `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_193/files/04-193-diseno-de-registro-modelo-193-2023-866-kb-pdf.pdf.extracted.md:862`
- `src/cadrumo/_data/registry/aeat/legal/is.toml` (LIS DA 17 and DA 18 entries)
- https://www.boe.es/buscar/act.php?id=BOE-A-2007-6820
- https://www.boe.es/buscar/act.php?id=BOE-A-2014-12328
