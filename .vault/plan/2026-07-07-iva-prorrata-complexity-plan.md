---
tags:
  - '#plan'
  - '#iva-prorrata-complexity'
date: '2026-07-07'
modified: '2026-07-17'
tier: L3
related:
  - '[[2026-07-07-prorrata-especial-adr]]'
  - '[[2026-07-07-prorrata-sectores-diferenciados-adr]]'
  - '[[2026-07-07-prorrata-art104-tres-exclusions-adr]]'
  - '[[2026-07-07-prorrata-art105-cinco-interrupted-adr]]'
  - '[[2026-07-05-cross-period-prorrata-adr]]'
  - '[[2026-07-01-iva-complexity-hardening-scope-adr]]'
  - '[[2026-07-10-iva-prorrata-complexity-research]]'
---

<!-- RETIRED: W05 -->

# `iva-prorrata-complexity` plan

## Wave `W01` - Independent axes (art-104.Tres exclusions parallel-with art-105.Cinco interrupted)

The two least-entangled ADRs. art-104.Tres (denominator exclusions) and art-105.Cinco (interrupted-activity seeding) share no ledger-transaction field, no _iva_ledger apportionment routing, and no CLI verb; they overlap only on distinct functions in _prorrata_regularizacion.py and distinct additive iva.toml blocks. P01 and P02 therefore run in parallel, coordinated by per-file explicit-pathspec commits.

### Phase `W01.P01` - art-104.Tres denominator exclusions

Ground the 6 real art-104.Tres exclusions and make the ledger volume-rollup a reconciliation pre-fill proposal (never a silent filed-volume authority), via a hybrid auto/operator exclusion classification.

- [x] `W01.P01.S01` - Author the ley-37-1992 art-104 (art-104.Tres) legal entries with corpus_ref and required_text for the 6 real exclusions, correcting the stale subvenciones-no-vinculadas prose removed by Ley 3/2006; `src/aeat/_data/registry/aeat/legal/iva.toml`.
- [x] `W01.P01.S02` - Add the Art104TresExclusion core enum and the operator-declared exclusion tag on the ledger transaction, with save/load roundtrip + anti-tautology proof; `src/aeat/core/, src/aeat/domain/transactions/_models.py`.
- [x] `W01.P01.S03` - Filter the art-104.Tres exclusions from the annual volume rollup and keep it a reconciliation pre-fill proposal, never a silent filed-volume authority; `src/aeat/application/aggregation/_iva_ledger.py, src/aeat/application/calculations/_prorrata_regularizacion.py`.
- [x] `W01.P01.S04` - Surface the operator exclusion declaration at the CLI and the M303 exclusion metadata in the registry; `src/aeat/entrypoints/cli/, src/aeat/_data/registry/aeat/modelos/303/`.
- [x] `W01.P01.S05` - Verify the exclusion classification against an AEAT worked example with no hand-computed expected values; `src/aeat/application/calculations/tests/`.

### Phase `W01.P02` - art-105.Cinco interrupted-activity seeding

Represent an interrupted ejercicio in the register and seed the resumed year with the lawful art-105.Cinco last-three-active-years global percentage (summed volumes, skipping the gap), advising honestly on insufficient history.

- [x] `W01.P02.S06` - Extend the ley-37-1992 art-105 required_text with the art-105.Cinco clause, corpus-grounded; `src/aeat/_data/registry/aeat/legal/iva.toml`.
- [x] `W01.P02.S07` - Add the interrupted-ejercicio marker/provenance to the register enums and the active/inactive history on ProrrataRegisterEntry; `src/aeat/core/_prorrata_register.py, src/aeat/domain/prorrata_register/__init__.py`.
- [x] `W01.P02.S08` - Implement the last-three-active-years global seed walk (summed volumes via compute_prorrata_definitiva_anual, skipping the gap) and the insufficient-history advisory; `src/aeat/domain/prorrata_register/__init__.py, src/aeat/application/calculations/_prorrata_regularizacion.py`.
- [x] `W01.P02.S09` - Verify the interruption seed against a worked example with a genuine gap and no averaged percentages; `src/aeat/domain/prorrata_register/tests/`.

## Wave `W02` - Prorrata especial: regime-aware apportionment foundation

The foundational ledger-trio change. Especial makes the one shared ledger IVA aggregation regime-aware (per-input 100/0/general routing per LIVA art-106) and adds the typed input_classification axis to the transaction. Hard-collides with W01 and W03 on _models.py and _iva_ledger.py, so it runs after W01. It is the substrate that sectores (W03) extends.

### Phase `W02.P03` - especial per-input classification, apportionment and +10% advisory

Wire a typed per-input use-classification from the ledger into a regime-aware apportionment (100/0/general), and fire the settlement art-103.Dos.2 +10% mandatory-especial advisory. Consumes the existing classify_input_deduction substrate; general path stays byte-identical.

- [x] `W02.P03.S10` - Author the ley-37-1992 art-103 and art-106 legal entries with corpus_ref + required_text, grounded in the bundled consolidated LIVA; `src/aeat/_data/registry/aeat/legal/iva.toml`.
- [x] `W02.P03.S11` - Add the typed input_classification axis (core InputClassification) to the ledger transaction, operator-declared for especial buckets, with roundtrip + anti-tautology proof; `src/aeat/domain/transactions/_models.py`.
- [x] `W02.P03.S12` - Make the shared ledger IVA apportionment regime-aware so especial routes each deducible cuota via _deductible_percentage_for (100/0/general), the general path stays byte-identical, and provenance carries the applied classification and percentage; `src/aeat/application/aggregation/_iva_ledger.py`.
- [x] `W02.P03.S13` - Emit the settlement art-103.Dos.2 +10% mandatory-especial advisory Notice via is_especial_mandatory, non-blocking, both totals on Notice.context; `src/aeat/application/calculations/_prorrata_regularizacion.py`.
- [x] `W02.P03.S14` - Surface the per-input classification declaration at the CLI and the M303 especial classification metadata; `src/aeat/entrypoints/cli/, src/aeat/_data/registry/aeat/modelos/303/`.
- [x] `W02.P03.S15` - Verify all three art-106 reglas (100/0/common) and the +10% comparison against an AEAT Manual practico worked example with no substrate-derived expected values; `src/aeat/application/aggregation/tests/`.
- [x] `W02.P03.S21` - Emit the art-103.Dos.2 +10% mandatory-especial advisory on the live M303 settlement diagnostics so the mandatory-especial breach surfaces to the operator (requires settlement-time dual-regime annual deducible-total computation); `src/aeat/application/modelo/_prorrata_regularizacion_advisory.py`.

## Wave `W03` - Sectores diferenciados: per-sector extension

Extends especial's regime-aware aggregation to per-sector routing over the (ejercicio,sector)-keyed register (LIVA arts 101/9.1.c). Depends on W02 (regime-aware aggregation must exist) and collides with it on _models.py and _iva_ledger.py, so it runs last. Art-101.Dos common-deduction regime is deferred.

### Phase `W03.P04` - sector classification, per-sector orchestration and lifecycle

Operator-declared sector identification (CNAE/IAE) driving per-(ejercicio,sector) register orchestration and per-sector routing in the regime-aware aggregation, with a per-sector provisional/definitive lifecycle.

- [x] `W03.P04.S16` - Author the ley-37-1992 art-101 legal entry corpus-grounded, noting the art-101.Dos common-deduction regime is deferred; `src/aeat/_data/registry/aeat/legal/iva.toml`.
- [x] `W03.P04.S17` - Add operator-declared sector identification (CNAE/IAE) on the contribuyente profile and the sector reference on the ledger transaction; `src/aeat/domain/contribuyente/, src/aeat/domain/transactions/_models.py`.
- [x] `W03.P04.S18` - Orchestrate per-(ejercicio,sector) register entries and per-sector routing in the regime-aware aggregation; `src/aeat/domain/prorrata_register/__init__.py, src/aeat/application/aggregation/_iva_ledger.py`.
- [x] `W03.P04.S19` - Run the per-sector provisional/definitive lifecycle (seed and settlement per sector); `src/aeat/application/prorrata_register/, src/aeat/application/calculations/_prorrata_regularizacion.py`.
- [x] `W03.P04.S20` - Verify per-sector prorrata against a worked example with a greater-than-50-percentage-point sector spread; `src/aeat/domain/prorrata_register/tests/`.

## Wave `W04` - Operator ingress: reach the especial + sectores engines

The W02 especial and W03 sectores apportionment engines are built, grounded and green but operator-unreachable: no production code writes an ESPECIAL ProrrataRegisterEntry or a SectorDefinition, the register has no CLI, and the S14 --input-classification flag is silently inert without an especial register entry. W04 builds the missing operator ingress (especial-regime election CLI, sector-definition partition CLI, per-row --sector tag) so the elected regime/sector actually fires from a real operator flow, proven by an anti-dormant end-to-end test, with the non-electing path byte-identical. Folds the MEDIUM oracle-claim reconciliation and the LOW interrupted-roundtrip fixture from the campaign-close honesty review. This is the campaign's genuine close.

### Phase `W04.P05` - Especial + sectores operator ingress and campaign-close reconciliation

Build the operator surface that writes an ESPECIAL ProrrataRegisterEntry and a SectorDefinition through the existing ProrrataRegisterService, thread the per-row prorrata_sector_id tag through ledger add, close the S14 inert-flag no-silent concern, and prove the especial/sector apportionment fires from the operator flow (non-electing path byte-identical). Fold the MEDIUM oracle-claim reconciliation and LOW interrupted-roundtrip fixture.

- [x] `W04.P05.S22` - Add the prorrata register CLI verb group (elect-especial, elect-general, list) writing GENERAL/ESPECIAL ProrrataRegisterEntry rows through ProrrataRegisterService.declare, and preserve sector_definitions across entry upsert and settlement write; `src/aeat/entrypoints/cli/_prorrata_register_cli.py, src/aeat/entrypoints/cli/_prorrata_register_payloads.py, src/aeat/adapters/persistence/profile/prorrata_register.py, src/aeat/application/modelo/_revision_persistence.py`.
- [x] `W04.P05.S23` - Add the declare-sector CLI verb writing a SectorDefinition partition (sector id, art-9.1.c letra, member activity codes) through a new ProrrataRegisterService.declare_sector over an entries-preserving repository upsert; `src/aeat/entrypoints/cli/_prorrata_register_cli.py, src/aeat/application/prorrata_register/__init__.py, src/aeat/adapters/persistence/profile/prorrata_register.py`.
- [x] `W04.P05.S24` - Thread operator-declared prorrata_sector_id through ManualLedgerTransactionCommand, the manual add action and the idempotency signature, add the --sector flag on ledger add, and surface a non-blocking Notice when --input-classification is set but the bucket has no especial register entry for the row ejercicio; `src/aeat/application/ledger/_models.py, src/aeat/application/ledger/_actions_manual.py, src/aeat/application/ledger/_actions_common.py, src/aeat/entrypoints/cli/_ledger.py`.
- [x] `W04.P05.S25` - Prove especial and sector apportionment fire from the operator flow: an anti-dormant end-to-end test that elects especial and declares sectors and tags inputs through the service the CLI calls then runs the live aggregation and asserts the especial and sector apportionment change the deducible cuota, with the non-electing path byte-identical; `src/aeat/application/aggregation/tests/test_prorrata_operator_ingress_end_to_end.py`.
- [x] `W04.P05.S26` - Reconcile the MEDIUM oracle-claim: amend the plan Verification bullet and the S15 and S20 exec notes to state especial and sectores are proven by law-derived-scenario-through-the-production-path with no bundled AEAT especial or two-sector oracle; `.vault/plan/2026-07-07-iva-prorrata-complexity-plan.md, .vault/exec/2026-07-07-iva-prorrata-complexity/`.
- [x] `W04.P05.S27` - Add an is_interrupted=True entry to the encrypted-SQL prorrata register roundtrip fixture so the interrupted marker crosses the encrypted boundary under test; `src/aeat/adapters/persistence/profile/tests/test_prorrata_register_roundtrip.py`.
- [x] `W04.P05.S28` - Surface a non-blocking WARNING Notice on ledger add when --sector names a sector absent from the bucket's declared SectorDefinition partition, so a typo'd sector tag that would silently deduct at the common-use percentage is instead disclosed (LIVA arts. 9.1.c / 101); `mirror the S24 inert-classification notice pattern and stay silent when the sector is declared; `src/aeat/entrypoints/cli/_ledger.py, src/aeat/locales/, src/aeat/entrypoints/cli/tests/test_prorrata_register_cli.py`.

## Description

Binds the four deferred IVA-prorrata "W06" axis ADRs (`prorrata-especial`,
`prorrata-sectores-diferenciados`, `prorrata-art104-tres-exclusions`,
`prorrata-art105-cinco-interrupted`) into one collision-free execution roadmap.
Each ADR concretises a slice the accepted `cross-period-prorrata` ADR explicitly
deferred, over the register / regime / sector schema that already exists from
birth (no migration). The four are clustered per-ADR (one Phase each) and grouped
into Waves by their code-surface footprint, so that any two axes sharing a
write-file never run concurrently. This plan authors no code; it only sequences
the future implementation, grounded verbatim in the bundled consolidated LIVA
(`ley-37-1992.html`, arts 101 / 103 / 104.Tres / 105.Cinco / 106).

## Steps

## Parallelization

Wave separation is derived from the ADR-vs-ADR write-file footprint matrix, not
assumed. The three ledger-touching axes - especial (E, W02), sectores (S, W03)
and art-104.Tres exclusions (X, W01.P01) - all WRITE the same two hot surfaces
(`domain/transactions/_models.py` and `application/aggregation/_iva_ledger.py`)
plus the M303 registry and the CLI ledger surface, so no two of them may run
concurrently. art-105.Cinco (I, W01.P02) is deliberately register / seeding
internal: it touches no transaction field, no apportionment routing and no CLI
verb, overlapping X only on a distinct function in `_prorrata_regularizacion.py`
and a distinct additive `iva.toml` block. Sectores additionally carries a logical
dependency on especial - it extends the regime-aware aggregation especial
establishes - so E must land before S regardless of the collision.

Resulting collision-free ordering:

- `W01` runs its two Phases IN PARALLEL: `W01.P01` (X) alongside `W01.P02` (I).
  This is the only parallel-safe pair. Their sole shared files are distinct
  functions in `_prorrata_regularizacion.py` (X extends the volume-divergence
  advisory; I adds the interrupted-seed branch) and distinct additive
  `[legal."ley-37-1992:art-104"]` vs `art-105` blocks in `iva.toml`; each Phase
  commits only its own files via explicit pathspec, so there is no line-level
  conflict.
- `W02` (E) is serial after W01: it rewrites the shared `_models.py` /
  `_iva_ledger.py` apportionment that X touched, and establishes the regime-aware
  aggregation W03 needs.
- `W03` (S) is serial last: it depends on E and collides with both E and X on the
  shared ledger surfaces.

Every Step declares its `path/to/file` scope; two Steps in different concurrent
Phases never share a write-scope. The four `iva.toml` legal-entry Steps (S01, S06,
S10, S16) each append a distinct, non-overlapping `[legal."..."]` block and are
safe under explicit-pathspec even when their Phases share Wave W01.

## Verification

The plan is complete when all 20 Steps are closed. Every Wave lands only against
these verifiable criteria:

- Legal grounding: each regulated rule/figure is grounded verbatim in the bundled
  `ley-37-1992` corpus (arts 101 / 103 / 104.Tres / 105.Cinco / 106) with a
  `required_text` cross-check; zero fabricated values.
- Roundtrip: each new persisted field (the art-104.Tres exclusion tag,
  `input_classification`, the sector reference, the interrupted-ejercicio marker)
  passes a strict save / load / equality roundtrip plus an anti-tautology proof.
- Oracle grounding: each apportionment / seed behaviour is proven against an AEAT
  Manual practico worked example where one is bundled (art-104.Tres uses the real
  56% AEAT oracle), never against numbers hand-computed from the compute
  substrate. No bundled AEAT prorrata-especial or two-sector worked-example oracle
  ships in the corpus, so the especial (S15) and sectores (S20) apportionments are
  instead proven by a law-derived scenario driven end-to-end through the
  production aggregation path, with expected values derived from the LIVA
  art. 106.Uno reglas and the art. 101 per-sector rule (grounded verbatim in the
  bundled `ley-37-1992` corpus) and a load-bearing anti-tautology assertion
  (especial/sectored result must differ from the whole-entity general result);
  values are never taken from the `deductible_percentage_for` substrate under
  test. The art-105.Cinco interruption seed (S09) likewise uses an
  ADR-pre-authorised hand-constructed gap scenario.
- Byte-identity: the general (non-especial, single-sector, no-exclusion) path
  stays byte-identical to the landed cross-period-prorrata behaviour.
- Non-silence: every unclassified input, insufficient interruption history,
  mandatory-especial breach, or ledger-vs-declared divergence surfaces an advisory
  Notice, never a silent assumed value or a blocking refusal of a legitimate
  in-progress filing.
- Gate: each Wave closes with `vault plan check` clean and the focused prorrata
  test slice green under `-n0` on a settled tree, with owner-distinction against
  concurrent worktree churn.
