---
tags:
  - '#research'
  - '#tributacion-conjunta-individual'
date: '2026-06-30'
modified: '2026-07-17'
related: []
---

# `tributacion-conjunta-individual` research: `tributacion conjunta vs individual comparison surface`

Issue #547 (P1, NEEDS-DESIGN) asks for a surface that computes a Modelo 100 filing under both tributacion conjunta and individual and reports the favorable one. The headline finding reverses the issue premise: a fully-wired comparison surface already exists at HEAD. This research reconciles the issue against HEAD, isolates which axes exist versus which are missing, and scopes the genuinely-open design question.

## Headline: the comparator already exists at HEAD (committed, not WIP)

- Application core: `src/aeat/application/modelo/_taxation_comparison.py` runs the registry formula engine twice over identical inputs, injecting `declaration_type=2` (conjunta) and `declaration_type=1` (individual), then diffs the result casillas. Returns a typed frozen `TaxationComparisonResult` (both cuota resultante 0595, both resultado 0610, signed `delta_resultado`, `TaxationRecommendation` StrEnum {conjunta, individual, indifferent} with a 1 EUR materiality threshold). Errors via `TaxationComparisonError`.
- CLI verb: `aeat app modelo work compare-taxation [WORK_UNIT_ID] [--modelo/--year/--period/--revision/--bucket-id]` in `src/aeat/entrypoints/cli/_modelo.py` (registered on the `work_app` group). Resolves a work address, calls `compare_taxation_for_work_address`, emits a `WorkCompareTaxationResult` envelope.
- Payload schema: `WorkCompareTaxationResult` registered under `modelo.work.compare_taxation` in `src/aeat/entrypoints/cli/_payloads_modelo_reconcile.py`.
- Tests: `src/aeat/application/modelo/tests/test_taxation_comparison.py` (behavioural oracle: high-disparity 52000+0 and a 45000 single-earner both recommend CONJUNTA; typed structure; error-registry membership). Semantic-role resolution tested in `test_semantic_role_resolution.py`.
- Locales: keys present in all four catalogues (en/es/ca/hu.yml).
- Status: all four files are committed and clean (git status empty for them). Not peer WIP. Landed via the filing-workflow restructure line (history: fc0173d6b, bde0c27fb). Origin recommendation: audit `2026-05-27-marcos-cli-testimonial-audit` (Recommendation 3, "Conjunta vs individual comparator", which even named the compare-taxation verb).

## Decision-relevant axis inventory (what exists vs what is missing)

### Modalidad axis + Art. 84 reduccion: EXISTS

- Declaration-type binding exists: `renta-2025-profile-declaration-type`, selector profile_key `filing_export.n`, xsd_attribute `TIPOTRIBUTACION`. Value 2 = conjunta, 1 = individual. No new core enum axis is needed; the comparator injects the value directly.
- Reduccion Art. 84 exists as a registry formula: M100 2025 `formulas/0179-renta-2025-reduccion-art-84-conjunta.toml` targets casilla 0461. Logic: declaration_type==2 AND family-minor-children-in-unit==0 gives 3400; ==1 child gives 2150; individual gives 0. legal_refs = [ley-35-2006:art-82, :art-83, :art-84]; source_refs include the DR-100-2025 dictionary and the 2025 manual. A parallel 0176 formula exists for 2024.
- Figure confirmation vs bundled corpus: the bundled AEAT Renta manuals (corpus/manuals/renta/2022..2025/part1) state 3.400 EUR for modalidad 1 (ambos conyuges, Art. 82.1.1) and 2.150 EUR for modalidad 2 (monoparental, Art. 82.1.2). Both match the registry formula. These are the long-standing LIRPF Art. 84.2 amounts. reviewed_by is honestly agent-prepared and grounded in the bundled manuals plus the formula source_citations; an operator cross-check against consolidated BOE Art. 84 is the finishing step (per legal-grounding-verifies-bundled-authoritative-corpus, a numeric amount is confirmed against live BOE even when the bundled corpus already states it).

### Household / spouse identity axes: EXIST; spouse INCOME axis: MISSING

- Spouse IDENTITY bindings exist (2025): spouse tax_id, display name, birth_date, sex, disability grade, non-resident IRPF, EU/EEA residence (bindings 0013..0020-renta-2025-profile-spouse-*, gated required_when_value 2). Marriage bindings exist: profile-marriage-full-year, month-start, month-end. Family axis exists: profile-family-minor-children-in-unit.
- Spouse INCOME axis does NOT exist. A search for any spouse-income / two-return / income-split binding or field returns nothing. The profile carries the spouse identity for the conjunta return header but not the spouse separately-attributable income.

### Overview discoverability: NO hook today

- `src/aeat/application/overview/` (status/explain/calendar/backlog/agenda) does not reference conjunta, unidad familiar, or the compare-taxation verb. A married taxpayer is not nudged toward the comparator; it must be known and invoked explicitly.

## The genuinely-open gap: single-return model, not a two-return income split

`compare_taxation_modes` runs the SAME inputs under both declaration types. This correctly models the ONE-RETURN case (a single-earner unidad familiar), where individual filing is one return on the earner income and conjunta is that same income minus the Art. 84 reduccion, so conjunta wins whenever income is positive (both shipped oracle tests confirm CONJUNTA). It does NOT model genuine two-earner individual filing, where individual means TWO separate declarations, each on that spouse own income, summed and compared against the single conjunta return. Because the engine evaluates a single return and there is no spouse-income axis, the comparator cannot represent the case where individual is actually cheaper (two mid-range salaries whose combined conjunta base climbs into a higher tarifa bracket that the 3.400 reduccion does not offset). The top-of-file test docstring describes an equal-income to individual scenario, but no such test is implemented; the shipped second test is a single-earner 45000 case recommending CONJUNTA. The individual branch is therefore only faithful for one-earner units today.

## Calc-path integrity (one-aggregation-path)

The comparator reuses the shared registry engine core (`calculate_registry_snapshot`); it does NOT fork formula evaluation, so the arithmetic authority is single-sourced. `compare_taxation_for_work_unit`, however, assembles resolved inputs with a locally-built path (`_resolve_declaration_period_inputs` plus `resolve_available_bound_inputs_by_casilla_id`; its own docstring notes it mirrors calculate_modelo_revision). That input-assembly parallelism is a drift risk relative to the live calculate path (one-aggregation-path-pull-equals-calculate): if the calculate path changes how bound inputs are assembled, the comparator can silently diverge. Consolidating both onto one input-assembly helper is the clean form.

## Constraints that bind the decision

- aeat-safety-legal-gates: the comparator is advisory/calc-only, no live submission; the current ephemeral (no-persist) design already honours this.
- aeat-architecture-boundaries: two-root CLI; compare-taxation sits under `app modelo work`, correct. Closed value sets are core StrEnums (`TaxationRecommendation` already is).
- cli-notices-are-the-only-diagnostic-channel: the which-is-better recommendation is primary result data (the command exists to produce it), analogous to allowed verify findings; legitimate as a result field. But a cross-surface nudge (overview advising a married taxpayer to run the comparator) MUST ride the typed Notice channel, not a bespoke result field.
- one-aggregation-path-pull-equals-calculate: see calc-path integrity above.

## Sources

- Code: `_taxation_comparison.py`, `_modelo.py:641-769`, `_payloads_modelo_reconcile.py:65-88`, `tests/test_taxation_comparison.py`.
- Registry: M100 2025 formulas/0179 art-84-conjunta, bindings/0009 declaration-type, bindings/0013..0020 spouse, bindings/0024 family-minor-children-in-unit.
- Corpus: _data/corpus/manuals/renta/2022..2025/part1/source.pdf.extracted.md (3.400 / 2.150 confirmation).
- Vault: audit `2026-05-27-marcos-cli-testimonial-audit` (origin recommendation).
