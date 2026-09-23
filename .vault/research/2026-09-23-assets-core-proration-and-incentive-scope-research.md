---
tags:
  - '#research'
  - '#assets-core'
date: '2026-09-23'
modified: '2026-09-23'
body_schema: 'body-v2'
body_hash: 'sha256:60a69033549880da572084c5b3a57e3e321719431d9c36858145c2d0197167b2'
related:
  - "[[2026-09-21-assets-core-lifecycle-contract-adr]]"
  - "[[2026-09-23-assets-core-amortization-method-set-adr]]"
---

# `assets-core` research: `Mid-year proration unit, LIS 103.5 reading and DA 17a/18a windows for IRPF 2025`

Three questions bore on filed amounts: whether a mid-year entry into service
prorates by days or by months, whether LIS art. 103.5 still admits reduced-size
acceleration of indefinite-life intangibles and goodwill after its cross
reference lost its target, and which entry-into-service years LIS DA 17a and
DA 18a admit for the 2025 IRPF period. Official sources settle the second and
third; the first has one binding statement of a unit.

## Findings

### Proration: one binding consulta states days; the manuals illustrate with months

- The law and regulation set only the start: RIS art. 3.3, "empezarán a
  amortizarse desde su puesta en condiciones de funcionamiento"
  (`src/cadrumo/_data/corpus/normatives/html/rd-634-2015.html.extracted.md:81`).
  The módulos order uses the same words
  (`src/cadrumo/_data/corpus/normatives/html/orden-hac-1347-2024.html.extracted.md:3577`).
- Binding consulta V1978-24 (17/09/2024, estimación objetiva) states the unit:
  "prorratear la cuota de amortización anual en función del número de días de
  funcionamiento en relación con el número de días de 2024".
  https://petete.tributos.hacienda.gob.es/consultas/?num_consulta=V1978-24
- Every AEAT manual example uses a first-of-month date and a month fraction,
  none stated as a rule: Renta 2025, x 1/12 = 720 for a 1 December entry
  (`src/cadrumo/_data/corpus/manuals/renta/2025/part1/source.pdf.extracted.md:19480-19504`),
  x 6/12 (`:18119`), x 5/12 (`:16022-16048`); Sociedades 2025, x 6/12
  (`src/cadrumo/_data/corpus/manuals/sociedades/2025/source.pdf.extracted.md:8342-8353`).
- For rented property the manual, Renta WEB and DGT 1929-98 prorate by days
  (`source.pdf.extracted.md:11916-11923`), and the same help page mixes month
  examples with day fields, so month fractions read as shorthand.
- No official source defines a partial month. At first-of-month dates the two
  units differ by at most about 0.5% of the annual charge, in both directions;
  a mid-month entry swings up to 1/12 depending on how the month counts.
- LIS art. 11.3.1º caps an ordinary tax charge at the charge booked, except for
  accelerated and free amortization (`ley-27-2014.html.extracted.md:110`); how
  that applies to IRPF taxpayers keeping only libros registro was not verified.

### LIS art. 103.5: 150% of the art. 12.2 one-twentieth

The consolidated text still cites the repealed art. 13.3
(`ley-27-2014.html.extracted.md:1849`). Binding consultas read it as 150% of
the art. 12.2 amount for corporate tax (V3057-19, V2568-22) and IRPF (V0539-20,
V0540-20, V2734-20, V2772-21, V2773-21, V1117-23, V2228-23, V0976-24), subject
to acquisition in a period meeting art. 101; V0976-24 adds "la norma establece
un porcentaje máximo, pero no mínimo". The Sociedades 2025 manual
(`source.pdf.extracted.md:25176-25190`), the Renta 2025 manual
(`source.pdf.extracted.md:19451-19460`) and AEAT Informa 139945 say the same.
Paragraph 5, unlike paragraph 1, does not require a new element.

### LIS DA 17a for IRPF 2025: 2025 entries only, on RDL 16/2025

RDL 7/2026 art. 37 reaches only periods not concluded at 22/03/2026, so not the
2025 IRPF period (https://www.boe.es/buscar/act.php?id=BOE-A-2026-6544). The AEAT
note of 01/04/2026 holds that RDL 16/2025 measures were in force at the 2025
accrual, and the Renta 2025 manual applies letter c) to 2025 on that basis
(`source.pdf.extracted.md:19004-19018`); the note's list does not name DA 17a,
which remains an advisory gap. Each year's letter covers only that year's
entries; unamortized earlier amounts do not carry over as free amortization.
https://sede.agenciatributaria.gob.es/Sede/todas-noticias/2026/abril/1/nota-sobre-efectos-ambito-tributario-febrero.html

### LIS DA 18a for IRPF 2025: 2024 and 2025, on RDL 4/2024

RDL 4/2024 art. 4.1 covers entry into service in periods starting in 2024 and
2025, and LIRPF DA 59a extends it to every IRPF method
(`src/cadrumo/_data/corpus/normatives/html/boe-a-2024-12944-rdl-4-2024-iva-alimentos.html.extracted.md:75-89`);
the manual says 2024 and 2025 (`source.pdf.extracted.md:19186-19230`).

### Options the ADRs must weigh

- Proration by days over the actual days of the year: the only stated unit,
  bias-free against the first-of-month examples. A month method would need an
  invented partial-month rule.
- LIS 103.5: admit 150% of the one-twentieth as the administration's settled
  reading, labelled as such, or keep refusing on the stale cross reference.

Not investigated: TEAC's DYCTEA database, ICAC consultas one by one, Renta WEB's
activity screens, and whether RDL 7/2026 was validated.

## Sources

- https://petete.tributos.hacienda.gob.es/consultas/?num_consulta=V1978-24 (and the 103.5 consultas named above, same query form)
- https://www.boe.es/buscar/doc.php?id=BOE-A-2013-2557 (ICAC resolution, norma 2a 3.2 and 3.6)
- https://www.boe.es/buscar/act.php?id=BOE-A-2026-6544 (RDL 7/2026)
- https://www.boe.es/buscar/doc.php?id=BOE-A-2025-26458 (RDL 16/2025)
- https://www.boe.es/buscar/doc.php?id=BOE-A-2026-2024 (derogation of RDL 16/2025)
- https://sede.agenciatributaria.gob.es/Sede/todas-noticias/2026/abril/1/nota-sobre-efectos-ambito-tributario-febrero.html
- `src/cadrumo/_data/corpus/normatives/html/rd-634-2015.html.extracted.md:81`
- `src/cadrumo/_data/corpus/normatives/html/ley-27-2014.html.extracted.md:110`, `:1849`, `:2358-2410`
- `src/cadrumo/_data/corpus/manuals/renta/2025/part1/source.pdf.extracted.md` (lines cited above)
- `src/cadrumo/_data/corpus/manuals/sociedades/2025/source.pdf.extracted.md:8342-8353`, `:25176-25190`
