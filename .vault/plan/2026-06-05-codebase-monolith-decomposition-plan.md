---
tags:
  - '#plan'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
tier: L3
related:
  - '[[2026-06-05-codebase-monolith-decomposition-adr]]'
  - '[[2026-06-05-codebase-monolith-decomposition-research]]'
  - '[[2026-06-05-modelo-work-revision-cli-decomposition-plan]]'
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #plan) and one feature tag.
     Replace codebase-monolith-decomposition with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.
     tier is mandatory for new plans. Allowed: L1, L2, L3, L4.
     L1 = Steps only. L2 = Phases above Steps. L3 = Waves above
     Phases above Steps. L4 = Epic above Waves above Phases above
     Steps; PM association required. Pre-existing plans without this
     field default to L2.

     Related: use wiki-links as '[[YYYY-MM-DD-foo-bar]]'. The related field
     carries the AUTHORISING documents (ADR, research, reference, prior
     plan) for every Step in this plan; Steps inherit this chain;
     per-row reference footers do not exist.

     DO NOT add frontmatter fields
     outside the frontmatter. -->


<!-- HIERARCHY AND TIERS:
     Epic > Wave > Phase > Step. Step is the canonical leaf-row
     noun. Execution-log artifact: <Step Record>.
     Tier is declared in frontmatter as tier: L1/L2/L3/L4
     (mandatory for new plans; pre-existing plans without the
     field default to L2 and the writer adds the field on first
     edit). The tier selects containers:
       L1 = Steps only.
       L2 = Phases above Steps.
       L3 = Waves above Phases above Steps.
       L4 = Epic above Waves above Phases above Steps; MUST declare
            a project-management association in the Epic intent
            block prose.
     Selection is by complexity criteria, not container counting.
     Writer never invents containers to qualify a tier. -->

<!-- IDENTIFIERS AND ROW CONTRACT:
     S##, P##, W## are flat, per-document, append-only, immutable.
     Promotion adds containers without renumbering. Gaps are not
     reused.
     Display paths are computed from current grouping:
       Step path:    L1 S##   L2 P##.S##   L3/L4 W##.P##.S##
       Phase heading:        L2 P##       L3/L4 W##.P##
       Wave heading:                      L3/L4 W##
     Row format:
       - [ ] `<display-path>` - imperative-verb action; `path/to/file`.
     Two-state checkboxes only ([ ] open, [x] closed). No per-row
     reference footers; wiki-links and markdown links are forbidden
     in plan body. Authorising documents go in the plan's `related:`
     frontmatter once.
     ASCII spaced hyphens everywhere; em-dash (U+2014) and en-dash
     (U+2013) are forbidden. Step rows within a Phase are
     contiguous. -->

<!-- NO COMPRESSION:
     N self-similar actions = N rows. Never collapse into "for each
     X, do Y" / "across all callers, do Z" / "in every module,
     replace W". The rule applies at every tier including L1. -->

<!-- VAULTSPEC-CORE VAULT PLAN CLI:
     The `vaultspec-core vault plan` CLI is the canonical surface for
     structural manipulation of this plan document. Writers and
     executors MUST use `vaultspec-core vault plan step add/insert/move/
     remove/check/uncheck/toggle/edit`,
     `vaultspec-core vault plan phase add/move/remove/edit`,
     `vaultspec-core vault plan wave add/move/remove/edit`,
     `vaultspec-core vault plan epic intent`, and
     `vaultspec-core vault plan tier promote/demote` for every
     identifier-affecting change rather than hand-editing the row
     grammar. Hand edits are tolerated by the parser but flagged by
     `vaultspec-core vault plan check`; canonical-identifier preservation is
     guaranteed only when the CLI performs the mutation. See the
     CLI ADR (2026-05-06-plan-hardening-adr) for the full
     subcommand surface. -->

# `codebase-monolith-decomposition` `codebase-wide monolith and cognitive complexity decomposition` plan

## Wave `W01` - global inventory and guard baseline

Establish authoritative current-state evidence for every production and test module over 1250 lines and every high-scoring function before selecting decomposition slices.

<!-- One-line headline summary plan. -->

### Phase `W01.P01` - inventory baseline

Persist the current over-1250-line module inventory and callable-size/cognitive-complexity inventory with exact and semantic discovery evidence.

- [x] `W01.P01.S01` - inventory every Python module over 1250 lines and classify production versus test scope; `src/aeat`.
- [x] `W01.P01.S02` - inventory high-length and high-branching callables as a cognitive-complexity proxy; `src/aeat`.

## Wave `W02` - CLI monolith decomposition

Reduce remaining CLI roots below the 1250-line objective through focused command registrars while preserving CLI-as-transport and backend-owned business logic.

### Phase `W02.P02` - ledger root continuation

Continue extracting coherent ledger command groups until _ledger.py moves materially toward the 1250-line objective without CLI-owned accounting policy.

- [x] `W02.P02.S03` - select the next coherent ledger command group for extraction using exact and semantic discovery; `src/aeat/entrypoints/cli/_ledger.py`.
- [x] `W02.P02.S04` - extract the selected ledger command group into a focused registrar module; `src/aeat/entrypoints/cli/_ledger.py src/aeat/entrypoints/cli/_ledger_*.py`.
- [x] `W02.P02.S05` - verify selected ledger behavior and ratchet ledger root size after extraction; `src/aeat/entrypoints/cli/tests/test_ledger* src/aeat/entrypoints/cli/tests/test_cli_module_size.py`.
- [x] `W02.P02.S09` - select the next residual ledger command group for extraction using exact and semantic discovery; `src/aeat/entrypoints/cli/_ledger.py src/aeat/entrypoints/cli/tests`.
- [x] `W02.P02.S10` - extract the selected residual ledger command group into a focused registrar module; `src/aeat/entrypoints/cli/_ledger.py src/aeat/entrypoints/cli/_ledger_*.py`.
- [x] `W02.P02.S11` - verify residual ledger behavior and ratchet ledger root size after extraction; `src/aeat/entrypoints/cli/tests/test_ledger* src/aeat/entrypoints/cli/tests/test_cli_module_size.py`.

### Phase `W02.P03` - live and modelo root continuation

Continue reducing _app_live.py, _modelo.py, and config CLI roots after ledger slices, preserving command registrations and tests.

- [x] `W02.P03.S06` - select the next live CLI command group for extraction using exact and semantic discovery; `src/aeat/entrypoints/cli/_app_live.py src/aeat/entrypoints/cli/tests`.
- [x] `W02.P03.S12` - extract the selected live CLI command group into a focused registrar module; `src/aeat/entrypoints/cli/_app_live.py src/aeat/entrypoints/cli/_app_live_*.py`.
- [x] `W02.P03.S13` - verify selected live CLI behavior and ratchet live root size after extraction; `src/aeat/entrypoints/cli/tests/test_live* src/aeat/entrypoints/cli/tests/test_cli_module_size.py`.
- [x] `W02.P03.S14` - select the next modelo CLI command group for extraction using exact and semantic discovery; `src/aeat/entrypoints/cli/_modelo.py src/aeat/entrypoints/cli/tests`.
- [x] `W02.P03.S15` - extract the selected modelo CLI command group into a focused registrar module; `src/aeat/entrypoints/cli/_modelo.py src/aeat/entrypoints/cli/_modelo_*.py`.
- [x] `W02.P03.S16` - verify selected modelo CLI behavior and ratchet modelo root size after extraction; `src/aeat/entrypoints/cli/tests/test_modelo* src/aeat/entrypoints/cli/tests/test_cli_module_size.py`.
- [x] `W02.P03.S17` - select the next config CLI command group for extraction using exact and semantic discovery; `src/aeat/entrypoints/cli/_config/__init__.py src/aeat/entrypoints/cli/_config/_google.py src/aeat/entrypoints/cli/_config/tests`.
- [x] `W02.P03.S18` - extract the selected config CLI command group into a focused registrar module; `src/aeat/entrypoints/cli/_config/__init__.py src/aeat/entrypoints/cli/_config/*.py`.
- [x] `W02.P03.S19` - verify selected config CLI behavior and ratchet config root size after extraction; `src/aeat/entrypoints/cli/_config/tests src/aeat/entrypoints/cli/tests/test_cli_module_size.py`.
- [x] `W02.P03.S20` - select the next residual config or google CLI command group for extraction using exact and semantic discovery; `src/aeat/entrypoints/cli/_config/__init__.py src/aeat/entrypoints/cli/_config/_google.py src/aeat/entrypoints/cli/_config/tests src/aeat/entrypoints/cli/tests`.
- [x] `W02.P03.S21` - extract the selected residual config or google CLI command group into a focused registrar module; `src/aeat/entrypoints/cli/_config/__init__.py src/aeat/entrypoints/cli/_config/*.py`.
- [x] `W02.P03.S22` - verify residual config or google CLI behavior and ratchet affected root size budgets; `src/aeat/entrypoints/cli/_config/tests src/aeat/entrypoints/cli/tests/test_cli_module_size.py`.
- [x] `W02.P03.S23` - select the next residual ledger CLI command group for extraction using exact and semantic discovery; `src/aeat/entrypoints/cli/_ledger.py src/aeat/entrypoints/cli/tests`.
- [x] `W02.P03.S24` - extract the selected residual ledger CLI command group into a focused registrar module; `src/aeat/entrypoints/cli/_ledger.py src/aeat/entrypoints/cli/_ledger_*.py`.
- [x] `W02.P03.S25` - verify residual ledger CLI behavior and ratchet ledger root size budget; `src/aeat/entrypoints/cli/tests/test_ledger* src/aeat/entrypoints/cli/tests/test_cli_module_size.py`.
- [x] `W02.P03.S26` - select the next residual live CLI command group for extraction using exact and semantic discovery; `src/aeat/entrypoints/cli/_app_live.py src/aeat/entrypoints/cli/tests`.
- [x] `W02.P03.S27` - extract the selected residual live CLI command group into a focused registrar module; `src/aeat/entrypoints/cli/_app_live.py src/aeat/entrypoints/cli/_app_live_*.py`.
- [x] `W02.P03.S28` - verify residual live CLI behavior and ratchet live root size budget; `src/aeat/entrypoints/cli/tests/test_live* src/aeat/entrypoints/cli/tests/test_cli_module_size.py`.
- [x] `W02.P03.S29` - select the next residual modelo CLI command group for extraction using exact and semantic discovery; `src/aeat/entrypoints/cli/_modelo.py src/aeat/entrypoints/cli/tests`.
- [x] `W02.P03.S30` - extract the selected residual modelo CLI command group into a focused registrar module; `src/aeat/entrypoints/cli/_modelo.py src/aeat/entrypoints/cli/_modelo_*.py`.
- [x] `W02.P03.S31` - verify residual modelo CLI behavior and ratchet modelo root size budget; `src/aeat/entrypoints/cli/tests/test_modelo* src/aeat/entrypoints/cli/tests/test_cli_module_size.py`.

### Phase `W02.P05` - residual CLI root closure

Close remaining oversized CLI roots through explicit residual extraction tranches before backend ADR decomposition, preserving CLI transport-only behavior and public facade imports.

- [x] `W02.P05.S32` - select the next ledger root closure command group using exact and semantic discovery; `src/aeat/entrypoints/cli/_ledger.py src/aeat/entrypoints/cli/tests`.
- [x] `W02.P05.S33` - extract the selected ledger root closure command group into a focused registrar module; `src/aeat/entrypoints/cli/_ledger.py src/aeat/entrypoints/cli/_ledger_*.py`.
- [x] `W02.P05.S34` - verify ledger root closure behavior and ratchet ledger size budget; `src/aeat/entrypoints/cli/tests/test_ledger* src/aeat/entrypoints/cli/tests/test_cli_module_size.py`.
- [x] `W02.P05.S35` - select the next config root closure command group using exact and semantic discovery; `src/aeat/entrypoints/cli/_config/__init__.py src/aeat/entrypoints/cli/_config/tests`.
- [x] `W02.P05.S36` - extract the selected config root closure command group into a focused registrar module; `src/aeat/entrypoints/cli/_config/__init__.py src/aeat/entrypoints/cli/_config/*.py`.
- [x] `W02.P05.S37` - verify config root closure behavior and ratchet config size budget; `src/aeat/entrypoints/cli/_config/tests src/aeat/entrypoints/cli/tests/test_cli_module_size.py`.
- [x] `W02.P05.S38` - select the next live root closure command group using exact and semantic discovery; `src/aeat/entrypoints/cli/_app_live.py src/aeat/entrypoints/cli/tests`.
- [x] `W02.P05.S39` - extract the selected live root closure command group into a focused registrar module; `src/aeat/entrypoints/cli/_app_live.py src/aeat/entrypoints/cli/_app_live_*.py`.
- [x] `W02.P05.S40` - verify live root closure behavior and ratchet live size budget; `src/aeat/entrypoints/cli/tests/test_live* src/aeat/entrypoints/cli/tests/test_cli_module_size.py`.
- [x] `W02.P05.S41` - select the next modelo root closure command group using exact and semantic discovery; `src/aeat/entrypoints/cli/_modelo.py src/aeat/entrypoints/cli/tests`.
- [x] `W02.P05.S42` - extract the selected modelo root closure command group into a focused registrar module; `src/aeat/entrypoints/cli/_modelo.py src/aeat/entrypoints/cli/_modelo_*.py`.
- [x] `W02.P05.S43` - verify modelo root closure behavior and ratchet modelo size budget; `src/aeat/entrypoints/cli/tests/test_modelo* src/aeat/entrypoints/cli/tests/test_cli_module_size.py`.
- [x] `W02.P05.S44` - select the next google config closure command group using exact and semantic discovery; `src/aeat/entrypoints/cli/_config/_google.py src/aeat/entrypoints/cli/_config/tests`.
- [x] `W02.P05.S45` - extract the selected google config closure command group into a focused registrar module; `src/aeat/entrypoints/cli/_config/_google.py src/aeat/entrypoints/cli/_config/*.py`.
- [x] `W02.P05.S46` - verify google config closure behavior and ratchet google size budget; `src/aeat/entrypoints/cli/_config/tests src/aeat/entrypoints/cli/tests/test_cli_module_size.py`.
- [x] `W02.P05.S47` - select the next residual ledger root command group using exact and semantic discovery; `src/aeat/entrypoints/cli/_ledger.py src/aeat/entrypoints/cli/tests`.
- [x] `W02.P05.S48` - extract the selected residual ledger root command group into a focused registrar module; `src/aeat/entrypoints/cli/_ledger.py src/aeat/entrypoints/cli/_ledger_*.py`.
- [x] `W02.P05.S49` - verify residual ledger root behavior and ratchet ledger size budget; `src/aeat/entrypoints/cli/tests/test_ledger* src/aeat/entrypoints/cli/tests/test_cli_module_size.py`.
- [x] `W02.P05.S50` - select the next residual config root command group using exact and semantic discovery; `src/aeat/entrypoints/cli/_config/__init__.py src/aeat/entrypoints/cli/_config/tests`.
- [x] `W02.P05.S51` - extract the selected residual config root command group into a focused registrar module; `src/aeat/entrypoints/cli/_config/__init__.py src/aeat/entrypoints/cli/_config/*.py`.
- [x] `W02.P05.S52` - verify residual config root behavior and ratchet config size budget; `src/aeat/entrypoints/cli/_config/tests src/aeat/entrypoints/cli/tests/test_cli_module_size.py`.
- [x] `W02.P05.S93` - Migrate stale ledger integration fixtures to UUID-safe profile registration; `src/aeat/entrypoints/cli/tests/test_ledger_validation_paths.py; src/aeat/entrypoints/cli/tests/test_ledger_ux_defect_cluster.py`.
- [x] `W02.P05.S94` - select the next residual config repair command group using exact discovery; `src/aeat/entrypoints/cli/_config/__init__.py src/aeat/entrypoints/cli/_config/tests`.
- [x] `W02.P05.S95` - extract the selected config repair command group into a focused registrar module; `src/aeat/entrypoints/cli/_config/__init__.py src/aeat/entrypoints/cli/_config/*.py`.
- [x] `W02.P05.S96` - verify config repair behavior and ratchet config size budget; `src/aeat/entrypoints/cli/_config/tests src/aeat/entrypoints/cli/tests/test_cli_module_size.py`.
- [x] `W02.P05.S97` - select the next config bucket/history command group using exact and semantic discovery; `src/aeat/entrypoints/cli/_config/__init__.py src/aeat/entrypoints/cli/_config/tests src/aeat/entrypoints/cli/tests`.
- [x] `W02.P05.S98` - extract the selected config bucket/history command group into a focused registrar module; `src/aeat/entrypoints/cli/_config/__init__.py src/aeat/entrypoints/cli/_config/*.py`.
- [x] `W02.P05.S99` - verify config bucket/history behavior and ratchet config size budget; `src/aeat/entrypoints/cli/tests/test_profile_lifecycle_verbs.py src/aeat/entrypoints/cli/tests/test_cli_module_size.py`.
- [x] `W02.P05.S100` - verify dirty modelo work fragment import regression exposed by output-language parity does not reproduce in a fresh process; `src/aeat/entrypoints/cli/_modelo*.py src/aeat/entrypoints/cli/tests/test_output_language_parity.py`.
- [x] `W02.P05.S101` - select the next config profile command group using exact and semantic discovery; `src/aeat/entrypoints/cli/_config/__init__.py src/aeat/entrypoints/cli/_config/tests src/aeat/entrypoints/cli/tests`.
- [ ] `W02.P05.S102` - extract the selected config profile command group into a focused registrar module; `src/aeat/entrypoints/cli/_config/__init__.py src/aeat/entrypoints/cli/_config/*.py`.
- [ ] `W02.P05.S103` - verify config profile behavior and ratchet config size budget; `src/aeat/entrypoints/cli/tests/test_profile_lifecycle_verbs.py src/aeat/entrypoints/cli/tests/test_cli_module_size.py`.
- [ ] `W02.P05.S104` - select the next ledger residual command group using exact and semantic discovery; `src/aeat/entrypoints/cli/_ledger.py src/aeat/entrypoints/cli/tests`.
- [ ] `W02.P05.S105` - extract the selected ledger residual command group into a focused registrar module; `src/aeat/entrypoints/cli/_ledger.py src/aeat/entrypoints/cli/_ledger_*.py`.
- [ ] `W02.P05.S106` - verify ledger residual behavior and ratchet ledger size budget; `src/aeat/entrypoints/cli/tests/test_ledger* src/aeat/entrypoints/cli/tests/test_cli_module_size.py`.
- [ ] `W02.P05.S107` - select a coherent split for oversized modelo CLI tests using exact discovery; `src/aeat/entrypoints/cli/tests/test_modelo.py src/aeat/entrypoints/cli/tests`.
- [ ] `W02.P05.S108` - split selected modelo CLI tests into focused test modules; `src/aeat/entrypoints/cli/tests/test_modelo.py src/aeat/entrypoints/cli/tests/test_modelo_*.py`.
- [ ] `W02.P05.S109` - verify split modelo CLI tests and ratchet test module size budget; `src/aeat/entrypoints/cli/tests/test_modelo.py src/aeat/entrypoints/cli/tests/test_modelo_*.py src/aeat/entrypoints/cli/tests/test_cli_module_size.py`.
- [x] `W02.P05.S110` - extract residual modelo audit command group into a focused registrar module; `src/aeat/entrypoints/cli/_modelo.py src/aeat/entrypoints/cli/_modelo_audit_cli.py`.
- [x] `W02.P05.S111` - verify modelo audit behavior and repair-policy discovery after extraction; `src/aeat/entrypoints/cli/tests/test_audit_verbs.py src/aeat/entrypoints/cli/tests/test_root_grammar_invariants.py src/aeat/entrypoints/cli/tests/test_repair_policy_coverage.py`.
- [ ] `W02.P05.S112` - reconcile modelo natural-key CLI verification coverage with cross-period clean-state requirements; `src/aeat/entrypoints/cli/tests/test_modelo_work_natural_key.py src/aeat/application/modelo/tests/test_cross_period_clean_state_* src/aeat/entrypoints/cli/tests/test_modelo_work_ux.py`.

## Wave `W03` - application and domain monolith decomposition

Decompose application/domain/backend monoliths only after ADR-backed boundary decisions identify safe seams and public facade preservation rules.

### Phase `W03.P04` - ADR bounded backend decomposition

Queue and execute ADR-backed decomposition for application, domain, adapter, persistence, and core modules over 1250 lines where safe boundaries require design decisions.

- [x] `W03.P04.S07` - queue ADRs for application/domain/adapter/core monoliths whose decomposition requires boundary decisions; `.vault/adr src/aeat/application src/aeat/domain src/aeat/adapters src/aeat/core`.
- [ ] `W03.P04.S08` - add or extend static guards proving no Python module exceeds 1250 lines and no tracked callable exceeds the complexity budget; `src/aeat/tests src/aeat/entrypoints/cli/tests`.

### Phase `W03.P06` - application service facade decomposition

Decompose oversized application service modules by use-case boundary while preserving top-level application facades and keeping adapters out of application internals.

- [x] `W03.P06.S53` - decompose application modelo actions by use-case helpers behind the public modelo application facade; `src/aeat/application/modelo/_actions.py src/aeat/application/modelo/*.py`.
- [x] `W03.P06.S54` - verify application modelo action behavior and facade imports after decomposition; `src/aeat/application/modelo/tests src/aeat/entrypoints/cli/tests/test_modelo*`.
- [ ] `W03.P06.S55` - decompose application ledger actions by orchestration boundary behind the public ledger application facade; `src/aeat/application/ledger/_actions.py src/aeat/application/ledger/*.py`.
- [ ] `W03.P06.S56` - verify application ledger action behavior and facade imports after decomposition; `src/aeat/application/ledger/tests src/aeat/entrypoints/cli/tests/test_ledger*`.
- [ ] `W03.P06.S57` - decompose application live package root by service family while preserving public live facade imports; `src/aeat/application/live/__init__.py src/aeat/application/live/*.py`.
- [ ] `W03.P06.S58` - verify application live behavior and public live facade imports after decomposition; `src/aeat/application/live/tests src/aeat/entrypoints/cli/tests/test_live*`.
- [ ] `W03.P06.S59` - decompose application auth operator module by credential and authority workflows behind the auth facade; `src/aeat/application/auth/_operator.py src/aeat/application/auth/*.py`.
- [ ] `W03.P06.S60` - verify application auth operator behavior and facade imports after decomposition; `src/aeat/application/auth/tests src/aeat/entrypoints/cli/_config/tests`.
- [ ] `W03.P06.S61` - decompose application workflow engine by execution and adapter orchestration helpers behind the workflow facade; `src/aeat/application/workflow/_engine.py src/aeat/application/workflow/*.py`.
- [ ] `W03.P06.S62` - verify application workflow engine behavior and facade imports after decomposition; `src/aeat/application/workflow/tests src/aeat/tests`.

### Phase `W03.P07` - domain registry decomposition

Decompose oversized calculation registry modules by schema, binding, applicability, parity, and record-design ownership without importing application or adapter layers.

- [ ] `W03.P07.S63` - decompose registry bindings module by binding group and relation ownership behind the registry facade; `src/aeat/domain/calculations/registry/_bindings.py src/aeat/domain/calculations/registry/*.py`.
- [ ] `W03.P07.S64` - verify registry binding behavior and facade imports after decomposition; `src/aeat/domain/calculations/registry/tests/test_*binding* src/aeat/domain/calculations/registry/tests`.
- [ ] `W03.P07.S65` - decompose registry schema module by schema family and validation ownership behind the registry facade; `src/aeat/domain/calculations/registry/_schema.py src/aeat/domain/calculations/registry/*.py`.
- [ ] `W03.P07.S66` - verify registry schema behavior and facade imports after decomposition; `src/aeat/domain/calculations/registry/tests/test_registry_schema.py src/aeat/domain/calculations/registry/tests`.
- [ ] `W03.P07.S67` - decompose registry record design module by record authority surface behind the registry facade; `src/aeat/domain/calculations/registry/_record_design.py src/aeat/domain/calculations/registry/*.py`.
- [ ] `W03.P07.S68` - verify registry record design behavior and facade imports after decomposition; `src/aeat/domain/calculations/registry/tests src/aeat/tests`.
- [ ] `W03.P07.S69` - decompose registry applicability module by applicability rule family behind the registry facade; `src/aeat/domain/calculations/registry/_applicability.py src/aeat/domain/calculations/registry/*.py`.
- [ ] `W03.P07.S70` - verify registry applicability behavior and facade imports after decomposition; `src/aeat/domain/calculations/registry/tests/test_applicability* src/aeat/domain/calculations/registry/tests`.
- [ ] `W03.P07.S71` - decompose registry workbook parity module by parity concern behind the registry facade; `src/aeat/domain/calculations/registry/_workbook_parity.py src/aeat/domain/calculations/registry/*.py`.
- [ ] `W03.P07.S72` - verify registry workbook parity behavior and facade imports after decomposition; `src/aeat/domain/calculations/registry/tests src/aeat/adapters/outbound/google/tests`.

### Phase `W03.P08` - adapter and persistence decomposition

Decompose oversized outbound adapter and persistence modules along external contract and storage boundary lines while preserving typed boundary errors.

- [ ] `W03.P08.S73` - decompose AEAT sede declarations adapter by declaration workflow behind the outbound AEAT facade; `src/aeat/adapters/outbound/aeat/sede/_declarations.py src/aeat/adapters/outbound/aeat/sede/*.py`.
- [ ] `W03.P08.S74` - verify AEAT sede declarations adapter behavior and facade imports after decomposition; `src/aeat/adapters/outbound/aeat/sede/tests src/aeat/entrypoints/cli/tests/test_live*`.
- [ ] `W03.P08.S75` - decompose AEAT auth adapters by clave movil and authenticator workflow behind the outbound AEAT auth facade; `src/aeat/adapters/outbound/aeat/auth/_clave_movil.py src/aeat/adapters/outbound/aeat/auth/_authenticator.py src/aeat/adapters/outbound/aeat/auth/*.py`.
- [ ] `W03.P08.S76` - verify AEAT auth adapter behavior and facade imports after decomposition; `src/aeat/adapters/outbound/aeat/auth/tests src/aeat/entrypoints/cli/_config/tests`.
- [ ] `W03.P08.S77` - decompose Google calc sheets apply adapter by Sheets API write concern behind the outbound Google facade; `src/aeat/adapters/outbound/google/_calc_sheets_apply.py src/aeat/adapters/outbound/google/*.py`.
- [ ] `W03.P08.S78` - verify Google calc sheets apply behavior and facade imports after decomposition; `src/aeat/adapters/outbound/google/tests src/aeat/entrypoints/cli/_config/tests/test_google*`.
- [ ] `W03.P08.S79` - decompose SQL secure objects persistence by row, crypto, and repository concerns behind the storage facade; `src/aeat/adapters/persistence/storage/sql/secure_objects.py src/aeat/adapters/persistence/storage/sql/*.py`.
- [ ] `W03.P08.S80` - verify SQL secure objects persistence behavior and facade imports after decomposition; `src/aeat/adapters/persistence/storage/sql/tests src/aeat/tests/test_storage_decimal_redaction_error_typing.py`.
- [ ] `W03.P08.S81` - decompose master key storage adapter by derivation, rotation, and persistence concerns behind the storage facade; `src/aeat/adapters/persistence/storage/master_key/_master_key.py src/aeat/adapters/persistence/storage/master_key/*.py`.
- [ ] `W03.P08.S82` - verify master key storage behavior and facade imports after decomposition; `src/aeat/adapters/persistence/storage/master_key/tests src/aeat/adapters/persistence/storage/tests`.

## Wave `W04` - core and final static guard closure

Close core over-limit modules and replace shrinking legacy budgets with hard codebase-wide line and callable guards once all decomposition evidence is clean.

### Phase `W04.P09` - core module and hard guard closure

Decompose oversized core modules, then enforce hard codebase-wide module and callable budgets with no silent legacy growth.

- [ ] `W04.P09.S83` - decompose core config module by settings source and validation concern behind the core config facade; `src/aeat/core/config.py src/aeat/core/*.py`.
- [ ] `W04.P09.S84` - verify core config behavior and facade imports after decomposition; `src/aeat/core/tests src/aeat/tests`.
- [ ] `W04.P09.S85` - decompose core error registry domain module behind the core errors facade; `src/aeat/core/errors/registry/_domain.py src/aeat/core/errors/registry/*.py`.
- [ ] `W04.P09.S86` - verify core domain error registry behavior and facade imports after decomposition; `src/aeat/core/errors/tests src/aeat/core/tests`.
- [ ] `W04.P09.S87` - decompose core error registry application module behind the core errors facade; `src/aeat/core/errors/registry/_application.py src/aeat/core/errors/registry/*.py`.
- [ ] `W04.P09.S88` - verify core application error registry behavior and facade imports after decomposition; `src/aeat/core/errors/tests src/aeat/core/tests`.
- [ ] `W04.P09.S89` - decompose core error registry adapters module behind the core errors facade; `src/aeat/core/errors/registry/_adapters.py src/aeat/core/errors/registry/*.py`.
- [ ] `W04.P09.S90` - verify core adapter error registry behavior and facade imports after decomposition; `src/aeat/core/errors/tests src/aeat/core/tests`.
- [ ] `W04.P09.S91` - replace shrinking legacy size budgets with hard codebase-wide 1250-line and callable-complexity guards; `src/aeat/tests src/aeat/entrypoints/cli/tests`.
- [ ] `W04.P09.S92` - run final codebase monolith decomposition feature gate and refresh RAG index; `.vault/plan/2026-06-05-codebase-monolith-decomposition-plan.md src/aeat`.

## Description

Deliver the codebase-wide monolith decomposition objective: no Python module over 1250 lines and no cognitively high-scoring function left unbroken or unbounded by an explicit guard. This plan starts from current-state inventory rather than prior assumptions, then decomposes the remaining CLI roots through focused registrars and queues ADR-backed backend decomposition for application/domain/adapter/core modules where boundaries require design decisions.

The immediate execution path is conservative: keep CLI modules as transports, preserve top-level application facades for consumers, and ratchet static guards after every slice. Backend monoliths are not split by string-moving; each decomposition must preserve domain ownership, storage contracts, and public re-export surfaces.

## Parallelization

Inventory and semantic discovery may run in parallel with exact `fd`/`rg` discovery. File edits, plan mutations, and budget ratchets must stay serialized. CLI command group extractions can run independently by subgroup once their command surfaces and tests are identified. Backend application/domain decomposition must be ADR-bounded before implementation because public facade and ownership decisions are part of the change.

## Verification

The plan is complete only when current-state evidence proves no Python module in `src/aeat` exceeds 1250 lines, no tracked callable exceeds the accepted complexity/length budget, all broad static guards pass, focused behavior tests pass for every extracted surface, `vaultspec-core vault plan check` passes, and exact plus semantic discovery show command transports consume backend/application services rather than owning business policy.
