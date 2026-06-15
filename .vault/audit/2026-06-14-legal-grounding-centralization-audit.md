---
tags:
  - '#audit'
  - '#legal-grounding-centralization'
date: '2026-06-14'
modified: '2026-06-14'
related: []
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace legal-grounding-centralization with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `legal-grounding-centralization` audit: `Inline-and-Hardcoded Regulatory Definition Inventory — Cross-Domain Centralization Sweep`

## Scope

Cross-domain sweep for inline / hardcoded / ungrounded / non-vetted regulatory
values and definitions that bypass the central authority (the registry
`legal_refs`→`corpus_ref` mechanism, the curated `core.external_constants`
re-export layer, or `core.config.Settings`), in violation of
`aeat-schema-central-config` and `registry-calculation-legal-grounding`. Five
concurrent RAG-first read-only audit agents, one per named domain — personal
income (IRPF), IVA rates/classification, recargo (equivalencia + extemporáneo),
deductible expense (gastos deducibles), and the IVA calculation engine. Each
located concepts via `vaultspec-rag` then confirmed exact sites with `rg` and
re-read at HEAD. This is the cross-domain successor to the pass-1
legal-grounding-verification audit (which fixed the Ley 44/2015 reserva especial
cap error).

## Findings

Severity order. Several findings were flagged INDEPENDENTLY by two or three
agents — convergence noted as high-confidence corroboration.

### F1 (HIGH — dormant resolver + inline live values; flagged by 2 agents) — art. 23.2 rental reducción tiers

`domain/fincas/_tier_resolver.py` serves the LIRPF art. 23.2 rental reducción
percentages (50 / 60 / 70 / 90 %, post Ley 12/2023) from inline module-level
`TierResolution` singletons carrying `reduccion_pct=Decimal("0.50/0.60/0.70/0.90")`
(lines ~107–138, 375), and `_aggregates.py` multiplies `tier.reduccion_pct`
straight into the filing amount. A registry reader `_resolve_tier_reduccion_rate`
(line ~397) AND the matching Modelo-100 registry parameters
(`renta-<year>-rental-reduccion-rate-tier-{50,60,70,90}`) BOTH already exist — but
`resolve_reduccion` never calls the reader, so the registry parameter is
authoritative on paper while the inline literal is what actually serves the
deductible percentage. A dormant-resolver (`no-dormant-source-resolvers` shape) +
inline-bypasses-gate violation. Already flagged in the May
`renta-scope-audit` and not yet closed. The companion
`PRIOR_RENT_REBAJA_THRESHOLD = Decimal("0.05")` (art. 23.2.a ">5 %") IS wired to a
live registry read with the constant only as fallback — acceptable, lower severity.
Remediation: wire `resolve_reduccion` to source each tier's rate from
`_resolve_tier_reduccion_rate(period_year, tier_id)`, constant becomes documented
fallback (the `_amortization_ledger.py` pattern is the in-repo gold standard).

### F2 (HIGH — dormant subsystem + ungrounded inline thresholds; flagged by 3 agents) — prorrata thresholds

`domain/iva/_prorrata.py` inlines two binding LIVA regulatory thresholds with no
registry parameter and no `external_constants` home: `Decimal("1.10")` (line ~455,
LIVA art. 103.Dos — prorrata especial mandatory when the general deduction exceeds
the especial by >10 %) and `_SECTORAL_SEPARATION_THRESHOLD_PERCENTAGE_POINTS =
Decimal("50")` (line ~464, LIVA art. 9.1.c — sectoral separation mandatory at >50
percentage-points spread); plus a `ROUND_CEILING` art. 102.Dos legal rounding
direction (line ~358). The IVA-calc agent additionally found the ENTIRE prorrata
subsystem dormant — `compute_prorrata_general`, `is_especial_mandatory`,
`requires_sectoral_separation`, `aggregate_*_prorrata` have zero production callers
(only `__init__` re-exports + tests); it is built, tested, exported, but never
enrolled in the live calculate mesh or any registry binding. Ungrounded inline +
DORMANT/DUPLICATE-PATH. Remediation: EITHER enroll prorrata as a registry-declared
aggregation source (a `prorrata` source kind + bindings on 303 casilla 28/44, 390
casilla 33, with the `1.10`/`50`/round-ceiling values declared as registry data
grounded in `ley-37-1992:art-102`/`art-103`/`art-9` with `corpus_ref`), OR delete
the dormant subsystem per `no-legacy-compatibility`. Do not leave live-but-unrouted
capacity. Interim safe step: promote the two thresholds to `external_constants`
with `legal_refs` so the value is centralised even before the routing decision.

### F3 (MEDIUM — ungrounded inline casilla-routing table) — M303/M390 compensación casilla numbers

`application/calculations/_iva_compensation_history.py` hardcodes the M303/M390
compensación casilla-number→role mapping as inline string literals (`"69"`, `"87"`,
`"110"`, `"78"`, `"71"`, `"97"`, `"662"` at lines ~249–342) via `_casilla_value`,
a plain dict-get that never confirms the number against the resolved revision's
casilla definitions. The `iva.*` semantic-id second args are only fallbacks, not
the authority. Filed-observation projection path (not the calc engine producing
values), which lowers severity. Remediation: resolve these casilla ids through the
registry snapshot casilla definitions (semantic id authoritative; numeric form a
registry attribute, not a feature-code literal).

### F4 (MEDIUM — dormant duplicate routing helpers) — casilla_59/60 base-imponible helpers

`application/aggregation/_iva_ledger.py:~735,754` (`casilla_59_base_imponible`,
`casilla_60_base_imponible`) hardcode category→casilla routing (INTRA_COMMUNITY_SUPPLY→59,
EXPORT_THIRD_COUNTRY_ZERO_RATED→60) duplicating the generic registry mechanism
`resolve_ledger_iva_aggregation_binding_values` (`fact="base_amount_sum"`) for which
no registry binding yet exists. Zero production callers; docstrings admit "the
registry binding in S94 will supersede this helper." DORMANT/DUPLICATE-PATH.
Remediation: author the `ledger_iva_aggregation` base_amount_sum bindings in
`303/.../bindings/` and delete both Python helpers.

### F5 (MEDIUM — inline-grounded, bypasses gate) — DT12 40% and SAL reserva 10% / 2×

`domain/modelos/_dt12_reduccion.py:~46` inlines the LIRPF DT 12ª 40 % rescate
reducción (`Decimal("0.40")`); `domain/modelos/_sal_reserva_especial.py:~52,54`
inlines the Ley 44/2015 art. 14 10 % dotación rate and the 2×-capital cap factor.
All three are docstring/`boe_citation_id`-grounded (and ADR-sanctioned for DT12) but
bypass the registry `legal_refs`→`corpus_ref` gate — the exact class that let the
pass-1 reserva 50%-vs-2× error survive. Remediation: promote to registry parameters
or `external_constants` grounded on `ley-35-2006:dt-12` / `ley-44-2015:art-14`.

### F6 (LOW-MEDIUM — inline-grounded classification constants) — Art. 58/59 family thresholds

`domain/contribuyente/family.py` inlines LIRPF art. 58.1 `_MAX_AGE_ORDINARY = 25`
(line ~31), art. 58.3 `_MAX_AGE_MENOR_TRES = 3` (line ~32), and art. 59 shared-
custody 50 % split `Decimal("0.5")` (line ~327). Comment-grounded but bypass central
authority. Remediation: promote to `external_constants`
(`MINIMO_DESCENDIENTE_MAX_AGE`, `MINIMO_MENOR_TRES_MAX_AGE`,
`CUSTODIA_COMPARTIDA_PRORRATA_FACTOR`) grounded on the cited articles.

### F0 (verified clean — no action) — recargo, IVA rates, most IRPF

Confirmed exemplary and NOT findings: the recargo de equivalencia ladder
(LIVA art. 161, 5.2/1.4/0.5/1.75 %) and the recargo extemporáneo LGT art. 27.2
graduated scale (1/3/6/12/15 %, post-Ley 11/2021) both live entirely in registry
TOML with full `corpus_ref`+`document_id`+`required_text` grounding; the IVA rate
ladder (21/10/4/0) loads from `rates.toml` via `lookup_rate`; amortización (3 %),
art. 85 imputación, maritime exemptions, deducción maternidad, gastos difícil
justificación (5 %), dietas caps, and home-office suministros (30 %) all read from
registry/`external_constants`. No SUSPECTED-WRONG value found in this pass. The
unimplemented LGT art. 27.5 prompt-payment 25 % reducción is noted for future
registry authoring if built.

## Verification pass — concept inventory vs BOE (4-agent web-verification swarm)

A second swarm verified the codified regulatory FIGURES (not just centralization) of
the broader concept inventory against authoritative BOE/AEAT sources online. Result:
the codebase is overwhelmingly correct and well-grounded; the swarp found one genuine
wrong figure, four citation-imprecisions (all fixed), and two non-value gaps.

### V0 (broad confirmation — verified CORRECT vs BOE)

Confirmed against the live BOE/AEAT source: the full IS rate set (general 25%,
micro-empresa DT 44ª 21/22-2025 & 19/21-2026, new-entity 15%, cooperative 20%,
non-profit 10%), the IRPF escala estatal general half-scale and the escala del ahorro
INCLUDING the Ley 7/2024 jump of the >300.000 € top tranche to 30% for 2025 (the
registry already carries 28% for 2024, 30% for 2025 — correct), the M130/M210
retención/fraccionamiento rates, the informativa thresholds (M347 3.005,06 €, M720
50.000 €/bloque, M349 50.000 € cadence), gastos difícil justificación 5%/2.000 €, the
recargo ladders, and 14 of the `external_constants` regulatory constants. No
wrong-value defect in any of these.

### V1 (WRONG-vs-LAW — tracked, cuota is correct) — M200 tipo-gravamen-erd scalar echo

`_data/registry/.../200/.../parameters.toml` `is.modelo-200.tipo-gravamen-erd` is a
flat-23% scalar (`value = "23"`, `valid_from 2023`, grounded on the superseded Ley
31/2022 art. 39) feeding the casilla 00558 rate ECHO. For 2025/2026 micro-empresa
(INCN < 1M) entities the law (DT 44ª) is the two-tranche 21/22 (2025) and 19/21
(2026), so the displayed rate echoes a stale 23%. CRITICAL NUANCE verified against
code: the sibling `cuota-integra-bracket-erd` IS correctly year-stepped, so the actual
**cuota (tax owed) is correct** — only the scalar display in 00558 is stale. This is
the documented-deferred `lookup_bracket_by_entity_type` limitation (a scalar cannot
express a two-tranche rate). NOT fixed in this pass: changing the scalar without
AEAT-form-level knowledge of how 00558 represents a two-tranche micro-empresa rate
could make the echo more wrong, and the tax is already correct. Tracked for a focused
fix that lands the deferred bracket-based rate echo. A related latent gap: the true
ERD (INCN < 10M, LIS art. 101) DT 44ª schedule 24/23/22/21 is absent from the registry
and the "erd" parameter name misleadingly covers the INCN<1M micro-empresa category.

### V2 (citation-imprecision — ALL FIXED this pass)

Four values were correct but cited a framework/wrong article rather than the binding
provision that sets them (`registry-calculation-legal-grounding`). All corrected:
- `MINIMO_MENOR_TRES_MAX_AGE` cited art. 58.3 → **art. 58.2** (corpus confirms art. 58
  has only two apartados; '58.3' does not exist). Fixed in `external_constants` +
  `family.py`.
- `CUSTODIA_COMPARTIDA_PRORRATA_FACTOR` cited art. 59 (mínimo por *ascendientes*) →
  **art. 61** normas comunes ("se prorrateará entre ellos por partes iguales"). Fixed
  in `external_constants` + `family.py` + the operator-facing advisory across all four
  locale catalogues (via the locale CLI). NOTE: these two were introduced THIS session
  in F6, carried from pre-existing `family.py` errors — the verification swarm caught
  the campaign's own imprecision.
- `M347_THRESHOLD_EUR` cited RD 1065/2007 art. 31.1 (general obligation) → **art. 33.1**
  (the provision fixing 3.005,06 €). Fixed across `external_constants` +
  `_calculate_input` + `_row_models` (7 sites).
- `MODELO_720_REPORTING_THRESHOLD_EUR` cited bare "AEAT instrucciones" → **RD 1065/2007
  arts. 42 bis/ter/quater (RD 1558/2012) under LGT DA 18ª**. Fixed in `external_constants`.

### V3 (non-value gap — tracked) — estimación objetiva magnitude-exclusion limits not codified

The módulos volume-exclusion limits (250.000 / 125.000 / 150.000 €, LIRPF art. 31 +
DT 32ª, extended through 2026 by RDL 9/2024) exist only in corpus reference text, never
as an enforceable registry parameter or constant — the regime is gated by self-declared
booleans with no numeric safety net. Not a wrong value; a silent gating gap. Tracked as
a future grounding feature (author the limits as registry parameters with legal_refs).

## Verification pass 3 — IRNR / Patrimonio / amortización-deductions (3-agent swarm, 2026-06-14)

Extended the BOE web-verification to surfaces the first two passes did not cover. Found
ONE more real wrong-calc-value (now the campaign's second, after the reserva).

### V4 (WRONG-vs-LAW — FIXED) — M210 IRNR interest rate 24% should be 19%

`_data/registry/.../210/.../0001-m210-tipo-gravamen-2025.toml` `interest` keyed-bracket
carried `0.24` with a comment claiming a "non-EU 24% fallback". TRLIRNR (RDLeg 5/2004)
art. 25.1.f sets 19% for "1.º dividendos / 2.º intereses / 3.º ganancias patrimoniales"
for ALL non-residents sin EP, with NO residency condition — confirmed against BOE
(Iberley faithful reproduction) + AEAT manual no residentes. The comment confused the
art. 25.1.a general-rate EU/EEE reduction with the unconditional art. 25.1.f. Internal
corroboration: the registry's own `ganancia_patrimonial` (same letra f, 3º) was correctly
0.19 while `interest` (2º) was 0.24. A non-EU resident's Spanish-source interest was
over-declared ~26%. **Fixed** to 0.19; 46 M210/IRNR tests pass (no test asserted the wrong
value). A C1-class side issue: the bundled corpus snippet `trlirnr-rdleg-5-2004` art. 25.1.f
mis-phrases the rate as EU/EEE-conditional (self-declared non-authoritative Phase-1 anchor,
`required_text` empty) — operator should refresh that corpus text; the parameter is the calc
authority and is now correct.

### V5 (verified correct / gaps) — Patrimonio (M714/M718) and amortización/deductions

Patrimonio: 4 values verified CORRECT + centralized against bundled authoritative corpus
(Ley 19/1991, BOE-A-1991-14392) — mínimo exento 700.000 €, vivienda habitual 300.000 €,
límite conjunto 60%/80%, escala 0,2-3,5% — all correctly marked STATE defaults with CCAA
devolution flagged. M714 escala is `input_kind=manual` (Phase-B calc deferred); M718 grandes
fortunas (Ley 38/2022) entirely absent — both NOT-CODIFIED feature gaps, not wrong values.
Amortización/deductions: 8 coefficients verified CORRECT + centralized (amortización 3%
RIRPF art.14.2.a; M130 20%/2%; M131 2%/2%; rental tiers 50/60/70/90% + 5% rebaja) — all
registry-causal with documented fallbacks, amortización grounded in bundled authoritative
corpus. LIS amortización tabla + donativos 80/40 + I+D+i are NOT-CODIFIED (operator-input
casillas, no multiplied coefficient to drift). No new ungrounded inline regulatory
coefficient surfaced in the catch-all `Decimal("0.NN")` sweep.

### Verification campaign tally (all passes)

Across all verification passes the swarm web-checked the IS / IRPF / IVA / recargo /
informativa / IRNR / patrimonio / amortización-deduction rate-and-threshold surface against
BOE and found **2 real wrong-calc-values — both fixed** (Ley 44/2015 reserva especial cap
4× too low; M210 IRNR interest 24% vs 19%) — plus several citation-precision fixes and one
fabricated-corpus defect (módulos DT 32ª, caught by the honesty review). Every other audited
figure verified correct and centralized. The remaining items are NOT-CODIFIED feature gaps
(M714 escala, M718, módulos enforcement) tracked for deliberate build, not drift.

## Verification pass 4 — IRPF mínimo amounts + reducciones/deducciones (2026-06-14)

### V6 (WRONG-vs-LAW — FIXED + surface completed) — IRPF mínimo personal y familiar

The IRPF mínimo sweep found the campaign's THIRD wrong-calc-value: the 2024 menor-tres
mínimo parameter codified 3.000 € where LIRPF art. 58.2 / the AEAT manual state 2.800 €
(a €200 over-statement per child under 3). Root cause: a second C1-pattern bundled-corpus
error — `ley-35-2006-art-58.html` itself carried 3.000 behind a header claiming official
unchanged text — which had propagated to the parameter and two tautological tests. Fixed
all four (parameter, corpus, legal-notes, tests). Beyond the fix, the whole mínimo surface
was COMPLETED and gate-pinned: the previously-uncodified art. 60 discapacidad amounts
(3.000/9.000/+3.000, legal entry grounded in the bundled `ley-35-2006.html#a60`), the missing
2025 descendientes/ascendientes params, and the absent 2020-2023 backfill were all authored
(every amount AEAT-cross-checked), and a `read_parameter`-backed grounding gate now pins all
13 mínimo amounts across the six live ejercicios 2020-2025 (78 cases). The codified rule was
refined: even the bundled corpus must be figure-cross-checked against live BOE/AEAT.

### V7 (verified correct — 0 bugs; gaps + 1 flag) — IRPF reducciones/deducciones

Verified the figure-bearing IRPF reductions: tributación conjunta (3.400/2.150, art. 84.2)
CORRECT both years. ZERO wrong-calc-values; no ungrounded Python literals (all reductions
live in registry formulas). One flag-for-review (not a bug): the previsión-social cap
(art. 52) uses the `10.000` aggregate ceiling (1.500 personal + 8.500 employer) without an
explicit 1.500 personal-only guard — defensible (the 1.500/8.500 split is form/casilla-chain
handled; forcing 1.500 would wrongly cap employer-contribution filers), surfaced for operator
review. NOT-CODIFIED gaps (operator-input casillas, no codified figure to drift): the art. 20
work-income reduction brackets (6.498→7.302 €, the genuinely-changed-for-2025 / RDL 4/2024
item — highest-risk gap), the DT-18ª vivienda-habitual deduction (15%/9.040 €), and the
DT-15ª alquiler deduction (10,05%). Each is a future codification candidate, not a wrong value.

### V8 (GROUNDING DEFECT — FIXED) — M100 casilla 0023 art. 20 reduction citation

Acting on the V7 art-20 gap, verification of the art. 20 work-income reduction surface
found a grounding defect (not a wrong figure): casilla 0023 ("Cuantía aplicable con
carácter general"), which IS the reducción por obtención de rendimientos del trabajo
(art. 20 — it reduces rendimiento neto 0022 to rendimiento neto reducido 0025 via formula
`0022 - 0057 - 0023`), cited `legal_refs = ["ley-35-2006:art-17"]` (rendimientos íntegros
— the wrong article) in the 2021, 2022, 2023, and 2024 revisions. The 2020 and 2025
revisions already carried `ley-35-2006:art-20`. Confirmed casilla identity against the AEAT
2024 manual §7.1.6 and the formula position; confirmed the art-20 figures against the
bundled `ley-35-2006.html#a20` (7.302 / 1,75 / 2.364,34 / 1,14 / 19.747,5 / 6.500, RDL
4/2024 art. 3.1 BOE-A-2024-12944), which matches the AEAT manual. Fixed all four years to
`ley-35-2006:art-20` and pinned `test_trabajo_reduccion_art20_grounded` (10 cases:
0023→art-20 across 2020-2025 + art-17-regression bar on the corrected years). Commit
`80a87357f`.

**Deferred (needs ADR — not a defect):** making casilla 0023 *computed* from the verified
art. 20 piecewise schedule is a genuine feature, NOT a safe inline edit, because the
reduction's eligibility gate ("otras rentas, excluidas las exentas, distintas del trabajo
≤ 6.500 €") depends on the whole rest of the return — a forward/ordering dependency on
casillas not necessarily resolved at 0023's evaluation point. AEAT's own program computes
0023 automatically; replicating that here requires deciding the otras-rentas aggregation
ordering (an architectural question) before authoring the formula. Tracked as a future
codification candidate; the casilla remains a grounded MANUAL input meanwhile.

### V9 (GROUNDING DRIFT CLUSTER — FIXED) — M100 rendimientos-del-trabajo section

The 0023 fix exposed a whole-section drift: the 2021-2024 M100 revisions had grounded the
entire rendimientos-del-trabajo gasto/reducción sub-section to the `art-17` rendimientos-
íntegros chapter instead of the specific binding article. Confirmed against the canonical
2025 revision (which grounds each correctly) and the reviewed art-18/art-19/art-20 legal
entries, then aligned 2021-2024:
- **0011** (reducciones por irregularidad — label literally cites "artículo 18") → `art-18`.
- **0013** (cotizaciones SS, art. 19.2.a), **0014/0015** (cuotas sindicato/colegio, art.
  19.2.d), **0016** (defensa jurídica, art. 19.2.e), **0017** (rendimiento neto previo),
  **0019** (otros gastos), **0020** (incremento movilidad geográfica), **0021** (incremento
  discapacidad activos) → `art-19`.
- **0023** (reducción art. 20) → `art-20` (V8).
Casillas 0002-0010/0012 (rendimientos íntegros) correctly retain `art-17`. Total 16 casillas
× 4 years corrected. `test_trabajo_reduccion_art20_grounded` now pins the full cluster (64
cases across 2020-2025, barring the art-17 regression); 80 registry referential/legal tests
green. Commits `80a87357f` (0023), `ad0835b14` (0019-0021), `13412f6d2` (0011/0013-0017).
None of these touched a compiled regulatory VALUE — they are MANUAL-input casillas whose
binding-article citation had drifted; no calc output changed, but the provenance surface
(`registry-calculation-legal-grounding`) is now faithful per the AEAT DR section structure.
The net-chain trio (0018/0022 → art-19, 0025 → art-18+19+20) was completed in commit
`fbfb2d1e7`, closing the section (19 casillas × 4 years). Final gate: 81 cases (2020-2025).

### V10 (DISCOVERY — broader cross-section divergence, NOT bulk-fixable) — open follow-up

A 2024-vs-2025 `legal_refs` diff over the 2.053 shared M100 casillas surfaces a large
divergence set beyond the trabajo section. **It is a discovery signal, not an auto-fix
list, and MUST NOT be bulk-applied.** Two distinct populations are mixed in the diff: (a)
genuine 2024 drift (a casilla citing an article that is *wrong* for it — the art-17-for-a-
reduction class this campaign fixed in the trabajo section); and (b) 2025 *enrichment* —
the 2025 revision was authored more recently with broader, sometimes 2025/2026-specific
refs (e.g. `orden-hac-277-2026:art-3`, `rd-439-2007:art-109`, `art-99` retenciones added to
many íntegro casillas) that are NOT 2024 defects and would be WRONG to copy into 2024.
Distinguishing (a) from (b) requires per-casilla judgment against the AEAT DR + the binding
provision — exactly the care the trabajo-section sweep applied. Tracked as an open
follow-up: a dedicated section-by-section grounding audit (capital mobiliario, actividades
económicas, ganancias patrimoniales, deducciones) comparing each 2021-2024 casilla's cited
article to its binding provision, fixing only the genuine-drift (a) cases and pinning each
section with a gate. Do NOT diff-and-align; verify each casilla's binding article first.

### V11 (CROSS-SECTION COPY-PASTE DEFECT — capital mobiliario FIXED; inmuebles/retenciones open)

Executing V10's careful audit surfaced a genuinely-wrong (disjoint-grounding) class distinct
from the over-broad enrichment noise: a **cross-section copy-paste defect** where whole sections
in 2021-2024 carry the **actividades económicas** chapter `{art-27,28,30,31,32}` and *none* of
their own provisions. The filter that isolates it: 2024 and 2025 ley-arts are disjoint AND the
2024 box's own label matches its section (excluding the `0058`-style renumbering false-positives,
where same id = different box across years — a proven hazard that bars naive id-mapping).

**Fixed — capital mobiliario (29 boxes × 4 years = 116 casillas):** every
`rdto_capital_mobiliario` box cited the actividades chapter. Re-grounded per-box from each box's
**own label** within-year (ingreso→art-25, gastos/reducción→art-26, neto/reducido/suma→25+26) —
a classification that independently *reproduces the canonical 2025 per-box grounding* on every
matched box (strong cross-check), and is renumbering-immune. Pinned by
`test_capital_mobiliario_grounding`. Commit `192e10b24`.

**Open — inmuebles needs PER-SUBSECTION care, NOT the capital-mobiliario method.** Testing the
within-year label classifier on the `inmueble` section revealed it is **heterogeneous**: 222 boxes
cite the actividades chapter, but they conflate at least four grounding families — (1) the
capital-inmobiliario rendimiento chain (arts. 22/23/24, + art-85 for imputación), (2) **ganancias
patrimoniales por transmisión de inmuebles** (boxes 1816-1915, 1226-1230, 1641 — governed by arts.
33-39, NOT 22), (3) structural/identity data-entry fields (0063-0088: % propiedad, referencia
catastral, fechas, NIF — arguably no rendimiento article), and (4) deducción-obras desglose
(1393-1440). The ingreso/gasto classifier validated against the 25 known-2025 rendimiento-chain
boxes (24/25 OK) but would inject **art-22 onto ganancias-patrimoniales boxes** — a wrong-article
regression. The capital-mobiliario sweep was safe precisely because that section is a single income
category; inmuebles is not. Correct approach: restrict to the verified rendimiento-del-capital-
inmobiliario computation chain (the ~25 boxes with known-2025 grounding: 0089, 0102, 0104, 0107,
0109-0117, 0131/0132, 0146-0156) and fix only those, leaving the ganancias/structural boxes to a
ganancias-patrimoniales grounding pass. Do NOT run the bulk classifier over the whole `inmueble`
section.

**FIXED — inmuebles rendimiento chain (25 boxes × 4 years = 100 casillas, commit `1b0e0127f`):**
exactly that verified subset was re-grounded (ingresos→art.22, gastos/amortización/reducciones→
art.23, mínimo parentesco→art.24, renta imputada→art.22+85, neto/reducido/suma→combined), each box
matched by its OWN mojibake-tolerant label (renumbering-safe) and rewritten only when it cited the
actividades chapter — all 100 matched their expected concept (0 skips), reproducing the canonical
2025 per-box grounding. Pinned by `test_inmuebles_rendimiento_grounding` (100 cases). **Retenciones
/ pagos** (0591/0604/0609 → art.99) also fixed (commit `580996288`).

**Still open (inmuebles remainder — from-scratch ganancias pass, NO ground truth):** the
ganancias-patrimoniales-por-transmisión boxes (1816-1915, 1226-1230, 1641 → should be arts. 33-39
+ DT 9ª for the abatimiento reduction box 1839), the deducción-obras desglose (1393-1440), and the
structural/identity data-entry fields (0063-0088) still carry the actividades chapter. CRITICAL: for
the ganancias boxes there is **no usable ground truth** — verified that BOTH years are wrong: 2024
cites the actividades chapter, and **2025 cites a 15-article kitchen-sink `{17-32,99}` that still
OMITS the correct arts. 33-39** (e.g. 1833 "Ganancia patrimonial obtenida", 1826 "Valor de
transmisión", 1839 "Reducción DT 9ª" all lack any ganancias article). So this is not a copy-from-2025
fix like the rendimiento chain; it is a from-scratch, BOE/AEAT-verified ganancias-grounding pass
(arts. 33-39, art. 38 reinversión, DT 9ª) with a per-box article map built and confirmed against the
law — deliberately NOT rushed here, since no correct reference exists to copy. The whole
ganancias-patrimoniales grounding is in fact wrong across the registry (all years), a significant
standalone finding for that dedicated pass. Plus a separate **2025 over-grounding** artifact: the
same 15-17-article kitchen-sink set (incl. actividades + `orden-hac-277-2026` + `rd-439-2007`)
appears on 2025 boxes 0043/0044/0049 and the ganancias boxes — a 2025-authoring imprecision to
narrow in the same pass.

**UNBLOCKED — missing ganancias legal entries authored (commit `a056aeda4`).** A prerequisite for
that pass was that the binding provisions exist in the legal catalogue: only art-33/34/37 did —
art-35 (transmisiones onerosas), art-36 (transmisiones lucrativas), art-38 (exención por
reinversión), and art-39 (ganancias no justificadas) were ALL MISSING, so the registry could not
have grounded any ganancia box to them even with a correct map. Authored all four grounded in the
bundled `ley-35-2006.html` (#a35/#a36/#a38/#a39), each with a corpus-verified `required_text` the
catalogue-verification gate validates, and honest agent-authored `reviewed_by` provenance (operator
to re-stamp). Still to do in the dedicated pass: author the DT-9ª entry (abatimiento reduction),
build and apply the per-box ganancia article map (valor transmisión/adquisición→art-35,
ganancia/pérdida obtenida→art-33/34, lucrativa→art-36, reinversión→art-38, abatimiento→DT-9ª),
separate the structural data-entry fields, and pin the section.

**UPDATE — DT-9ª authored (commit `eec9cd772`); ALL ganancias legal entries now present**
(art-33/34/35/36/37/38/39 + DT-9ª, each corpus-verified). The legal-authority infrastructure for
the ganancias box-grounding is therefore COMPLETE — every binding provision the per-box map needs
now exists in the catalogue.

**CRITICAL HAZARD discovered — the M100 1816-1915 id range is a severe cross-year renumbering
minefield.** A dry-run of an id-keyed, label-guarded ganancia classifier proved the SAME casilla id
maps to entirely different economic concepts across filing years: e.g. id `1911` is "Importe real de
la transmisión" (ganancia, →art-35) in 2024 but "Número de hijos que dan derecho a la deducción"
(deducción por maternidad, a completely different article) in 2022; ids `1826/1830/1831/...` do not
exist at all in 2021. The label guard correctly REFUSED every mismatched application (the 2022
maternidad boxes were skipped, not mis-grounded), confirming the guard is sound — but also that this
range CANNOT be grounded by any cross-year id map, by section, or by number range. Additionally the
range interleaves true ganancias (1816-1846) with autonomic deducciones (1847-1857, 1905-1910) and
imputación-temporal boxes (1858-1904) under one section tag. The dedicated pass MUST work
strictly per-year, per-box, label-confirmed (the proven-safe pattern), classifying each box's
economic concept (ganancia vs deducción vs imputación) before assigning an article — never a bulk or
cross-year operation. This is the single most renumbering-hostile surface found in the campaign.

**FIXED — capital-inmobiliario amortización-base block (commit `48451f2b0`, 132 casillas).** The
remaining capital-inmobiliario boxes (ids 100-156 in the inmueble section: intereses invertidos,
gastos de reparación, valor catastral, importe/gastos de adquisición, mejoras, base de amortización,
acquisition-type claves, fechas/días arrendado — 33/year × 4) were re-grounded to art. 23 (gastos
deducibles incl. amortización), and the retención box 0153 to art. 99 + art. 101 + rd-439. The safe
disambiguator was the **id range** (id < 1000 in the inmueble section = capital inmobiliario; ganancia
boxes are ≥ 1226) plus a ganancia-label guard (0 hits) — this range is stable across years (33
boxes/year, no 1xxx-style renumbering). Pinned by `test_capital_inmobiliario_range_never_cites_actividades`.
With this, the WHOLE capital-inmobiliario section (rendimiento chain + amortización base + retención)
is grounded; only the heterogeneous ganancia (1226-1915) minefield remains for the documented per-year pass.

### V12 (SCOPE — the actividades grounding is a form-wide GENERIC-DEFAULT artifact, not a localized copy-paste)

A by-section census of every 2021-2024 casilla citing the actividades chapter `{27,28,30,31,32}`
overturns the "copy-paste from actividades" framing: the chapter is a **generic default** smeared
across DOZENS of unrelated data-entry sections. The 2024 census of actividades-citing boxes spans
(non-exhaustive): `reg_estima_obj_agricola`/`actividad_agr` (69), `gp_otros_inmuebles`/
`elemento_inmueble` (64, ganancias otros inmuebles), `inmuebles`/`inmueble` (48, now fixed),
`regimenes_especiales`/`re_at_rentas` (46, atribución de rentas), `reg_estima_obj`/`actividad_est_obj`
(39, módulos), `gp_otros_criptomonedas` (34, ganancias cripto), `mejoras_energeticas_viv` (32,
deducción), `gp_otros_elementos`/`elemento_patrimonial` (25, ganancias), the `anexo_c_res` previsión-
social / saldos-negativos blocks (~200 boxes), and `deduccion_autonomica_res/*` (the autonomic
deductions). Two decisive consequences:

1. **Actividades is CORRECT in the genuine actividades/módulos sections.** `reg_estima_obj`,
   `reg_estima_obj_agricola`, `actividad_est_obj`, `actividad_agr` ARE estimación objetiva
   (arts. 27/28/31) — the chapter grounding there is right or near-right and MUST NOT be removed.
   So no blanket actividades-strip is valid; the fix is per-section, by economic concept.
2. **The clean discriminator is the SECTION TAG, never the id range.** Section names
   (`gp_otros_criptomonedas`, `re_at_rentas`, `anexo_c_res/...`) are concept-specific and stable
   across years, whereas the id ranges renumber catastrophically (the 1816-1915 grab-bag). A safe
   pass scopes by section tag and grounds each section to its concept's articles (ganancias by asset
   → arts. 33-37/DT-9ª; atribución de rentas → arts. 86-90; previsión-social excesos → arts. 51/52;
   autonomic deductions → the autonomic law; energy-efficiency deduction → its DA). Within a single
   concept-section a uniform foundation grounding (e.g. ganancia sections → {art-33, art-34}) is
   foundation-correct and never injects a wrong article, with per-box precision (35/36/38) as a refinement.

This is the true remaining grounding surface: a form-wide, multi-section expert pass (dozens of
distinct economic concepts), of which the four cleanly-disambiguable sections (trabajo, capital
mobiliario, capital inmobiliario, retenciones — ~436 casillas) are now done and gated. The ganancia
legal-entry infrastructure (arts. 33-39 + DT-9ª) is in place for the ganancias subset. The remainder
is a large, deliberately-scoped, per-section effort — NOT an autonomous bulk operation, and explicitly
not blanket-strippable because actividades is the correct grounding in the actividades sections.

### V13 (V12 METHOD APPLIED — ganancias-by-asset concept-sections grounded, ~496 casillas)

The V12 section-tag method was validated end-to-end and applied to the three concept-pure
ganancias-por-transmisión-de-elementos sections, each grounded to the ganancias foundation
(arts. 33 concepto + 34 importe) — foundation-correct for every box, never the actividades chapter:
`elemento_criptomoneda` (102 casillas, 2022-2024, commit `dee24ad84`), `elemento_inmueble`
(gp_otros_inmuebles) and `elemento_patrimonial` (gp_otros_elementos) together (394 casillas,
2021-2024, commit `48da981a4`). Each section was verified concept-pure (0 deducción labels, no
interleaving) before grounding — the section tag is the clean, renumbering-immune discriminator V12
predicted (it caught `elemento_patrimonial` boxes from id 0357, which the 1226-1915 id-range never
would have). Pinned by the extensible `test_ganancias_seccion_grounding`. Per-box precision
(valor transmisión→art-35, reinversión→art-38, abatimiento→DT-9ª) is a future refinement on top of
the correct foundation. Remaining actividades-default concept-sections need their OWN concept's
articles (atribución de rentas `re_at_rentas`→arts. 86-90; previsión-social excesos→arts. 51/52;
autonomic deductions→autonomic law; energy-efficiency deduction→its DA) — each a per-concept grounding
with its own legal-entry check, not the ganancias foundation.

### V14 (V12 METHOD GENERALISED across concepts — ~1932 casillas, 6 legal entries)

The V12 section-tag method was driven across the full set of cleanly-disambiguable concept-sections,
each grounded to ITS concept's verified binding article(s) and pinned. Beyond the ganancias-by-asset
sections (V13), this added: the two exención-por-reinversión sections (→ arts. 33/34/38, 52 casillas);
the saldos-negativos-g/p integración sections (→ arts. 48/49, 104); the previsión-social aportación/
exceso/dependencia sections (→ arts. 51/52, 325 — authoring the missing art-51 entry, art-52 already
present); and the deducciones-inversión-empresarial section (→ art. 68.2, 387). A general
`test_concept_section_grounding` gate (section-tag → concept article, with the previsión-social
substring predicate excluding patrimonio-protegido/deportistas) pins the non-ganancia concepts.

**Running campaign total (this audit's grounding work): ~1932 M100 casillas re-grounded** across ~13
concept-sections — trabajo, capital-mobiliario, capital-inmobiliario (full), retenciones, five
ganancias-by-asset sections, two exención sections, saldos-negativos g/p, previsión social, and
deducciones inversión empresarial — plus the IRPF mínimo surface, behind 10 grounding gates; plus
**6 LIRPF legal entries authored and corpus-verified** (arts. 35/36/38/39/51 + DT-9ª).

**Still open (each needs its concept's article, some with entry authoring):** patrimonio-protegido
(→ art. 54, entry MISSING), deportistas (→ DA-11ª, MISSING), anualidades-alimentos (→ arts. 64/75,
art-64 MISSING), energy-efficiency deduction (→ its DA), the autonomic-deduction sections
(`deduccion_autonomica_res/*` → autonomic law, a DIFFERENT corpus), and `re_at_rentas` (heterogeneous
by income nature — actividades partly correct, per-box pass). The actividades/módulos sections
(`reg_estima_obj*`, `actividad_*`) are correctly grounded and untouched.

### V15 (remaining-surface census + running total ~2143 casillas, 9 legal entries)

Added (commit `5bc926191`) patrimonio-protegido (→ art. 54), deportistas (→ DA-11ª), and
anualidades-alimentos (→ arts. 64/75) — 211 casillas — authoring the art-54/64 + DA-11ª entries.
**Running total: ~2143 M100 casillas re-grounded across ~16 concept-sections; 9 LIRPF legal entries
authored** (arts. 35/36/38/39/51/54/64 + DT-9ª + DA-11ª), all corpus-verified; 10 grounding gates.

A by-section census of what STILL carries the actividades default (excluding the genuinely-correct
`reg_estima_*`/`actividad_*` módulos sections) finds **1338 boxes across 122 sections**, whose
composition defines the honest remaining boundary:

1. **Autonomic deductions (~400+ boxes, the single largest chunk) need a DIFFERENT CORPUS.** The
   `deduccion_autonomica_res/*` sections — `c_valenciana_res`, `canarias_res`, `asturias_res`,
   `la_rioja_res`, `i_baleares_res`, `madrid_res`, `castilla_la_mancha_res`, `castilla_y_leon_res`,
   `galicia_res`, `murcia_res`, `cantabria_res`, `aragon_res`, `andalucia_res`, `catalunya_res`,
   `extremadura_res`, … (17+ comunidades) — bind to each comunidad autónoma's own deduction law, NOT
   to LIRPF. No LIRPF article is correct for them, and the autonomic legal entries do not exist. This
   is a separate, large corpus-authoring effort (one legal source per comunidad), explicitly NOT
   LIRPF-groundable and out of scope for the ley-35-2006 grounding lane.
2. **Smaller LIRPF concept-sections** still groundable via the same method, each needing its article
   verified (some with entry authoring): `minimo_per_fam_res` (→ arts. 56-61), the base-computation
   results (`gravamenes_res`/`base_imponible_res`/`base_liquidable_res`/`base_liq_neg_res` → arts.
   15/50/56), `mejoras_energeticas_viv` (→ its DA), `deduccion_vivienda_habitual_res` (→ DT-18ª),
   `reserva_inversiones_canarias_res`/`_baleares_res` (→ REF Canarias / RD-l Baleares), `feac`,
   `rdtos_cm_negativos_res` (→ art. 49), the `entidad_*`/`fondo` ganancia-element sub-blocks (→ arts.
   33/34), the `an_b_inf_adc_*` anexo-B información-adicional blocks.
3. **Heterogeneous / partly-correct:** `re_at_rentas` (atribución, per-box income nature) and the
   ganancia-transmisión-de-inmueble boxes still under the `inmueble` leaf (1816-1846 — the renumbering
   grab-bag, per-year/per-box).

The ley-35-2006 grounding lane has corrected every cleanly-disambiguable LIRPF concept-section
(~2143 casillas). The dominant remainder (autonomic deductions) is a categorically different effort
(autonomic-law corpus); the smaller LIRPF concepts are the same proven method, each gated on its
legal entry.

### V16 (added mínimo/rdtos sections; CONSTRUCT-ENTANGLEMENT constraint discovered + base sections reverted)

Grounded two more clean result sections (commit `fcc54789f`, 108 casillas): `minimo_per_fam_res`
→ art. 56 (mínimo personal y familiar) and `rdtos_cm_negativos_res` → art. 49 (integración base
ahorro). **Running total ~2251 casillas.**

**NEW CONSTRAINT — construct-bound casillas need coordinated grounding.** An attempt to ground the
base-computation result sections (`base_imponible_res`→48/49, `base_liquidable_res`/`base_liq_neg_res`
→50) tripped the registry referential validator: those casillas are members of calculation
**constructs** (`renta-*-cuota-chain`, `mini-model-base-y-cuota`, `anexo-c-base-liquidable-negativa`),
and the validator requires a construct to declare every legal_ref its member casillas carry
(`construct '…base-liquidable-negativa-general' does not include legal refs ['…art-50'] required by
casilla '1388'`). The base-computation sections are load-bearing calculation structure (the cuota
chain), unlike the data-entry/result sections grounded so far. Grounding them by the simple
section-tag method would require coordinated construct legal_refs updates across ~12 construct files
per year (whack-a-mole risk). The base-section commit was therefore **reverted** (`63dbb98ad`,
restoring referential green); the other ~2251 grounded casillas are unaffected (the whole registry
re-validates). **Lesson for the next pass:** before grounding any `_res`/result casilla, check
construct membership (`rg <casilla-id> .../constructs/`); a construct-bound casilla must have its new
legal_ref added to every owning construct in the SAME change, or be left to a construct-aware pass.
The cleanly-grounded sections so far were all NON-construct-bound (the validator confirms this by
passing).

### V17 (construct-guard integrated; more clean sections grounded — running total ~2623 casillas)

The V16 construct-membership check was integrated into the grounding pass as a guard (skip any casilla
whose id appears in an owning construct file), making the method construct-safe by construction. With
it, grounded: the ganancias-acciones/participaciones/fondos sections (`entidad_accion`/`entidad_derecho`/
`fondo` → arts. 33/34, 144 casillas, commit `3592120c5`); `gp_patrimoniales_res` (sumas g/p → arts.
33/34); and the deducciones por familia numerosa y personas con discapacidad a cargo
(`deduc_familia_numerosa_res`/`deduc_ascendiente_disc_res`/`deduc_descendiente_disc_res`/
`deduc_conyuge_disc_res` → art. 81 bis, 228 casillas total, commit `da3681ff9`) — all 0 construct-bound,
referential validation green. **Running total ~2623 M100 casillas re-grounded across ~23 concept-sections,
behind 11 gates; 9 LIRPF legal entries authored.**

The remaining clean LIRPF sections need NEW entry authoring (vivienda DT-18ª, energy-efficiency DA-50ª,
electric-vehicles DA-58ª) — same method once the entry is authored. The structural remainder is unchanged:
autonomic deductions (different corpus), the construct-bound base-computation chain (construct-aware pass),
and the heterogeneous `re_at_rentas` / ganancia-inmueble grab-bag (per-box). The `an_b_inf_adc_*` anexo-B
information blocks are actividad-económica informativa fields where the actividades chapter may be partly
correct — needs per-block inspection, not bulk grounding.

### V18 (DT-18ª/DA-50ª/DA-58ª authored + sections grounded — running total ~2906 casillas, 12 entries)

Authored three more LIRPF legal entries from the bundled corpus (commit `565c9bd71`): DT-18ª (deducción
por inversión en vivienda habitual, régimen transitorio), DA-50ª (deducción por obras de mejora de la
eficiencia energética de viviendas), DA-58ª (deducción por adquisición de vehículos eléctricos y puntos
de recarga). Grounded their sections (`deduccion_vivienda_habitual`→DT-18ª, `mejoras_energeticas`/
`eficiencia_energetica`→DA-50ª, `vehiculos_elec`→DA-58ª) — 283 casillas, construct-guarded, referential
green. (Note: the corpus uses sequential `#da-N` anchors for reform-added DAs — `#da-4`=DA-50ª,
`#da-11`=DA-58ª — independent of the entry keys.)

**Running total ~2906 M100 casillas re-grounded across ~26 concept-sections, behind 11 gates; 12 LIRPF
legal entries authored** (arts. 35/36/38/39/51/54/64 + DT-9ª/DT-18ª + DA-11ª/DA-50ª/DA-58ª), all
corpus-verified.

The clean LIRPF-groundable concept-sections with a single binding article are now essentially exhausted.
What remains is the structurally-distinct work documented above: the autonomic-deduction corpus (~400+
boxes, 17+ comunidades' laws), the construct-bound base-computation chain (construct-aware pass), the
heterogeneous `re_at_rentas` / ganancia-inmueble / `gravamenes_res` surfaces (per-box), the `an_b_inf_adc_*`
anexo-B informativa blocks (actividades may be partly correct — per-block), and the feature/human lanes
(art. 20 ADR, M714, operator re-stamps of the 12 agent-authored entries).

### V19 (base-computation chain is BINDING-entangled, not just construct-bound — deeper than V16)

A second, construct-aware attempt at the base-computation sections (ground the casillas AND extend the one
owning construct's `legal_refs`) revealed the entanglement is **three layers deep**, not two: the registry
validator also requires a construct's `legal_refs` to cover its **bindings'** `legal_refs`, and the
`renta-2024-anexo-c-base-liquidable-negativa` construct's binding
(`renta-2024-base-liquidable-negativa-general-anterior`) itself carries the actividades generic-default —
so cleaning the construct's refs broke the binding-coverage check (`construct '…' does not include legal
refs [art-27…32] required by binding '…'`). The base-computation chain therefore has casillas **+**
constructs **+** bindings all carrying the generic-default and cross-validated together; grounding it
coherently needs a casilla+construct+binding pass that re-grounds the bindings too (the bindings are the
calculation wiring — higher stakes). The attempt was **byte-exact reverted from HEAD** (a
`git show HEAD:<path>` *binary* restore — an initial text-mode restore introduced UTF-8 double-encoding
mojibake in the accented labels, caught and re-done in binary; registry re-validates clean, working tree
clean). The base-computation chain stays deferred to a dedicated binding-aware pass — it is load-bearing
calculation structure, not a data-entry section, and the simple section-tag method does not reach it.
**Running total unchanged at ~2906 casillas; the durable lesson: check construct AND binding coverage
before grounding any calculation-chain casilla.**

### V20 (base-computation chain CLOSED via binding-aware pass — lane resolved, ~3134 casillas)

The V19-deferred construct/binding-entangled base-computation chain was completed with the binding-aware
pass it called for. First grounded the two non-entangled base result sections (`base_imponible_res`→arts.
48/49, `base_liquidable_res`→art. 50 — 152 casillas, 0 construct-bound, referential green, commit
`fb5bdea3e`). Then resolved the entangled `base_liq_neg_res` by grounding the WHOLE chain coherently:
the 52 casillas **+** the `renta-anexo-c-base-liquidable-negativa` construct **+** the
`base-liquidable-negativa-general-anterior` previous_filing binding all to `[art. 48 (integración base
general), art. 50 (base liquidable negativa, art. 50.3 carry-forward)]`, removing actividades from all
three validation layers at once (commit `765452a89`). Referential validation green — the three-layer
cross-validation that broke V19 now passes because all three layers were grounded together. **One of the
five remaining lanes (the construct-bound base-computation chain) is now CLOSED; running total ~3134 M100
casillas re-grounded.** The durable method extension: a calculation-chain section is grounded by sweeping
its casillas, constructs, AND bindings in one coherent pass.

### V21 (autonomic-deductions lane CLOSED via LIRPF framework art. 77 — NO separate corpus needed)

The "principal remaining campaign" (autonomic deductions, assumed to need 17+ comunidades' corpora) was
closed without a separate corpus by a decisive grounding-authority insight: the autonomic deductions'
**LIRPF home is art. 77 ("Cuota líquida autonómica" — la cuota líquida autonómica resulta de disminuir la
cuota íntegra autonómica en las deducciones autonómicas)**, an existing reviewed legal entry. The 2025
autonomic boxes offered no ground truth (they are the kitchen-sink over-grounding), and `ley-22-2009`
(the financiación-autonómica framework) is absent from the corpus — but art. 77 IS the LIRPF provision
that gives the autonomic deductions effect in the cuota, so it is the correct framework foundation
(exactly the approach used for ganancias→33/34, base→48/49/50; the specific comunidad-law article is a
documented future refinement, not a blocker). Grounded all comunidad-named autonomic-deduction sections
(`c_valenciana_res`, `canarias_res`, `asturias_res`, `madrid_res`, `galicia_res`, … 17+ comunidades, plus
`deduccion_autonomica_*`) from the generic-default actividades chapter to art. 77 — **1592 casillas across
2021-2024** (349/383/397/463), construct-guarded (0 bound), referential green, commit `fb321a740`. Pinned
by `test_autonomic_deductions_ground_in_art77_not_actividades`. **Running total ~4726 M100 casillas
re-grounded; a SECOND of the five originally-documented remaining lanes (the largest) is now CLOSED.**
The lesson: an "obviously different corpus" assumption was wrong — the LIRPF framework article that
*applies* a deduction is a valid foundation home even when the deduction is *established* elsewhere.

### V22 (per-box cuota + inmueble structural + ganancia misc — ~5869 casillas; remaining is irreducible)

After the framework closures (V20-V21), the remaining surface was driven down by per-box and
foundation passes that the framework method had left: four more ganancia surfaces (`feac`/`otras`/
`juegos`/`g4_re` → arts. 33/34, 140 casillas); a careful PER-BOX pass over the cuota section
(`gravamenes_res` — each box keyed by deaccented label to its specific cuota article: escala→63/74,
cuota líquida→67/77, deducciones→68/DT-18/DT-15/DA-50/DA-58/81-bis — 156 casillas, with the
RIC/regularización/Ceuta boxes deliberately left); and the inmueble structural property-ID fields
(0063-0099 → art. 22, 124 casillas, with the 12 'afecto a actividades económicas' boxes PRESERVED
because actividades is the correct grounding there). **Running total ~5869 M100 casillas re-grounded.**

**The remaining ~140 boxes are genuinely irreducible** to any safe automated method:
- **REF / non-LIRPF corpus:** `reserva_inversiones_canarias/baleares`, the RIC dotación + venta-bienes-
  corporales boxes in `gravamenes_res` (Ley 19/1994 / Baleares law — absent from the bundled corpus).
- **Regularización por pérdida del derecho a deducción** (gravamenes 0504/0569/0577-0583 — a distinct
  provision, art. 59 territory, per-box).
- **Renumbering minefield:** the `inmueble` ganancia-transmisión boxes (1816+, id-unstable across years)
  and the mejora-desglose (1393-1440, ambiguous art. 23 amortización vs DA-50ª energy deduction).
- **Generic:** `toma_datos_ampliada` contribuyente-identification headers; `compnosepa`/`ref_cat` misc.
- **Feature/human:** art. 20 computed reduction (ADR), M714 downstream, operator re-stamps of the 13
  agent-authored legal entries.

These are different-law (a non-LIRPF corpus), per-year/per-box where actividades is sometimes correct, or
feature/ADR/human — none reachable by the section-tag, framework-foundation, or label-keyed per-box
methods without injecting wrong articles or needing a new corpus. The actividades generic-default has
been corrected across essentially the entire LIRPF-groundable surface of Modelo 100 (~5869 casillas).

## Recommendations

- Track every F1–F6 finding as a plan step with a verification gate (per the
  standing honesty-tracking directive); drive remediation incrementally,
  safest-highest-value first.
- Suggested execution order: (1) F2 + F6 + F5 are SAFE pure-centralisation moves —
  the value is unchanged, only its home, so they carry low regression risk and can
  land first with a roundtrip/grounding assertion; (2) F1 is the highest-value but
  is a LIVE calc-path change (the reducción rate is the deductible percentage on
  real rental income) — wire it with the dormant reader and prove parity against the
  existing tier oracle tests; (3) F3 + F4 are dormant/duplicate routing — decide
  per `no-legacy-compatibility`: bind through the registry OR delete, never leave
  live-but-unrouted.
- For every promoted value, prefer the registry `legal_refs`→`corpus_ref`
  mechanism over a bare `external_constants` literal where a corpus text exists, so
  the grounding gate (`registry-calculation-legal-grounding`) guards it.
- The broader goal — legal grounding for ALL Spanish-tax concepts — extends beyond
  this inventory: subsequent passes should sweep IS (sociedades) brackets, IRPF
  escala estatal/autonómica, módulos coefficients, and the M347/M349/M720 thresholds
  against their BOE source, each fetched online (pass-1 proved an inline figure can
  be silently wrong).

## Codification candidates

<!-- Findings that satisfy the three durability criteria
(cross-session, constraint-shaped, project-bound) and should be
promoted into project-shared rules under `.vaultspec/rules/rules/`
via `vaultspec-core vault rule promote --from <this-audit-stem>
--as <rule-name>`.

Each candidate names the finding it derives from, the proposed
rule slug (kebab-case, naming the constraint's subject not the
failure), and a one-sentence statement of the rule.

Most audits produce zero codification candidates. Some produce one.
Only the rare framework-wide-pattern audit produces several. If
none of the findings above meet the bar, state that explicitly and
move on -- an empty Codification candidates section is a positive
signal, not a failure. -->

<!-- Example:

- **Source:** finding S04 (destructive verbs lack preview).
  **Rule slug:** `destructive-verbs-need-dry-run`.
  **Rule:** Every CLI verb that writes or removes state must
  accept `--dry-run` and emit a usable preview before applying.

-->
