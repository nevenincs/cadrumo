---
tags:
  - '#plan'
  - '#deadline-window-revision-authority'
date: '2026-08-24'
tier: L3
related:
  - '[[2026-08-24-deadline-window-revision-authority-adr]]'
  - '[[2026-08-24-deadline-window-revision-authority-research]]'
  - '[[2026-08-24-deadline-window-revision-authority-reference]]'
  - '[[2026-07-09-m210-plazo-keying-adr]]'
  - '[[2026-08-14-registry-temporal-coverage-adr]]'
  - '[[2026-08-14-registry-temporal-coverage-authority-grade-coverage-adr]]'
  - '[[2026-08-14-registry-temporal-coverage-plan]]'
modified: '2026-08-25'
body_hash: 'sha256:d536687eba8b1aa1a8ebea9d05947763da147d1de370fe6e4ac7029cca0eaeca'
---

<!-- RETIRED: P06, P07, P09 -->

# `deadline-window-revision-authority` plan

## Description

Implement deadline windows as revision-owned law facts through the existing temporal
registry authority. Reuse `select_revision`, `Period`, `registry_period_kind`,
`ValidatedRegistryAuthority.deadline_windows`, and `resolve_filing_window`. Add no
parallel revision selector, period parser, cadence map, deadline catalogue, horizon, or
downstream deduplication.

Periodic completeness consumes the registry-temporal-coverage campaign's single
supported-filing-year projection. M210 retains `EVENT-N`/`0A` identity, reuses
`ResultDisposition`, and preserves registry-backed official two-digit tipo-renta codes;
the many-to-one `TipoRentaIrnr` concept projection is not a deadline identity.

## Steps

## Wave `W01` - canonical authority contract

Establish deadline semantic identity, exact-one revision ownership, and supported-year completeness through existing temporal and period authorities.

### Phase `W01.P01` - shared temporal and identity contract

Type deadline identity through existing canonical vocabularies and shared temporal coverage.

- [x] `W01.P01.S01` - Record the canonical shared temporal-coverage dependency in the approved deadline architecture; `.vault/adr/2026-08-24-deadline-window-revision-authority-adr.md`.
- [x] `W01.P01.S02` - Add optional typed deadline qualifiers reusing ResultDisposition and official M210 tipo-renta code authority without a lossy TipoRentaIrnr projection; `src/cadrumo/domain/calculations/registry/_schema.py`.
- [x] `W01.P01.S03` - Define the canonical deadline semantic coordinate from modelo, Period, ResultDisposition, and official tipo-renta code scope using existing period authorities; `src/cadrumo/domain/calculations/registry/`.
- [x] `W01.P01.S04` - Extend deadline-window loading and serialization for typed qualifiers while preserving unqualified rows and fragmented authoring ownership; `src/cadrumo/domain/calculations/registry/_loader.py; src/cadrumo/domain/calculations/registry/tests/`.

### Phase `W01.P02` - ownership and completeness gates

Fail registry construction on identity, ownership, uniqueness, and periodic completeness defects.

- [x] `W01.P02.S05` - Enforce equality between deadline filing_year and Period.filing_year while preserving following-calendar-year physical dates; `src/cadrumo/domain/calculations/registry/; src/cadrumo/domain/calculations/registry/tests/`.
- [x] `W01.P02.S06` - Enforce globally unique deadline IDs and semantic coordinates across every revision with independent bite tests; `src/cadrumo/domain/calculations/registry/; src/cadrumo/domain/calculations/registry/tests/`.
- [x] `W01.P02.S07` - Enforce exact-one deadline ownership through canonical select_revision including period-sensitive cutovers; `src/cadrumo/domain/calculations/registry/_validate_revision_rules.py; src/cadrumo/domain/calculations/registry/tests/`.
- [x] `W01.P02.S09` - Prove deadline validation under cold construction and fingerprint-backed warm-load verdict paths with planted mutations; `src/cadrumo/domain/calculations/registry/tests/`.

## Wave `W02` - officially grounded corpus repair

Repair every affected registry row and complete officially grounded schedules without runtime masking.

### Phase `W02.P03` - annual information-return identity repair

Correct following-January annual identity without altering physical filing dates.

- [x] `W02.P03.S10` - Re-adjudicate and repair Modelo 190 deadline identity against bundled and official AEAT authority while retaining following-January physical dates; `src/cadrumo/_data/registry/aeat/modelos/190/`.
- [x] `W02.P03.S11` - Re-adjudicate and repair Modelo 193 deadline identity against bundled and official AEAT authority while retaining following-January physical dates; `src/cadrumo/_data/registry/aeat/modelos/193/`.

### Phase `W02.P04` - periodic IVA schedule repair

Remove stale copies and complete every officially supported periodic schedule.

- [ ] `W02.P04.S12` - Re-adjudicate Modelo 303 deadlines for every supported filing year 2022-2026, remove every non-owner copy, preserve the 2024 cutover, and materialise all 22 measured missing monthly and quarterly cells only from bundled official-source evidence, using Vaultspec RAG plus exact-symbol confirmation to prove no selector, resolver, parser, cadence authority, horizon, or deadline catalogue is redeclared and never inferring a date; `src/cadrumo/_data/registry/aeat/modelos/303/`.
- [ ] `W02.P04.S13` - Re-adjudicate Modelo 322 deadlines for every supported filing year 2022-2026, remove stale copies, and materialise all 42 measured missing periodic cells only from bundled official-source evidence, using Vaultspec RAG plus exact-symbol confirmation to prove no selector, resolver, parser, cadence authority, horizon, or deadline catalogue is redeclared and never inferring a date; `src/cadrumo/_data/registry/aeat/modelos/322/`.
- [ ] `W02.P04.S14` - Re-adjudicate Modelo 353 deadlines for every supported filing year 2022-2026, remove stale copies, and materialise all 37 measured missing periodic cells only from bundled official-source evidence, using Vaultspec RAG plus exact-symbol confirmation to prove no selector, resolver, parser, cadence authority, horizon, or deadline catalogue is redeclared and never inferring a date; `src/cadrumo/_data/registry/aeat/modelos/353/`.
- [x] `W02.P04.S15` - Re-adjudicate Modelo 369 deadlines for every supported filing year 2022-2026 and materialise all 60 measured missing periodic cells only from bundled official-source evidence, using Vaultspec RAG plus exact-symbol confirmation to prove no modelo-specific selector, resolver, parser, cadence authority, horizon, or deadline catalogue is redeclared and never inferring a date; `src/cadrumo/_data/registry/aeat/modelos/369/`.
- [ ] `W02.P04.S16` - Generate an auditable 555-cell before-and-after census for supported filing years 2022-2026 that accounts for all 294 measured missing cells and every removed, corrected, retained, materialised, or still-blocked deadline coordinate with its official source, reconciling M369 60, M111 48, M322 42, M353 37, M349 32, M303 22, M115 16, M123 12, M202 9, M130 8, M131 4, and M216 4 exactly; `dev/; .vault/audit/`.

### Phase `W02.P05` - Modelo 210 qualified plazo repair

Complete M210 using canonical periods, ResultDisposition, and official tipo-renta codes.

- [x] `W02.P05.S17` - Re-adjudicate every Modelo 210 plazo case against bundled Orden EHA 3316/2010 article 5 and official authority including presentation versus domiciliacion; `src/cadrumo/_data/registry/aeat/modelos/210/`.
- [x] `W02.P05.S18` - Replace invalid M210 quarter identities with canonical EVENT-N or 0A identities and author ResultDisposition plus official-code-qualified variants; `src/cadrumo/_data/registry/aeat/modelos/210/revisions/`.
- [x] `W02.P05.S19` - Keep M210 tipo 28 event-shaped without a numeric offset until RD 1776/2004 article 14 is bundled and verified; `src/cadrumo/_data/registry/aeat/modelos/210/; src/cadrumo/_data/registry/aeat/legal/`.
- [x] `W02.P05.S20` - Prove M210 qualifiers accept canonical ResultDisposition and official codes while rejecting lossy conceptual tipo authoring; `src/cadrumo/domain/calculations/registry/tests/`.

### Phase `W02.P14` - remaining periodic fleet corpus repair

Complete the measured non-IVA periodic corpus for supported filing years 2022-2026 from official sources, with one canonical-authority redeclaration audit per modelo.

- [x] `W02.P14.S37` - Re-adjudicate Modelo 111 deadlines for supported filing years 2022-2026 and materialise all 48 measured missing periodic cells only from bundled official-source evidence, using Vaultspec RAG plus exact-symbol confirmation to prove no selector, resolver, parser, cadence authority, horizon, or deadline catalogue is redeclared and never inferring a date; `src/cadrumo/_data/registry/aeat/modelos/111/`.
- [x] `W02.P14.S38` - Re-adjudicate Modelo 115 deadlines for supported filing years 2022-2026 and materialise all 16 measured missing periodic cells only from bundled official-source evidence, using Vaultspec RAG plus exact-symbol confirmation to prove no selector, resolver, parser, cadence authority, horizon, or deadline catalogue is redeclared and never inferring a date; `src/cadrumo/_data/registry/aeat/modelos/115/`.
- [x] `W02.P14.S39` - Re-adjudicate Modelo 123 deadlines for supported filing years 2022-2026 and materialise all 12 measured missing periodic cells only from bundled official-source evidence, using Vaultspec RAG plus exact-symbol confirmation to prove no selector, resolver, parser, cadence authority, horizon, or deadline catalogue is redeclared and never inferring a date; `src/cadrumo/_data/registry/aeat/modelos/123/`.
- [x] `W02.P14.S40` - Re-adjudicate Modelo 130 deadlines for supported filing years 2022-2026 and materialise all 8 measured missing periodic cells only from bundled official-source evidence, using Vaultspec RAG plus exact-symbol confirmation to prove no selector, resolver, parser, cadence authority, horizon, or deadline catalogue is redeclared and never inferring a date; `src/cadrumo/_data/registry/aeat/modelos/130/`.
- [x] `W02.P14.S41` - Re-adjudicate Modelo 131 deadlines for supported filing years 2022-2026 and materialise all 4 measured missing periodic cells only from bundled official-source evidence, using Vaultspec RAG plus exact-symbol confirmation to prove no selector, resolver, parser, cadence authority, horizon, or deadline catalogue is redeclared and never inferring a date; `src/cadrumo/_data/registry/aeat/modelos/131/`.
- [x] `W02.P14.S42` - Re-adjudicate Modelo 202 deadlines for supported filing years 2022-2026 and materialise all 9 measured missing periodic cells only from bundled official-source evidence, using Vaultspec RAG plus exact-symbol confirmation to prove no selector, resolver, parser, cadence authority, horizon, or deadline catalogue is redeclared and never inferring a date; `src/cadrumo/_data/registry/aeat/modelos/202/`.
- [x] `W02.P14.S43` - Re-adjudicate Modelo 216 deadlines for supported filing years 2022-2026 and materialise all 4 measured missing periodic cells only from bundled official-source evidence, using Vaultspec RAG plus exact-symbol confirmation to prove no selector, resolver, parser, cadence authority, horizon, or deadline catalogue is redeclared and never inferring a date; `src/cadrumo/_data/registry/aeat/modelos/216/`.
- [ ] `W02.P14.S44` - Re-adjudicate Modelo 349 deadlines for supported filing years 2022-2026 and materialise all 32 measured missing periodic cells only from bundled official-source evidence, using Vaultspec RAG plus exact-symbol confirmation to prove no selector, resolver, parser, cadence authority, horizon, or deadline catalogue is redeclared and never inferring a date; `src/cadrumo/_data/registry/aeat/modelos/349/`.

### Phase `W02.P15` - fleet periodic completeness hard gate

After every source-grounded fleet corpus repair and its reconciled census, activate the canonical supported-year completeness invariant as the final corpus gate before projection and consumer work.

- [ ] `W02.P15.S08` - After corpus Steps S12-S16 and S37-S44 complete, consume the canonical temporal-coverage supported-year projection and hard-fail incomplete periodic deadline cadence across all 559 expected 2022-2026 cells without a second horizon or cadence map, keeping this completeness gate last and proving it bites on a planted missing cell; `src/cadrumo/domain/calculations/registry/; src/cadrumo/domain/calculations/registry/tests/`.

## Wave `W03` - canonical projection and resolution

Project only validated owning rows and share one exact filing-window matcher.

### Phase `W03.P08` - registry authority projection

Correct the authority projection without runtime deduplication.

- [x] `W03.P08.S21` - Rewrite ValidatedRegistryAuthority.deadline_windows to project canonical owners through select_revision with deterministic qualifier-aware ordering and no deduplication; `src/cadrumo/domain/calculations/registry/_authority.py`.
- [x] `W03.P08.S22` - Add a fleet authority test proving canonical ownership, exact multiplicity, qualifier distinction, and modelo-filter invariance; `src/cadrumo/domain/calculations/registry/tests/`.

### Phase `W03.P10` - filing-window resolution

Extend the existing resolver for exact-one qualified matching.

- [x] `W03.P10.S23` - Extend resolve_filing_window with optional ResultDisposition and official tipo-code context using one exact matcher and ambiguity refusal; `src/cadrumo/domain/deadlines/_plazo.py`.
- [x] `W03.P10.S24` - Keep resolve_filing_closes_on as the unqualified convenience and route post-calculation M210 plazo through the same matcher; `src/cadrumo/domain/deadlines/_plazo.py`.
- [x] `W03.P10.S25` - Prove qualified resolution wildcard and exact scopes, official-code distinction, ambiguity refusal, and no year borrowing; `src/cadrumo/domain/deadlines/tests/`.

### Phase `W03.P11` - engine and M210 projection

Keep the engine thin and resolve resultado-aware M210 deadlines post-calculation.

- [x] `W03.P11.S26` - Keep DeadlineEngine.compute thin and prove exact-one complete monthly and quarterly emission without local selection or deduplication; `src/cadrumo/domain/deadlines/_engine.py; src/cadrumo/domain/deadlines/tests/test_engine.py`.
- [x] `W03.P11.S27` - Route calculated M210 ResultDisposition and official tipo code into canonical deadline resolution and the existing typed Notice channel; `src/cadrumo/application/modelo/`.
- [x] `W03.P11.S28` - Prove M210 calculate and verify envelopes emit grounded qualified plazo notices and never claim an ungrounded tipo-28 offset; `src/cadrumo/application/modelo/tests/`.

## Wave `W04` - consumer parity and closure

Prove every operator surface inherits canonical authority and close with formal review.

### Phase `W04.P12` - overview workflow and CLI parity

Verify the full consumer chain without local matching or multiplicity erasure.

- [x] `W04.P12.S29` - Audit overview, agenda, backlog, workflow gates, filing-window lookup, and explain for exclusive consumption of canonical deadline APIs; `src/cadrumo/application/`.
- [x] `W04.P12.S30` - Add overview and workflow regressions comparing ordered semantic coordinates without multiplicity-erasing assertions; `src/cadrumo/application/overview/tests/; src/cadrumo/application/modelo/tests/`.
- [x] `W04.P12.S31` - Add real CLI JSON regressions for calendar, agenda, backlog, workflow, and explain including exactly four M303 quarterly obligations for 2025; `src/cadrumo/entrypoints/cli/tests/`.
- [x] `W04.P12.S32` - Add all-modelo parity coverage across registry, DeadlineEngine, overview, workflow, and real CLI for every supported filing year; `src/cadrumo/domain/deadlines/tests/; src/cadrumo/application/overview/tests/; src/cadrumo/entrypoints/cli/tests/`.

### Phase `W04.P13` - exhaustive gates and formal review

Close against fleet invariants, source evidence, repository rules, and architectural intent.

- [ ] `W04.P13.S33` - Run the bundled-registry invariant proving zero ownership, identity, uniqueness, qualifier, period, and completeness violations; `src/cadrumo/domain/calculations/registry/tests/`.
- [ ] `W04.P13.S34` - Run exact historical engine and CLI scenarios for every repaired modelo against the adjudicated registry census; `src/cadrumo/domain/deadlines/tests/; src/cadrumo/entrypoints/cli/tests/; .vault/audit/`.
- [ ] `W04.P13.S35` - Run Ruff, focused and full pytest, Vaultspec, registry validation, generated-reference drift, locale, and real CLI smoke gates; `src/cadrumo/; dev/; .vault/`.
- [ ] `W04.P13.S36` - Perform formal code and architecture review for canonical reuse, source fidelity, warm-load enforcement, consumer parity, and absence of superseded paths, running Vaultspec RAG discovery followed by exact-symbol sweeps to prove no revision selector, filing-window resolver, period parser, cadence authority, supported-year horizon, deadline catalogue, qualifier vocabulary, or downstream deduplication has been redeclared; `src/cadrumo/; .vault/exec/; .vault/audit/`.

## Parallelization

Waves are ordered. Within W01, schema typing precedes validator work; identity,
ownership, and uniqueness may land before the temporal-coverage supported-year
projection, while completeness waits for it. Within W02, M190 and M193 can be
adjudicated independently, and each periodic modelo may have one isolated writer after
the shared validator contract is stable. M210 data follows qualifier schema. W03 follows
valid registry data. W04 and formal review are strictly last.

## Verification

- Every deadline semantic coordinate has exactly one owner selected by
  `select_revision`, one identifier, and one occurrence.
- Every redundant `filing_year` equals `Period.filing_year`; physical filing dates may
  lawfully fall in the following calendar year.
- Periodic completeness consumes the one supported-year authority and derives cadence
  via `Period` and `registry_period_kind`; no parallel horizon or cadence map exists.
- M210 resultado uses `ResultDisposition`, tipo scope preserves official two-digit codes,
  and tipo 28 gains no numeric offset without verified RD 1776/2004 authority.
- Registry authority and `resolve_filing_window` remain the only projection and matching
  surfaces; runtime and CLI layers contain no dedupe or revision-selection workaround.
- M303 filing year 2025 produces exactly four quarterly obligations at authority,
  engine, overview, workflow, and real CLI boundaries.
- Cold and warm registry validation, focused and full tests, Ruff, Vaultspec, generated
  references, locales, CLI smoke tests, and formal code review all pass.
