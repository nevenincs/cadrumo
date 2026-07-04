---
tags:
  - '#audit'
  - '#y-siguientes-verification'
date: '2026-07-03'
modified: '2026-07-03'
related: []
---

# `y-siguientes-verification` audit: `y-siguientes multi-year revision correctness verification`

## Scope

The registry carries 37 `-y-siguientes` revisions that each claim to be current
for every filing year from their `valid_from` forward. The premise under test:
that a single multi-year revision is genuinely correct across all served years.
AEAT publishes per-year órdenes (módulos coefficients, estimación-objetiva
reductions, IS tipo-gravamen phasing) whose numeric figures drift annually, so a
single stamped value can silently serve a year whose BOE-published figure differs.
This is the fuller per-modelo grounding review flagged as the follow-up to the
`registry-grounding-spotcheck` audit, which already caught the EO general
reduction gap (100/2023, 100/2024) and the M303 módulos coefficient year-naming
drift.

The verification unit is one numeric figure in one revision: for each rate,
threshold, minoración, reduction, coefficient, or bracket the revision compiles,
determine whether AEAT published a DIFFERENT value for any served year in
2023-2026, and whether the registry carries the correct per-year value window
(a parameter's `values` array supports `date_axis` + `valid_from` time-windowing,
so a correct multi-year revision CAN hold several per-year values). Each figure is
classed GROUNDED (matches BOE for all served years), DRIFT (registry holds one
value but BOE changed it in a served year), or GAP (a per-year figure AEAT
publishes is missing or wrong).

Method: a progressively-rolled-out haiku+sonnet fleet, one agent per revision or
cluster, sonnet for the calc-bearing rate-varying modelos and haiku for the
breadth confirm over the structural/informativa forms. Findings are inventory to
confirm against HEAD before any remediation; this document does not modify
production code.

Coverage waves:
- Wave 1 (sonnet, calc-bearing): M130, M303 (both revisions), M200, M202.
- Wave 2 (sonnet, retenciones + IRPF): M180, M190, M193, M123, and the M131
  per-year revisions (EO reduction follow-up).
- Wave 3 (haiku, breadth confirm): the structural / informativa forms whose
  revisions carry no year-varying numeric calc parameter.

## Findings

### m130-2019-y-siguientes | low | genuine y-siguientes, every figure GROUNDED 2023-2026

Modelo 130 `2019-y-siguientes` (pagos fraccionados IRPF estimación directa),
served years 2019+. Every numeric figure the revision compiles is a stable RD
439/2007 art. 110 value that has NOT changed across 2023-2026, so a single
un-windowed value is correct. Verified against the bundled corpus
(`rd-439-2007-art-110.html.extracted.md`) plus live AEAT/BOE: the general 20%
fractional-payment rate (`irpf.direct_estimation_fractional_payment_rate`,
art. 110.1.a — GROUNDED), the 2% agriculture/livestock/forestry rate
(`irpf.agriculture_fractional_payment_rate`, art. 110.1.c — GROUNDED), the
100/75/50/25€ minoración table at 9.000/10.000/11.000/12.000€ thresholds
(`modelo-130-minoracion-rendimientos-netos`, art. 110.3.c — exact table match),
and the negative-result / prior-quarter carry bindings (structural, no year-scoped
variation). Art. 109 exemption is correctly modelled as a non-blocking ADVISORY
predicate reading a profile flag, not baked into the casilla-17 arithmetic
(consistent with commit `b645c8df3`). NON-DRIFT NOTE: the Ceuta/Melilla art. 110.2
60% rate reduction (extended by RDL 4/2024 and RDL 13/2025) is absent from the M130
registry — a narrow residency-segment coverage gap, not a served-year grounding
drift, since the reduction mechanism itself did not change; record only as a
possible future profile-conditional-rate coverage item.

### m202-2025-y-siguientes | low | no year-varying figure drift; DT 44ª variability correctly manual-input

Modelo 202 `2025-y-siguientes` (pago fraccionado IS). Served-year partition
confirmed: `2019-2022` (valid_to 2022-12-31), `2023-2024` (valid_to 2024-12-31),
`2025-y-siguientes` (valid_from 2025-01-01, no valid_to, periods 1P/2P/3P) serving
2025/2026+. Verified 2025-y-siguientes only. NO drift. The single registry constant
— the modalidad art. 40.2 percentage (`is.modalidad_cuota.percentage` = 18) — is
legally invariant (LIS art. 40.2 sets a flat 18% by statute text, not derived from
the filer's own tipo), verbatim-matched against bundled corpus
`ley-27-2014-art-40.html.extracted.md`, and correctly identical across all three
sibling revisions — GROUNDED. The DT 44ª micro-empresa phasing (21/22 in 2025 →
19/21 in 2026, Ley 7/2024, BOE-A-2024-26694) enters M202 ONLY through modalidad
art. 40.3 "porcentaje" casillas, which are correctly `input_kind = "manual"` (the
filer supplies their own tipo-derived percentage) — hardcoding a micro-empresa
tranche here would be wrong. The registry shows deliberate DT 44ª awareness: the
tipo-3 / tipo-4 band casillas (61/62, 64/65) are annotated 2025-only additions
absent from older revisions. ADJACENT (out of scope, already tracked): casilla 26
(B2 resultado previo) is not wired into casilla 32 — a structural wiring gap, not a
numeric drift, already referenced in the `m202-deferred-items` verify audit
(2026-07-01); confirm it is actioned.

### m200-2024-y-siguientes | medium | phasing GROUNDED per-year, but a provenance mis-cite and a 2026 engine-test gap

Modelo 200 `2024-y-siguientes` (IS declaración). The DT 44ª micro-empresa (INCN<1M)
and entidades-reducida-dimensión (art. 101, 1M-10M) rate phasing is CORRECTLY
time-windowed per year — NO repeat of the historical flat-23% mis-route. Casilla
`DP200014:00562` computes via a `bracket_table` parameter `is.modelo-200.tipo-
gravamen-pyme` with per-year brackets: 2024 flat 23% (Ley 31/2022 art. 39,
pre-DT44), 2025 21%/22% (DT 44ª §1.a), 2026 19%/21% (DT 44ª §2.a) — each
verbatim-matched against bundled corpus `ley-27-2014-dt-44.html.extracted.md` /
`ley-31-2022-art-39.html.extracted.md`. The ERD art. 101 lane
(`is.modelo-200.cuota-integra-bracket-erd-art101`) is separately phased 2025 24% →
2026 23% → 2027 22% → 2028 21% → 2029+ 20% (art. 29.1 steady state), all grounded.
General 25% and empresas-nueva-creación 15% are flat per art. 29, correctly
unwindowed. Structural nuance: DT 44ª is a HIGHER transitional override phasing
DOWN toward the art. 29.1 baseline (17%/20%), not a discount from it — registry
encodes this correctly. TWO ACTIONABLE ITEMS:
(1) PROVENANCE MIS-CITE (minor): the DT44 legal-catalogue entry in
`legal/is.toml` carries `document_id = "BOE-A-2014-12328"` and a matching
`permalink` pointing at the ORIGINAL Ley 27/2014, not `BOE-A-2024-26694` (Ley
7/2024, the amending law that inserted DT 44ª). The `notes` text and `corpus_ref`
content are correct; only the structured `document_id`/`permalink` are mis-pointed.
Does not affect calculation, only citation-tracking integrity.
(2) ENGINE-TEST GAP (medium): `test_modelo_200_cuota_integra_lanes.py` asserts the
2024 and 2025 figures against an engine run but nothing asserts the 2026 (19%/21%
pyme; 23% ERD) or 2027/2028 ERD figures — declared-in-TOML but not
engine-reproduced. Per `verification-grounding-needs-oracle-evidence`, extend the
2025 test pattern with 2026 (and ideally 2027/2028 ERD) sibling assertions.

### m303-2023-y-siguientes | low | GROUNDED; supersedes the prior spot-check módulos drift finding

Modelo 303 `2023-y-siguientes` (IVA). Served-year partition confirmed clean:
`2009-y-siguientes` closes at `year_to = 2022`; `2023-y-siguientes` (valid_from
2023-01-01, no year_to) serves 2023/2024/2025/2026+. SUPERSESSION: the
`registry-grounding-spotcheck` audit's medium finding (módulos coefficients
"-2025" applied across 2023-2026) no longer matches HEAD. A Phase-2 rework (ADR
`2026-07-01-modelo-303-regimen-simplificado-adr`) re-authored the parameters
`m303-modulos-iva-coeficientes-2025` / `-cuota-minima-pct-2025` as `keyed_brackets`
each individually stamped `valid_from = 2025-01-01, valid_to = 2025-12-31` (verified
directly). The 3 tabled IAE epígrafes (721.2, 722, 972.1) are byte-exact against
bundled corpus `orden-hac-1347-2024.html` (BOE-A-2024-24949, "para el año 2025"),
citing the IVA-specific table not the IRPF one. The runtime filters keyed_brackets
by filing year, so 2023/2024/2026 match no row and the op returns Decimal('0') — a
fail-safe abstention (casilla 48 stays manual input; the divergence advisory only
fires when the computed reference is >0), NOT silent under-declaration. Both
computed casillas are `internal_only` (export-excluded). Residual is coverage
breadth only (3 of ~80 epígrafes, 2025-only) — an explicitly-declared phased
backlog per the ADR, not a grounding defect; any future 2023/2024/2026 rows MUST
use the same per-year windowing (ground against Orden HFP/1172/2022 for 2023 etc.).
Recargo de equivalencia rates (LIVA art. 161: 5,2/1,4/0,5/1,75%) and general IVA
rates (21/10/4) are ledger-driven and law-stable — GROUNDED, not year-sensitive.
ACTION: the prior spot-check audit's módulos finding should be marked superseded.

### retenciones-cluster | low | all GROUNDED / NOT-APPLICABLE; one real rate, stable

Retención-rate cluster (M180 `2023-y-sig`, M190/M193/M123 `2024-y-sig`, plus M111
/M115 `2019-y-sig`). NO drift. Only M115 compiles a genuine rate parameter:
`irpf.urban_rental_withholding_rate` = 19% (single value, valid_from 2019-01-01),
consumed by `modelo-115-retenciones` (casilla 03 = 02 × rate), grounded to
`rd-439-2007:art-100` (bundled corpus, in force from 2018-12-23) — 19% has been law
since the 2015 reduction and is unchanged for 2023-2026 filings (live-confirmed), so
the single-value shape is correct — GROUNDED. The other five are pure informativas:
M123 lets the operator declare the withheld amount directly (`input_kind = manual`,
no computed rate); M111 the same; M180/M190/M193 are annual resúmenes that aggregate
already-filed quarterly M115/M111/M123 amounts via relations (`copy`/`add`), carrying
no rate literal. This is intentional design (retención amount as a taxpayer-declared
fact), not a gap — NOT-APPLICABLE / GROUNDED-by-abstention. RECURRING NON-DRIFT
NOTE: M115 (like M130) does not model the Ceuta/Melilla 60% reduction carve-out
(art. 100 §2) — a narrow residency-segment coverage item, not a served-year drift.

### eo-general-reduction-m100-m131 | medium | CORRECTS the spot-check; no under-declaration, orphan param + advisory-completeness gaps

Estimación-objetiva general reduction across M100 (2023/2024/2025) and M131
(2024/2025/2026). This RESOLVES and CORRECTS the `registry-grounding-spotcheck`
finding `eo-general-reduction-2023-2024-missing`, which feared a 2023/2024
over-declaration. There is NO numeric under/over-declaration: the official filed
casilla is MANUAL in every year and modelo — M100 casilla `1481` ("Rendimiento neto
reducido", no formula, no `target_casilla_id` producer in any of 2023/2024/2025) and
M131 casilla `01` ("Suma de rendimientos netos", manual) — so the taxpayer enters
the already-reduced figure computed off-app via AEAT's Renta WEB worksheet, exactly
as AEAT's own workflow operates. The reduction is applied upstream (mechanism (c)),
not by a registry formula. BOE figures confirmed against bundled corpus: 2023 = 10%
(Orden HFP/1172/2022, verbatim "reducir el rendimiento neto de módulos obtenido en
2023 en un 10 por 100"), 2024 = 5% (Orden HFP/1359/2023), 2025 = 5% (Orden
HAC/1347/2024). The real findings are ADVISORY-COMPLETENESS gaps:
(1) ORPHAN PARAM (the actionable one): M100/2025
`renta-2025-estimacion-objetiva-reduccion-general-rate` = 5 is correctly grounded
(`orden-hac-1347-2024:art-4`, `ley-35-2006:art-31`) but has ZERO consumers — dead
registry data. Either wire it into an advisory computed cross-check casilla
(mirroring the M131/2025 pattern below) or remove it.
(2) M131/2025 is the worked example done right: `modulos-rendimiento-neto-actividad`
= modulos - percent(modulos, `m131-modulos-reduccion-general-2025`=5), grounded
`orden-hac-1347-2024:da-1`, `internal_only=true`, NOT overwriting manual casilla 01,
surfaced via a non-blocking `advisory_when_computed_diverges(["01", ...])` predicate
— GROUNDED, consistent with `no-silent-under-declaration`.
(3) BREADTH GAP (low): only M131/2025 has the full Fase 1-4 módulos advisory engine;
M131 2024/2026/2019-2023 and M100 2023/2024 have no EO advisory cross-check at all —
absent everywhere pre-2025, so no regression, just an un-built advisory feature.
Extending the M131/2025 advisory-engine pattern to sibling years is a scoped
feature follow-up, not a grounding fix.

### m714-2021-y-siguientes | low | state escala GROUNDED, base-liquidable derivation a declared completeness GAP

Modelo 714 (Impuesto sobre el Patrimonio) `2021-y-siguientes`, serving 2021-2026.
NO numeric drift. The state escala de gravamen (Ley 19/1991 art. 30, all 8 tranches
0,2%→3,5%, `parameters/0001-patrimonio-escala-estatal.toml`, single value
valid_from 2021) is byte-identical to bundled corpus `ley-19-1991-art-30.html` AND
to the AEAT Manual Práctico Patrimonio 2024/2025 — GROUNDED, no BOE amendment to
art. 30 in the window. Mínimo exento 700.000€ (art. 28) and vivienda-habitual cap
300.000€ (art. 4.Nueve) are grounded legal-catalogue entries (reviewed, corpus
required_text passes), confirmed unchanged as STATE defaults. The art. 31 80%-floor
(casilla 39) formula is correct. SCOPE (declared, not a defect): the revision models
the STATE-DEFAULT scale ONLY — no autonomic (CCAA) scales/mínimos/bonificaciones —
so a resident of a CCAA with its own scale gets a state-only approximation; this is
openly documented in the constructs comment, a known limitation not a silent gap.
COMPLETENESS GAP (not drift): `patrimonio.base-imponible` and `base-liquidable` are
both `input_kind = manual` — no formula subtracts the 700k mínimo / 300k vivienda to
derive base liquidable, and the full límite-conjunto 60% (casilla 33/40) chain stays
manual. Honestly declared in the completeness_manifest (nothing claims completeness
it lacks, so `no-silent-under-declaration` is satisfied). Natural follow-up if deeper
coverage is wanted: wire `base-liquidable = base-imponible − mínimo − vivienda` as a
state-only formula. ITSGF (grandes fortunas) is correctly a separate modelo (718),
zero contamination of M714.

### m151-2015-y-siguientes | low | general escala GROUNDED (static since 2015); savings-base scale unmodelled (coverage gap)

Modelo 151 (régimen impatriados / Ley Beckham, LIRPF art. 93) `2015-y-siguientes`,
serving 2015-2026. NO drift. The general-base escala (24% up to 600.000€ / 47%
excess, `modelo-151.escala-cuota-integra-general`, single value valid_from 2015)
matches Ley 35/2006 art. 93.2.e).1º verbatim in bundled corpus
`ley-35-2006-art-93.html` — this figure has NOT changed since Ley 26/2014 took
effect 2015 (the 45%→47% raise happened AT the 2015 transition), so a single
non-windowed bracket_table is CORRECT, not a defect. Ley 28/2022 (startups) amended
only eligibility conditions, not the rate scale. Retención (art. 93.2.f) is manual
input, not computed — no drift risk. COVERAGE GAP (not drift): the savings-base
(ahorro) scale (art. 93.2.e).2º) — which Ley 31/2022 changed for 2023 by adding the
27%/28% top tranches — is ENTIRELY UNMODELLED (no parameter, no formula), honestly
disclosed in three separate code comments as an intentional corpus-first deferral.
So there is no stale/wrong value to correct — only an absent computation: an
impatriado with dividend/interest income has that portion absent from the computed
cuota. Honestly declared, so not a silent-under-declaration wrong-number violation,
but a real coverage gap. Follow-up (feature, not a grounding fix): build the
savings-base scale grounded to the per-year Ley 31/2022 tranches (verify exact
2023+ figures before implementing).

## Recommendations
