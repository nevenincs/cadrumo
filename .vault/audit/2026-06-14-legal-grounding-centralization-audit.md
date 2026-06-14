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
