---
tags:
  - '#plan'
  - '#modelo-verify-nonzero-guards'
date: '2026-06-30'
modified: '2026-07-17'
tier: L3
related:
  - '[[2026-06-30-modelo-verify-nonzero-guards-adr]]'
  - '[[2026-06-30-modelo-verify-nonzero-guards-research]]'
  - '[[2026-06-02-modelo-200-base-determination-adr]]'
---

# `modelo-verify-nonzero-guards` plan

## Description

This plan closes the silent-under-declaration gaps the research confirmed open at HEAD on five self-assessment modelos whose headline liability is computed from a manual or partially-manual base: M202 (IS pago fraccionado), M123 (retenciones capital mobiliario), M151 (IRPF impatriados), M714 (Patrimonio), and M210 (IRNR, which already carries one BLOCKING_RULE guard unrelated to base under-declaration). The no-silent-under-declaration discipline requires every modelo verify gate to surface at least an ADVISORY finding when a positive economic input resolves to a zero dependent base or cuota with no offsetting reduction declared; the M200 base-determination work and the M131 cuota-minima advisory established the worked pattern this plan extends to five further modelos.

Every guard authored in this plan reuses the shipped `implies_nonzero` operator (`KNOWN_VERIFICATION_PREDICATE_OPERATORS`, `src/aeat/domain/calculations/registry/_schema.py`) against casilla ids and legal grounding that already exist in the registry at HEAD, mirroring the M200 and M131 precedent exactly: pure registry-authoring TOML changes plus a two-tier test (a registry-shape test asserting the predicate's shape on the loaded snapshot, and a gate-behaviour test calling `evaluate_verification_predicates` directly to prove FIRES on positive-antecedent/zero-consequent, HOLDS on positive/positive, and trivial-HOLD on zero-or-negative-antecedent). Every guard is ADVISORY, never BLOCKING_RULE, because no chain in this plan was confirmed free of legitimate zero-consequent cases.

Two findings the research deliberately scoped out rather than guessed at are not silently dropped: M714's `base-imponible -> base-liquidable` and `total-cuota-integra -> cuota-a-ingresar` edges (high false-positive risk from the minimo exento and limite conjunto mechanics), and M210's inmobiliaria branch (the highest real-world value silent-zero risk, gated on a categorical casilla condition the current `implies_nonzero` DSL cannot express). Wave `W02` resolves both with a grounded decision -- author a false-positive-free guard where one exists, or record a documented non-guard rationale -- so no open item from the ADR or research is stranded at plan close.

This plan is grounded in the approved `2026-06-30-modelo-verify-nonzero-guards-adr` and its backing `2026-06-30-modelo-verify-nonzero-guards-research`, and follows the worked pattern recorded in `2026-06-02-modelo-200-base-determination-adr`. During plan authoring the M202 formula-text re-confirmation the ADR flagged as an open item for this phase was completed: `13 = 04 + 38 - 39` was read verbatim and confirmed byte-identical across all three M202 revisions (2025-y-siguientes, 2023-2024, 2019-2022), so Wave `W01` authors the guard across all three rather than scoping to one revision with a follow-up.

## Steps

## Wave `W01` - ADVISORY nonzero guards across five manual-base modelos

Author the five ADR-decided implies_nonzero ADVISORY verification predicates (M202, M123, M151, M714, M210) closing the no-silent-under-declaration gap the research confirmed open at HEAD; each Phase is a single modelo, pure registry-authoring plus a two-tier registry-shape and gate-behaviour test, with every casilla id and legal_ref already confirmed against the bundled corpus and existing legal catalogue, so Phases are fully independent and parallelizable across distinct files.

### Phase `W01.P01` - M202 IS pago fraccionado: base-imponible-previa guard

Author the implies_nonzero(04, 13) ADVISORY across all three M202 revisions (formula text 13 = 04 + 38 - 39 confirmed byte-identical across 2025-y-siguientes, 2023-2024, and 2019-2022 during plan authoring) and ship the two-tier test pair.

- [x] `W01.P01.S01` - Author the modelo-202-base-imponible-previa-determinada-cuando-resultado-positivo ADVISORY predicate implies_nonzero(["04", "13"]) with legal_refs ley-27-2014:art-40-3 and ley-27-2014:art-40, grounded in the 2025-y-siguientes 13 = 04 + 38 - 39 formula confirmed during plan authoring; `src/aeat/_data/registry/aeat/modelos/202/revisions/2025-y-siguientes/verification_expectations/0002-verification_predicates.toml`.
- [x] `W01.P01.S02` - Author the identical implies_nonzero(["04", "13"]) ADVISORY predicate on the 2023-2024 revision after re-confirming its base-imponible-previa formula text is byte-identical to 2025-y-siguientes; `src/aeat/_data/registry/aeat/modelos/202/revisions/2023-2024/verification_expectations/0002-verification_predicates.toml`.
- [x] `W01.P01.S03` - Author the identical implies_nonzero(["04", "13"]) ADVISORY predicate on the 2019-2022 revision after re-confirming its base-imponible-previa formula text is byte-identical to 2025-y-siguientes; `src/aeat/_data/registry/aeat/modelos/202/revisions/2019-2022/verification_expectations/0002-verification_predicates.toml`.
- [x] `W01.P01.S04` - Add a registry-shape test asserting predicate_id, expression, finding_kind, and legal_refs for the new M202 04-to-13 advisory on all three loaded revision snapshots; `src/aeat/domain/calculations/registry/tests/test_modelo_202_registry.py`.
- [x] `W01.P01.S05` - Add a gate-behaviour test calling evaluate_verification_predicates directly for the M202 04-to-13 advisory across all three revisions, proving FIRES on positive-04-zero-13, HOLDS on positive-04-positive-13, and trivial-HOLD on zero-or-negative-04; `src/aeat/application/modelo/tests/test_verification_m202_advisory.py`.

### Phase `W01.P02` - M123 retenciones capital mobiliario: base-total guard

Author the implies_nonzero(06, 09) ADVISORY on the single calc-grade revision (2024-y-siguientes; 2019-2023 has no calc chain) with the aggregate-vs-per-category design choice resolved and recorded, and ship the two-tier test pair.

- [x] `W01.P02.S06` - Author the modelo-123-2024-base-total-implica-retenciones-total ADVISORY predicate implies_nonzero(["06", "09"]) with legal_refs rd-439-2007:art-90 and ley-35-2006:art-101 on the 2024-y-siguientes revision, recording the aggregate-versus-per-category design decision in the exec record; `src/aeat/_data/registry/aeat/modelos/123/revisions/2024-y-siguientes/verification_expectations/0002-verification_predicates.toml`.
- [x] `W01.P02.S07` - Add a registry-shape test asserting predicate_id, expression, finding_kind, and legal_refs for the new M123 06-to-09 advisory on the loaded 2024-y-siguientes revision snapshot; `src/aeat/domain/calculations/registry/tests/test_modelo_123_registry.py`.
- [x] `W01.P02.S08` - Add a gate-behaviour test calling evaluate_verification_predicates directly for the M123 06-to-09 advisory, proving FIRES on positive-06-zero-09, HOLDS on positive-06-positive-09, and trivial-HOLD on zero-or-negative-06; `src/aeat/application/modelo/tests/test_verification_m123_advisory.py`.

### Phase `W01.P03` - M151 IRPF impatriados: base-liquidable guard

Author the implies_nonzero(impatriado.base-liquidable-general, impatriado.cuota-integra-general) ADVISORY on the single revision (2015-y-siguientes) and ship the two-tier test pair.

- [x] `W01.P03.S09` - Author the modelo-151-base-liquidable-implica-cuota-integra ADVISORY predicate implies_nonzero(["impatriado.base-liquidable-general", "impatriado.cuota-integra-general"]) with legal_refs ley-35-2006:art-93, creating the verification_expectations directory on the 2015-y-siguientes revision; `src/aeat/_data/registry/aeat/modelos/151/revisions/2015-y-siguientes/verification_expectations/0001-verification_predicates.toml`.
- [x] `W01.P03.S10` - Add a registry-shape test asserting predicate_id, expression, finding_kind, and legal_refs for the new M151 base-liquidable-to-cuota-integra advisory on the loaded 2015-y-siguientes revision snapshot; `src/aeat/domain/calculations/registry/tests/test_modelo_151_registry.py`.
- [x] `W01.P03.S11` - Add a gate-behaviour test calling evaluate_verification_predicates directly for the M151 base-liquidable-to-cuota-integra advisory, proving FIRES on positive-base-zero-cuota, HOLDS on positive-base-positive-cuota, and trivial-HOLD on zero-or-negative-base; `src/aeat/application/modelo/tests/test_verification_m151_advisory.py`.

### Phase `W01.P04` - M714 Patrimonio: cuota-integra to total-cuota-integra guard

Author the implies_nonzero(patrimonio.cuota-integra, patrimonio.total-cuota-integra) ADVISORY on the single revision (2021-y-siguientes), explicitly the only SAFE edge of the three candidates -- the other two are deferred to Wave W02 -- and ship the two-tier test pair.

- [x] `W01.P04.S12` - Author the modelo-714-cuota-integra-implica-total-cuota-integra ADVISORY predicate implies_nonzero(["patrimonio.cuota-integra", "patrimonio.total-cuota-integra"]) with legal_refs ley-19-1991:art-30, creating the verification_expectations directory on the 2021-y-siguientes revision -- the base-liquidable and cuota-a-ingresar edges are explicitly NOT authored here; `src/aeat/_data/registry/aeat/modelos/714/revisions/2021-y-siguientes/verification_expectations/0001-verification_predicates.toml`.
- [x] `W01.P04.S13` - Add a registry-shape test asserting predicate_id, expression, finding_kind, and legal_refs for the new M714 cuota-integra-to-total-cuota-integra advisory on the loaded 2021-y-siguientes revision snapshot; `src/aeat/domain/calculations/registry/tests/test_modelo_714_registry.py`.
- [x] `W01.P04.S14` - Add a gate-behaviour test calling evaluate_verification_predicates directly for the M714 cuota-integra-to-total-cuota-integra advisory, proving FIRES on positive-cuota-integra-zero-total, HOLDS on positive-cuota-integra-positive-total, and trivial-HOLD on zero-or-negative-cuota-integra; `src/aeat/application/modelo/tests/test_verification_m714_advisory.py`.

### Phase `W01.P05` - M210 IRNR: rendimientos-integros to base-imponible general/UE branch guard

Append the implies_nonzero(rendimientos_integros, base_imponible) ADVISORY to the existing 2025 verification_predicates.toml alongside the untouched representante-fiscal predicate, and ship the two-tier test pair; the inmobiliaria branch is explicitly out of scope here and deferred to Wave W02.

- [x] `W01.P05.S15` - Append the modelo-210-2025-rendimientos-integros-implica-base-imponible ADVISORY predicate implies_nonzero(["rendimientos_integros", "base_imponible"]) with legal_refs trlirnr-rdleg-5-2004:art-24 to the existing 2025 verification_predicates.toml, leaving the representante-fiscal predicate untouched; `src/aeat/_data/registry/aeat/modelos/210/revisions/2025/verification_expectations/0001-verification_predicates.toml`.
- [x] `W01.P05.S16` - Add a registry-shape test asserting predicate_id, expression, finding_kind, and legal_refs for the new M210 rendimientos-integros-to-base-imponible advisory alongside the existing representante-fiscal predicate on the loaded 2025 revision snapshot; `src/aeat/domain/calculations/registry/tests/test_modelo_210_registry.py`.
- [x] `W01.P05.S17` - Add a gate-behaviour test calling evaluate_verification_predicates directly for the M210 rendimientos-integros-to-base-imponible advisory, proving FIRES on positive-rendimientos-zero-base, HOLDS on positive-rendimientos-positive-base, and trivial-HOLD on zero-or-negative-rendimientos; `src/aeat/application/modelo/tests/test_verification_m210_advisory.py`.

## Wave `W02` - Deferred-item resolution: M714 riskier edges and M210 inmobiliaria branch

Resolve the two genuinely-uncertain findings the research deliberately scoped out rather than guessing at: M714's base-liquidable and cuota-a-ingresar edges (high false-positive risk from the minimo exento and limite conjunto mechanics) and M210's inmobiliaria branch (the highest-value silent-zero risk, gated on a categorical casilla condition the current implies_nonzero DSL cannot express). Depends on Wave W01 landing first so the M714 and M210 registry files and their test scaffolding already exist; every Step ends in either an authored guard with tests or a grounded, documented non-guard decision -- no item is left silently unresolved.

### Phase `W02.P06` - M714 riskier-edge grounded decisions

Decide, per edge, whether a false-positive-free ADVISORY exists; author it if so, otherwise document the wontfix rationale grounded in the minimo exento and limite conjunto mechanics -- never silence by omission.

- [x] `W02.P06.S18` - Investigate the M714 base-imponible-to-base-liquidable edge against the minimo exento mechanics (a filer obligated to file on gross assets at or above EUR 2M can legitimately have a positive base-imponible and a zero or floored base-liquidable below the EUR 700000 default exemption), decide whether a false-positive-free ADVISORY condition exists, and either author it with legal_refs ley-19-1991:art-28 plus a two-tier test pair or record the wontfix rationale as a vault audit finding; `src/aeat/_data/registry/aeat/modelos/714/revisions/2021-y-siguientes/verification_expectations/0001-verification_predicates.toml`.
- [x] `W02.P06.S19` - Investigate the M714 total-cuota-integra-to-cuota-a-ingresar edge against the limite conjunto art. 31 cap, the Ceuta and Melilla bonificacion, and foreign-tax-credit deductions, decide whether a false-positive-free ADVISORY condition exists, and either author it with grounded legal_refs plus a two-tier test pair or record the wontfix rationale as a vault audit finding; `src/aeat/_data/registry/aeat/modelos/714/revisions/2021-y-siguientes/verification_expectations/0001-verification_predicates.toml`.

### Phase `W02.P07` - M210 inmobiliaria categorical-conditional guard

Investigate whether a narrow, non-Decimal-widening DSL extension can express tipo_renta == "inmobiliaria" implies nonzero(base_imponible); act on the grounded decision -- author the operator, its companion ADR if the design is non-trivial, the M210 predicate, and tests, or scaffold a follow-up research stub recording the deferral and its blocking constraint.

- [x] `W02.P07.S20` - Investigate whether a categorical-conditional predicate (tipo_renta equals a literal implies a numeric casilla nonzero) can be evaluated without widening the Decimal-only casilla_values mapping that flows through every verification and calculation call site, decide between (a) a narrow operator extension scoped to the verification-evaluator boundary or (b) deferral, and record the decision plus its blocking constraints in the exec record; `src/aeat/application/modelo/_verification_actions.py`.
- [x] `W02.P07.S21` - Act on the prior Step's decision, authoring a companion ADR documenting the new casilla_equals_implies_nonzero operator's grammar, evaluator semantics, and registry-build validation coverage via vaultspec-adr when outcome (a) is selected, or scaffolding a follow-up research document recording the deferral and the casilla_values plumbing constraint via vaultspec-core vault add research when outcome (b) is selected; `.vault/adr/`.
- [x] `W02.P07.S22` - When outcome (a) was selected, implement the casilla_equals_implies_nonzero operator end to end -- the KNOWN_VERIFICATION_PREDICATE_OPERATORS entry, the regex and evaluator branch, and the registry-build validator coverage -- with a generic operator-level unit test in the same commit, otherwise close this Step immediately with a one-line exec record cross-referencing the deferral; `src/aeat/domain/calculations/registry/_schema.py`.
- [x] `W02.P07.S23` - When outcome (a) was selected, append the M210 inmobiliaria-branch predicate using the new operator to the 2025 verification_predicates.toml and ship its two-tier test pair, FIRES when tipo_renta is inmobiliaria and valor_catastral is blank, HOLDS otherwise, or close this Step immediately with a one-line exec record cross-referencing the deferral; `src/aeat/_data/registry/aeat/modelos/210/revisions/2025/verification_expectations/0001-verification_predicates.toml`.

## Wave `W03` - Verification, review, and closeout

Run the focused and full-tree quality gates over every Wave W01 and W02 deliverable, dispatch an independent code review and a fresh-context honesty review per the campaign-close-honesty-review discipline, action every finding into a tracked Step or a documented deferral, and close the plan with a complete exec-record set and a clean vault check. Depends on both W01 and W02 landing first.

### Phase `W03.P08` - Focused and full-tree quality gates

Run the focused registry and verification-action suites for all five touched modelos, the feature-surface gate over only the touched files, and the full-tree collect-only gate, triaging any peer-owned failures per the full-tree-gate-must-distinguish-owner discipline.

- [x] `W03.P08.S24` - Run the focused registry test suites for all five touched modelos (test_modelo_202_registry.py, test_modelo_123_registry.py, test_modelo_151_registry.py, test_modelo_714_registry.py, test_modelo_210_registry.py) plus every new gate-behaviour test file and confirm a clean pass; `src/aeat/domain/calculations/registry/tests/`.
- [x] `W03.P08.S25` - Run the feature-surface gate (ruff plus pytest plus vault check) restricted to this feature's touched files and confirm a clean pass; `src/aeat/_data/registry/aeat/modelos/`.
- [x] `W03.P08.S26` - Run uv run --no-sync pytest --collect-only -q across the full src/aeat tree, confirm clean collection, and triage any failing signature as owner-feature-scoped versus peer-campaign churn before closing this Step; `src/aeat/`.

### Phase `W03.P09` - Independent code review and honesty review

Dispatch vaultspec-code-review over the full campaign diff and run a fresh-context honesty review per aeat-campaign-close-honesty-review, persisting both as audit documents and converting every finding into a tracked Step or a documented deferral.

- [x] `W03.P09.S27` - Dispatch vaultspec-code-reviewer over the full campaign commit range (Waves W01 and W02) and persist its findings as a vault audit document; `.vault/audit/`.
- [x] `W03.P09.S28` - Run a fresh-context honesty review per aeat-campaign-close-honesty-review against the closure summary, persist the output as a second vault audit document, and confirm no Step's underlying decision was assumed-but-unverified; `.vault/audit/`.
- [x] `W03.P09.S29` - Convert every finding from the two review passes into either a newly inserted plan Step with a verification gate or an explicitly documented deferral cross-referenced from the audit document; `.vault/plan/2026-06-30-modelo-verify-nonzero-guards-plan.md`.

#### `W03.P09` documented deferral register

- `DFR-M210-INMOBILIARIA-E2E` - RESOLVED by commits `d10662573`
  and `40c1d690c`: the real calculate -> verify path now proves text
  `tipo_renta` persists through production input values and fires the M210
  inmobiliaria advisory. Cross-reference
  `2026-07-01-modelo-verify-nonzero-guards-review-closeout-audit` and exec
  record `2026-07-01-modelo-verify-nonzero-guards-exec-DFR-M210-INMOBILIARIA-E2E`.
- `DFR-M210-TEXT-INPUT-LOCALE-PARITY` - RESOLVED by commit `96c666d56`:
  `application.modelo.errors.calculate_text_input_empty` resolves through the
  four runtime locale catalogues via the sanctioned locale CLI, with a focused
  `_text_value` / `resolve_error_message` regression. The same pass repaired
  the locale scaffold/audit drift exposed by the gate.
- `DFR-M123-RIRPF-EXONERATION-CORPUS` - RESOLVED by commit `b860c576e`:
  RD 439/2007 art. 75 is bundled and catalogued, and the retained conclusion is
  limited to non-withheld art. 75.3 classes not populating positive M123
  withholding-base casillas. Carve-back/payment-on-account cases remain outside
  that conclusion.
- `DFR-M202-B2-RESULTADO-FORMULA-WIRING` - RESOLVED by commits `cb002833a`
  and `db7f4434b`: casilla 26 now feeds casilla 32 for B2 grupos fiscales,
  grounded in bundled AEAT instructions. Residual B1/B2 mutual-exclusion
  validation remains a follow-up, not part of the formula wiring deferral.
- `RESOLVED-CAMPAIGN-SCOPED-COMMIT` - commit `5592a0a3a` landed the scoped
  campaign files and vault records with explicit pathspecs while leaving
  unrelated peer WIP outside the commit; cross-reference
  `2026-07-01-modelo-verify-nonzero-guards-review-closeout-audit`.

#### `W03.P09` carry-forward hardening queue

- `FUP-M202-B1-B2-XOR-VALIDATION` - RESOLVED by commit `af391159a`:
  M202 now declares `at_most_one_positive(["18", "26"])` as a
  `BLOCKING_RULE` for every active revision. The additive formula remains for
  B1-only and B2-only cases; verification refuses the impossible both-positive
  filing state grounded in the official `clave [18] (o clave [26])` wording.
- `FUP-M210-ENUM-DISPATCH-ARG-INDEX` - RESOLVED by commit `556b93033`:
  enum-dispatch binding collection is now shape-aware for `m210_resolve_rate`,
  preserving the legacy 4-arg country binding at `args[3]` and collecting the
  current 6-arg country binding at `args[5]`.
- `FUP-FILING-DRAFT-TEXT-CASILLA` - RESOLVED by commit `1237c075c`:
  the filing-draft builder splits registry `data_type = "text"` casillas out of
  the Decimal channel, passes them to `calculate_registry_snapshot(text_inputs=...)`,
  and preserves the literal `tipo_renta` value in the draft output.

### Phase `W03.P10` - Exec-record completeness and vault closeout

Confirm every closed Step carries a matching exec record per plan-closure-requires-exec-records, rebuild the feature index, and run vault check all to a clean result before declaring the plan complete.

- [x] `W03.P10.S30` - Confirm every closed Step in this plan carries a matching exec record per plan-closure-requires-exec-records, scaffolding any missing record via vaultspec-core vault add exec; `.vault/exec/2026-06-30-modelo-verify-nonzero-guards/`.
- [x] `W03.P10.S31` - Rebuild the feature index via vaultspec-core vault feature index; `.vault/index/modelo-verify-nonzero-guards.index.md`.
- [x] `W03.P10.S32` - Run vaultspec-core vault check all and resolve any reported drift before declaring the plan complete; `.vault/`.

## Parallelization

Waves are sequenced: `W02` depends on `W01` because the M714 and M210 Phases it extends must already carry their authored Wave-`W01` guard and registry files before the deferred-edge decisions and the categorical-conditional investigation can act on them, and `W03` depends on both `W01` and `W02` because the quality gates, review, and closeout cover the full campaign diff.

Within `W01`, every Phase (`P01` M202, `P02` M123, `P03` M151, `P04` M714, `P05` M210) touches a disjoint set of registry TOML files and a disjoint set of new test files, so all five Phases are fully parallelizable across five agents. Within each Phase, the registry-authoring Step(s) must land before that Phase's two test Steps (the tests load the predicate off the authority), so the registry-shape test Step and the gate-behaviour test Step are each blocked on their Phase's registry Step(s) but not on each other or on any other Phase. M202's three registry Steps (`S01`, `S02`, `S03`) touch three independent revision directories and may run in parallel with each other; both M202 test Steps (`S04`, `S05`) are blocked on all three landing first because their parametrized suites cover all three revisions.

Within `W02`, Phase `P06` (M714) and Phase `P07` (M210) are independent and parallelizable; `P06`'s two Steps (`S18`, `S19`) address independent edges and are mutually parallelizable. `P07` is strictly sequential: `S20` (investigate and decide) gates `S21` (act on the decision: companion ADR or deferral stub), which gates `S22` (engine-level operator implementation, only under outcome (a)), which gates `S23` (the M210 predicate and its tests, only under outcome (a)).

Within `W03`, Phase `P08` (quality gates) must complete before `P09` (review) can meaningfully assess a green campaign, and `P09` must complete before `P10` (closeout) converts its findings and confirms exec-record completeness. `P08`'s three Steps are sequential in the order listed (focused suites, then the feature-surface gate, then the full-tree collect-only gate) since each is a strictly broader verification scope than the last.

Per the git-and-worktree-safety and swarm-orchestration disciplines, every executing agent runs `git diff -- <file>` immediately before its first edit to confirm no peer agent holds uncommitted WIP in the same file, and re-reads HEAD immediately before acting on any finding from a prior Step or review pass. No executing agent runs `git stash`, `git reset`, `git checkout <path>`, `git restore`, `git clean`, or `git rebase` in any form; this worktree is shared with concurrent campaigns, including a possibly-active legal-grounding campaign under `src/aeat/_data/registry/`.

## Verification

The plan is complete when every Step is closed (`- [x]`) and every closed Step carries a matching `.vault/exec/2026-06-30-modelo-verify-nonzero-guards/` execution record per `plan-closure-requires-exec-records` (Wave `W03` Phase `P10`), with the following verifiable checks satisfied:

- Every Wave `W01` registry-shape test (`src/aeat/domain/calculations/registry/tests/test_modelo_202_registry.py`, `test_modelo_123_registry.py`, `test_modelo_151_registry.py`, `test_modelo_714_registry.py`, `test_modelo_210_registry.py`) asserts `predicate_id`, `expression`, `finding_kind == "ADVISORY"`, and `legal_refs` membership for its new guard, loaded off `resources().modelos.authority`, and passes.
- Every Wave `W01` gate-behaviour test (`src/aeat/application/modelo/tests/test_verification_m202_advisory.py`, `test_verification_m123_advisory.py`, `test_verification_m151_advisory.py`, `test_verification_m714_advisory.py`, `test_verification_m210_advisory.py`) calls `evaluate_verification_predicates` directly and proves FIRES on positive-antecedent/zero-consequent, HOLDS on positive/positive, and trivial-HOLD on zero-or-negative-antecedent, per `no-tautological-calculation-tests` (gate-behaviour assertions, not hand-computed Decimal oracles).
- Every M202 revision (`2025-y-siguientes`, `2023-2024`, `2019-2022`) carries the identical `implies_nonzero(["04", "13"])` predicate; no revision is silently scoped out.
- Wave `W02` Phase `P06` resolves both M714 candidate edges to either an authored ADVISORY with its own two-tier test pair, or a documented wontfix rationale persisted as a vault audit finding citing the minimo exento or limite conjunto mechanics; neither edge is left unaddressed.
- Wave `W02` Phase `P07` resolves the M210 inmobiliaria branch to either a fully implemented and tested `casilla_equals_implies_nonzero` operator (schema, evaluator, validator, M210 predicate, generic operator unit test, M210-specific two-tier test pair) backed by a companion ADR if the design proved non-trivial, or a scaffolded follow-up research document recording the casilla_values Decimal-only plumbing constraint and the deferral; the open item is tracked, not stranded, under either outcome.
- `uv run --no-sync pytest --collect-only -q` over the full `src/aeat` tree exits clean (Wave `W03` Phase `P08` `S26`), with any non-owner-scoped failure triaged per `full-tree-gate-must-distinguish-owner` rather than blocking this plan's closure.
- The feature-surface gate (ruff, pytest, vault check) restricted to this feature's touched files passes (Wave `W03` Phase `P08` `S25`).
- An independent `vaultspec-code-reviewer` pass and a fresh-context honesty review per `aeat-campaign-close-honesty-review` are both persisted as `.vault/audit/` documents (Wave `W03` Phase `P09`), and every finding from either pass is either a newly tracked plan Step with its own verification gate or an explicitly documented deferral.
- `vaultspec-core vault feature index` reflects the complete document set for `modelo-verify-nonzero-guards`, and `vaultspec-core vault check all` reports zero feature-scoped drift for `modelo-verify-nonzero-guards` / `m210-categorical-conditional-predicate`; any repository-wide residual is triaged as unrelated peer or historical vault drift, not claimed as global green (Wave `W03` Phase `P10`).

For the underlying legal and design grounding behind each guard, see `2026-06-30-modelo-verify-nonzero-guards-adr` and `2026-06-30-modelo-verify-nonzero-guards-research` in the `related:` frontmatter.
