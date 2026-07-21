---
tags:
  - "#audit"
  - "#aeat-grounding-completion"
date: '2026-06-14'
related:
  - "[[2026-06-14-aeat-grounding-completion-plan]]"
promoted_to:
  - 'rule:legal-grounding-verifies-bundled-authoritative-corpus'
modified: '2026-06-29'
---

# `aeat-grounding-completion` audit: `Campaign-Close Honesty Review — Centralization + Grounding`

## Scope

Fresh-context campaign-close honesty review (per `aeat-campaign-close-honesty-review`)
dispatched on the completed centralization remediation plan (7/7) and the
grounding-completion W01.P01 módulos build. An independent code-reviewer agent read each
substantive commit, verified claims against the bundled corpus + tests, and reported
what is wrong / missing / unverified. This document persists its findings and their
resolution.

## Findings

### C1 (CRITICAL — FIXED) — DT 32ª agent-authored corpus had a fabricated year-list

The W01.P01 módulos build (`47b903cd5`) authored a NEW DT 32ª corpus excerpt from a
secondary source with the year-list "...2025 y 2026". The repository ALREADY bundles the
authoritative consolidated LIRPF (`corpus/normatives/html/ley-35-2006.html`
`#dttrigesimasegunda`), whose real DT 32ª reads "en los ejercicios 2016 a 2024" and
records that the 2025/2026 extensions (RD-ley 9/2024, 16/2025, 2/2026) were each DEROGADAS
by Congreso acuerdos (BOE-A-2026-4667). The agent year-list was wrong, and the corpus
cross-check was tautological (agent wrote both the `required_text` and the corpus).
**Resolution:** repointed `corpus_ref` to the authoritative bundled corpus
(`ley-35-2006.html#dttrigesimasegunda`), corrected the scope to 2016-2024, flagged the
2025/2026 derogation in the legal entry + all three parameter notes (a consumer must gate
on filing year and treat 2025+ as unresolved), deleted the orphaned agent excerpt. The
strict cross-check now validates against the real bundled BOE text (non-tautological);
the parameter values (250000/125000/250000) and article mapping were faithful and stand.
56 corpus/catalogue tests pass.

### H1 (HIGH — FIXED) — incomplete citation sweep, 6 stragglers

The citation campaign (`3281d2024`, `50e9adaa6`) corrected the primary sites but left six
docstring/comment stragglers with the old wrong articles: `_descendant_facts.py:157`
(Art. 59→61), `test_external_constants_centralisation_part1.py:435` (art. 31.1→33.1),
`test_descendant_info.py:236` (Art. 58.3→58.2), and `test_custodia_compartida.py` ×3
(Art. 59→61). The corrected provisions were verified legally correct by the reviewer.
**Resolution:** all six swept to the correct articles; 129 affected tests pass.

### M1 (MEDIUM — FIXED) — F3 `available` extra-probe contradicted the "exactly preserving" claim

`_iva_compensation_history.py` routed the semantic-only `iva.compensacion-disponible-fin-periodo`
casilla through the registry resolver, adding a second probe key vs the original
single-probe. That casilla has no numeric AEAT box, so it was never an inline-number
routing literal (the finding's target). **Resolution:** reverted it to the direct
single-probe `_casilla_value` lookup — behaviour-preserving and correct.

### M2 (MEDIUM — CLOSED 2026-06-29) — EO exclusion parameters now feed the advisory gate

The módulos magnitudes are now consumed by
`src/aeat/application/modelo/_objective_estimation_advisory.py`. The advisory reads the
current structured profile inputs
`objective_estimation_prior_year_gross_income_eur`,
`objective_estimation_prior_year_invoice_gross_income_eur`,
`objective_estimation_prior_year_agri_livestock_forest_gross_eur`, and
`objective_estimation_prior_year_purchases_eur`; emits Modelo 100/131 advisory findings
inside the official 2016-2026 scope; and carries the relevant legal refs from the
parameter grounding. The no-legacy cleanup also retired the old
`uses_objective_estimation_irpf` input surface: objective-estimation routing is now driven
by `irpf.estimation_regime`, and Modelo 131 deadline windows predicate on
`irpf.estimation_regime == "objetiva"`. Focused tests include
`test_objective_estimation_exclusion_advisory.py` and the profile/deadline coverage in the
2026-06-29 focused run.

### L1 / N1 (LOW / NIT — awareness only) — F4 process + registry-load nit

L1: F4 (`69d3ecd50`) landed with three `application/calculations` test helpers red, fixed
in the follow-up `0ab778724` — net HEAD green, flagged as a clean-collection process note.
N1: `_casilla_id_to_number` loads the whole registry tree (lru-cached, off hot path) to
resolve ~7 box numbers — acceptable.

### W02 current-state verification (C1-lesson applied) — rate gaps closed in registry

Applying the C1 lesson (check the bundled authoritative corpus before authoring), the
remaining grounding-completion steps were re-verified against the current registry:

- **W02.P03 (IS ERD INCN<10M schedule):** 2026-06-29 current-state verification closes
  this blocker. The legal catalogue now includes reviewed entries for
  `ley-27-2014:dt-44` and `ley-27-2014:art-101`; the Modelo 200 parameter registry
  declares `is.modelo-200.tipo-gravamen-erd-art101` and
  `is.modelo-200.cuota-integra-bracket-erd-art101`; and the Art.101 schedule is encoded
  for INCN below 10M and at least 1M as 25 (2024), 24 (2025), 23 (2026), 22 (2027), 21
  (2028), and 20 (2029). `formulas.toml` routes general-rate Art.101 forms through those
  parameters, and the completeness manifest carries both legal refs. Focused tests include
  `test_modelo_200_tipo_gravamen_dispatch.py` and
  `test_modelo_200_cuota_integra_lanes.py`.
- **W02.P04 (M200 casilla 00558 two-tranche echo):** 2026-06-29 current-state
  verification closes this blocker. The registry now declares
  `is.modelo-200.tipo-gravamen-pyme-display` with dated scalar echo values 23
  (2024), 21 (2025), and 19 (2026), and the `DP200014:00558` formula routes
  micro-empresa general forms to that display parameter. The cuota remains
  bracket-derived through `DP200014:00562`, so the trust/export echo changed
  without weakening tax arithmetic. Focused tests passed:
  `test_modelo_200_tipo_gravamen_dispatch.py` (18 passed),
  `test_modelo_200_cuota_integra_lanes.py` (14 passed), and
  `test_modelo_200_temporal_coverage.py` (7 passed).
- **W01.P02 (módulos advisory gate):** 2026-06-29 current-state verification closes this
  step. The user-profile schema now exposes the declared volume inputs, the advisory gate
  consumes them, and tests prove the gate fires for official 2025/2026 AEAT scope while it
  does not project beyond the supported scope. The path is advisory-only and legally
  grounded; it is no longer represented as a hard filing block.

These are current registry/application closures, not historical backfills. The C1 lesson
still stands: future legal authoring must use bundled authoritative corpus evidence or
honestly mark a non-authoritative anchor; secondary-source text must not become fabricated
corpus.

### Verified-sound (honest green surface)

The reviewer independently confirmed: F4 binding selectors correct (rate_kind=zero does not
drop observations; production resolves via the mesh, non-tautological 5000/3000 test); F4
completeness-manifest edit consistent; F3 behaviour-preserving for every box number (zero
cross-revision conflicts); F1 tier-resolver parity-preserving with a non-tautological
causality proof; all landed citation fixes legally correct. The earlier F2 prorrata
deferral statement is superseded by the 2026-06-29 legal-grounding-centralization V33
currentization: the exported application prorrata wrapper is deleted, while the domain
IVA prorrata substrate remains for validated ledger prorrata references. Clean
`--collect-only` (15467, 0 errors).

## Recommendations

- C1/H1/M1 fixed this pass. M2/W01.P02, W02.P03, and W02.P04 are closed in the current
  registry/application state: módulos exclusion is surfaced as an advisory grounded in
  declared volume inputs, the Art.101 ERD schedule is encoded separately from the
  micro-empresa lane, and the M200 scalar echo now matches the two-tranche display policy.
- Operator action: re-stamp the now-grounded DT 32ª / AEAT-manual source split after
  confirming the 2016-2026 advisory scope and the 2025/2026 handling.
- Lesson for future grounding work: always check the bundled authoritative corpus
  (`ley-35-2006.html` etc.) BEFORE authoring a new excerpt from a secondary source — the
  authoritative consolidated text is already shipped and is the faithful source.

## Codification candidates
