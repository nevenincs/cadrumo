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
