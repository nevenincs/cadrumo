---
tags:
  - '#research'
  - '#assets-core'
date: '2026-09-23'
modified: '2026-09-24'
body_schema: 'body-v2'
body_hash: 'sha256:a29668b26530decf8ce4fb01ec0590c4a4941149680efb6a326868b973e167d1'
related:
  - "[[2026-09-21-assets-core-lifecycle-contract-adr]]"
  - "[[2026-09-23-assets-core-amortization-method-set-adr]]"
---

# `assets-core` research: `IRPF vehicle affectation and LIS DA 18a vehicle free depreciation`

The accepted lifecycle decision leaves vehicles outside its scope, yet the 2025
registry admits the LIS table classes `transporte-externo` and
`transporte-buque-aeronave` and the simplified class `transporte` with no
affectation check (`src/cadrumo/_data/registry/aeat/modelos/100/revisions/2025/parameters/0002-activity-asset-amortization.toml:12`,
`:10`, `:102`). A passenger car also used privately can therefore be amortized
today although the regulation says it is not an affected asset at all. The
question is what affectation facts make a vehicle amortizable for an IRPF
activity, and what LIS DA 18a adds for new electric vehicles.

## Findings

### An asset used for both the activity and private needs is not affected

RIRPF art. 22.2.1º excludes elements used simultaneously for the activity and
private needs unless the private use is accessory and notoriously irrelevant
(`src/cadrumo/_data/corpus/normatives/html/rd-439-2007.html.extracted.md:473`).
Art. 22.4 defines that allowance as personal use on non-working days or hours
during which the activity is interrupted (`:476`). An element not recorded in
the accounts or official registers the taxpayer must keep is not affected,
save proof to the contrary (`:474`).

### A vehicle cannot be partially affected

LIRPF art. 29.2 and RIRPF art. 22.3 limit partial affectation to parts capable
of separate and independent use and exclude indivisible elements outright
(`src/cadrumo/_data/corpus/normatives/html/ley-35-2006.html.extracted.md:486`,
`rd-439-2007.html.extracted.md:475`). A vehicle is either wholly affected or
not affected; a business-use percentage has no legal footing.

### Passenger cars and similar lose the accessory-use allowance

Art. 22.4 second paragraph denies the accessory-use allowance to passenger cars
and their trailers, mopeds, motorcycles, aircraft and sport or leisure boats,
except (a) mixed vehicles for goods transport, (b) paid passenger transport,
(c) paid driving or pilot instruction, (d) travel of commercial
representatives or agents, and (e) habitual and onerous cession of use
(`rd-439-2007.html.extracted.md:477-482`). Vehicle categories follow the
traffic-law annex, and all-terrain vehicles are always passenger cars for this
purpose (`:483`). The AEAT 2025 manual restates the rule: such vehicles are
affected only when used exclusively for the activity, never when also used
privately, even accessorily, and gives a taxi on rest days as an admitted
exception (`src/cadrumo/_data/corpus/manuals/renta/2025/part1/source.pdf.extracted.md:15793-15817`,
`:15901-15914`).

### LIS DA 18a adds free depreciation only for affected new electric vehicles

DA 18a.1 admits free depreciation of new FCV, FCHV, BEV, REEV or PHEV vehicles
as defined in annex II of the Reglamento General de Vehículos, affected to an
activity, entering service in periods starting in 2024, 2025 and 2026
(`src/cadrumo/_data/corpus/normatives/html/ley-27-2014.html.extracted.md:2395`).
The AEAT 2025 manual states 2024 and 2025 for the 2025 IRPF period
(`source.pdf.extracted.md:19190-19196`). The incentive presupposes affectation;
it does not relax art. 22.

### Options

- A business-use percentage on the revision. Rejected: vehicles are indivisible,
  so a percentage would under- or over-state a charge that is legally all or
  nothing.
- A typed affectation declaration on the revision (vehicle category, private
  use, the art. 22.4 exception relied on, recording in the activity books and an
  evidence reference), evaluated before any vehicle-capable class is charged.
  Favoured: it encodes exactly the facts the regulation tests and fails closed
  on anything short of them.
- Keeping vehicles refused. Rejected as the end state: taxis, delivery vans,
  hire vehicles and exclusively-used cars are lawful affected assets; refusal
  remains the answer for undeclared or mixed-use vehicles.

The ADR must settle which table classes can hold a restricted vehicle and the
DA 18a entry-into-service window for 2025, which an open research question on
the RDL 7/2026 effect clause also touches.

Not investigated: DGT doctrine on proving exclusive use of a passenger car, and
VAT deduction of vehicles (LIVA art. 95.Tres), which the IVA register owns.

## Sources

- `src/cadrumo/_data/corpus/normatives/html/rd-439-2007.html.extracted.md:464-483` (RIRPF art. 22)
- `src/cadrumo/_data/corpus/normatives/html/ley-35-2006.html.extracted.md:486` (LIRPF art. 29)
- `src/cadrumo/_data/corpus/normatives/html/ley-27-2014.html.extracted.md:2393-2398` (LIS DA 18a)
- `src/cadrumo/_data/corpus/manuals/renta/2025/part1/source.pdf.extracted.md:15780-15914` (manual, affectation)
- `src/cadrumo/_data/corpus/manuals/renta/2025/part1/source.pdf.extracted.md:19186-19230` (manual, DA 18a)
- `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2025/parameters/0002-activity-asset-amortization.toml:10-13`, `:102` (admitted transport classes)
