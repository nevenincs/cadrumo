---
tags:
  - '#plan'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
modified: '2026-06-05'
tier: L3
related:
  - '[[2026-06-05-codebase-monolith-decomposition-adr]]'
  - '[[2026-06-05-codebase-monolith-decomposition-research]]'
  - '[[2026-06-05-modelo-work-revision-cli-decomposition-plan]]'
---


# `codebase-monolith-decomposition` `codebase-wide monolith and cognitive complexity decomposition` plan

## Wave `W01` - global inventory and guard baseline

Establish authoritative current-state evidence for every production and test module over 1250 lines and every high-scoring function before selecting decomposition slices.

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
- [x] `W02.P05.S102` - extract the selected config profile command group into a focused registrar module; `src/aeat/entrypoints/cli/_config/__init__.py src/aeat/entrypoints/cli/_config/*.py`.
- [x] `W02.P05.S103` - verify config profile behavior and ratchet config size budget; `src/aeat/entrypoints/cli/tests/test_profile_lifecycle_verbs.py src/aeat/entrypoints/cli/tests/test_cli_module_size.py`.
- [x] `W02.P05.S104` - select the next ledger residual command group using exact and semantic discovery; `src/aeat/entrypoints/cli/_ledger.py src/aeat/entrypoints/cli/tests`.
- [x] `W02.P05.S105` - extract the selected ledger residual command group into a focused registrar module; `src/aeat/entrypoints/cli/_ledger.py src/aeat/entrypoints/cli/_ledger_*.py`.
- [x] `W02.P05.S106` - verify ledger residual behavior and ratchet ledger size budget; `src/aeat/entrypoints/cli/tests/test_ledger* src/aeat/entrypoints/cli/tests/test_cli_module_size.py`.
- [x] `W02.P05.S107` - select a coherent split for oversized modelo CLI tests using exact discovery; `src/aeat/entrypoints/cli/tests/test_modelo.py src/aeat/entrypoints/cli/tests`.
- [x] `W02.P05.S108` - retire the selected modelo CLI test split as unnecessary after current line-count discovery; `src/aeat/entrypoints/cli/tests/test_modelo.py src/aeat/entrypoints/cli/tests`.
- [x] `W02.P05.S109` - verify modelo CLI test module remains below threshold and focused tests pass; `src/aeat/entrypoints/cli/tests/test_modelo.py src/aeat/entrypoints/cli/tests/test_cli_module_size.py`.
- [x] `W02.P05.S110` - extract residual modelo audit command group into a focused registrar module; `src/aeat/entrypoints/cli/_modelo.py src/aeat/entrypoints/cli/_modelo_audit_cli.py`.
- [x] `W02.P05.S111` - verify modelo audit behavior and repair-policy discovery after extraction; `src/aeat/entrypoints/cli/tests/test_audit_verbs.py src/aeat/entrypoints/cli/tests/test_root_grammar_invariants.py src/aeat/entrypoints/cli/tests/test_repair_policy_coverage.py`.
- [x] `W02.P05.S112` - reconcile modelo natural-key CLI verification coverage with cross-period clean-state requirements; `src/aeat/entrypoints/cli/tests/test_modelo_work_natural_key.py src/aeat/application/modelo/tests/test_cross_period_clean_state_* src/aeat/entrypoints/cli/tests/test_modelo_work_ux.py`.

### Phase `W02.P10` - residual CLI root second pass

Close any CLI roots still above the hard module budget after first-pass registrar extraction, preserving CLI-as-transport and backend-owned policy.

- [x] `W02.P10.S116` - select the next residual config CLI closure group using exact and semantic discovery; `src/aeat/entrypoints/cli/_config/__init__.py src/aeat/entrypoints/cli/_config/tests src/aeat/entrypoints/cli/tests`.
- [x] `W02.P10.S117` - extract the selected residual config CLI group into focused transport registrar modules; `src/aeat/entrypoints/cli/_config/__init__.py src/aeat/entrypoints/cli/_config/*.py`.
- [x] `W02.P10.S118` - verify residual config CLI behavior and ratchet config module size budget; `src/aeat/entrypoints/cli/_config/tests src/aeat/entrypoints/cli/tests/test_cli_module_size.py`.
- [x] `W02.P10.S143` - split residual config custody command registration into focused transport helpers without moving custody policy into CLI; `src/aeat/entrypoints/cli/_config/_custody.py src/aeat/entrypoints/cli/_config/tests`.
- [x] `W02.P10.S144` - split residual profile censo command registration into focused transport helpers without moving censo policy into CLI; `src/aeat/entrypoints/cli/_config/_profile_censo.py src/aeat/entrypoints/cli/_config/tests`.
- [x] `W02.P10.S145` - repair hard size-budget inventory for deleted or moved tracked paths and shrunken modelo compatibility modules; `src/aeat/tests/test_codebase_size_budgets.py src/aeat/application/modelo src/aeat/entrypoints/cli/tests`.
- [x] `W02.P10.S146` - verify residual config callable splits and hard size-budget inventory no longer fail on stale paths or config registrar callables; `src/aeat/entrypoints/cli/_config/tests src/aeat/entrypoints/cli/tests src/aeat/tests/test_codebase_size_budgets.py`.
- [x] `W02.P10.S150` - move profile censo bucket-event emission from config CLI into the user-profile application service; `src/aeat/application/user_profile/_censo_sync.py src/aeat/application/user_profile/__init__.py src/aeat/entrypoints/cli/_config/_profile_censo.py src/aeat/entrypoints/cli/tests/test_profile_censo_verbs.py`.
- [x] `W02.P10.S151` - split config secret-custody command registration into a focused transport helper without moving custody policy into CLI; `src/aeat/entrypoints/cli/_config/_custody.py src/aeat/entrypoints/cli/_config/_custody_secret.py src/aeat/entrypoints/cli/_config/tests src/aeat/entrypoints/cli/tests/test_config_custody_profile_lifecycle.py`.

## Wave `W03` - application and domain monolith decomposition

Decompose application/domain/backend monoliths only after ADR-backed boundary decisions identify safe seams and public facade preservation rules.

### Phase `W03.P04` - ADR bounded backend decomposition

Queue and execute ADR-backed decomposition for application, domain, adapter, persistence, and core modules over 1250 lines where safe boundaries require design decisions.

- [x] `W03.P04.S07` - queue ADRs for application/domain/adapter/core monoliths whose decomposition requires boundary decisions; `.vault/adr src/aeat/application src/aeat/domain src/aeat/adapters src/aeat/core`.
- [x] `W03.P04.S08` - add or extend static guards proving no Python module exceeds 1250 lines and no tracked callable exceeds the complexity budget; `src/aeat/tests src/aeat/entrypoints/cli/tests`.

### Phase `W03.P06` - application service facade decomposition

Decompose oversized application service modules by use-case boundary while preserving top-level application facades and keeping adapters out of application internals.

- [x] `W03.P06.S53` - decompose application modelo actions by use-case helpers behind the public modelo application facade; `src/aeat/application/modelo/_actions.py src/aeat/application/modelo/*.py`.
- [x] `W03.P06.S54` - verify application modelo action behavior and facade imports after decomposition; `src/aeat/application/modelo/tests src/aeat/entrypoints/cli/tests/test_modelo*`.
- [x] `W03.P06.S55` - decompose application ledger actions by orchestration boundary behind the public ledger application facade; `src/aeat/application/ledger/_actions.py src/aeat/application/ledger/*.py`.
- [x] `W03.P06.S56` - verify application ledger action behavior and facade imports after decomposition; `src/aeat/application/ledger/tests src/aeat/entrypoints/cli/tests/test_ledger*`.
- [x] `W03.P06.S57` - decompose application live package root by service family while preserving public live facade imports; `src/aeat/application/live/__init__.py src/aeat/application/live/*.py`.
- [x] `W03.P06.S58` - verify application live behavior and public live facade imports after decomposition; `src/aeat/application/live/tests src/aeat/entrypoints/cli/tests/test_live*`.
- [x] `W03.P06.S59` - decompose application auth operator module by credential and authority workflows behind the auth facade; `src/aeat/application/auth/_operator.py src/aeat/application/auth/*.py`.
- [x] `W03.P06.S60` - verify application auth operator behavior and facade imports after decomposition; `src/aeat/application/auth/tests src/aeat/entrypoints/cli/_config/tests`.
- [x] `W03.P06.S61` - decompose application workflow engine by execution and adapter orchestration helpers behind the workflow facade; `src/aeat/application/workflow/_engine.py src/aeat/application/workflow/*.py`.
- [x] `W03.P06.S62` - verify application workflow engine behavior and facade imports after decomposition; `src/aeat/application/workflow/tests src/aeat/tests`.
- [x] `W03.P06.S113` - extract live IVA remote-state outcome and redaction helpers behind the public live facade; `src/aeat/application/live/__init__.py src/aeat/application/live/_remote_state_outcomes.py src/aeat/application/live/tests/test_iva_remote_state_acquisition.py src/aeat/entrypoints/cli/tests/test_live_read_subgroups.py`.
- [x] `W03.P06.S114` - extract live filed-data selection and listing helpers behind the public live facade; `src/aeat/application/live/__init__.py src/aeat/application/live/_filed_data.py src/aeat/application/live/tests src/aeat/entrypoints/cli/tests/test_registry_cli.py`.
- [x] `W03.P06.S115` - extract live filed-data capture service orchestration behind the public live facade; `src/aeat/application/live/__init__.py src/aeat/application/live/_session.py src/aeat/application/live/_filed_observation_persistence.py src/aeat/application/live/_filed_data_capture.py src/aeat/application/live/tests/test_filed_bulk_capture.py src/aeat/application/live/tests/test_filed_capture_calculation_history.py src/aeat/entrypoints/cli/tests/test_registry_cli.py`.

### Phase `W03.P07` - domain registry decomposition

Decompose oversized calculation registry modules by schema, binding, applicability, parity, and record-design ownership without importing application or adapter layers.

- [x] `W03.P07.S63` - decompose registry bindings module by binding group and relation ownership behind the registry facade; `src/aeat/domain/calculations/registry/_bindings.py src/aeat/domain/calculations/registry/*.py`.
- [x] `W03.P07.S64` - verify registry binding behavior and facade imports after decomposition; `src/aeat/domain/calculations/registry/tests/test_*binding* src/aeat/domain/calculations/registry/tests`.
- [x] `W03.P07.S65` - decompose registry schema module by schema family and validation ownership behind the registry facade; `src/aeat/domain/calculations/registry/_schema.py src/aeat/domain/calculations/registry/*.py`.
- [x] `W03.P07.S66` - verify registry schema behavior and facade imports after decomposition; `src/aeat/domain/calculations/registry/tests/test_registry_schema.py src/aeat/domain/calculations/registry/tests`.
- [x] `W03.P07.S67` - decompose registry record design module by record authority surface behind the registry facade; `src/aeat/domain/calculations/registry/_record_design.py src/aeat/domain/calculations/registry/*.py`.
- [x] `W03.P07.S68` - verify registry record design behavior and facade imports after decomposition; `src/aeat/domain/calculations/registry/tests src/aeat/tests`.
- [x] `W03.P07.S69` - decompose registry applicability module by applicability rule family behind the registry facade; `src/aeat/domain/calculations/registry/_applicability.py src/aeat/domain/calculations/registry/*.py`.
- [x] `W03.P07.S70` - verify registry applicability behavior and facade imports after decomposition; `src/aeat/domain/calculations/registry/tests/test_applicability* src/aeat/domain/calculations/registry/tests`.
- [x] `W03.P07.S71` - decompose registry workbook parity module by parity concern behind the registry facade; `src/aeat/domain/calculations/registry/_workbook_parity.py src/aeat/domain/calculations/registry/*.py`.
- [x] `W03.P07.S72` - verify registry workbook parity behavior and facade imports after decomposition; `src/aeat/domain/calculations/registry/tests src/aeat/adapters/outbound/google/tests`.

### Phase `W03.P08` - adapter and persistence decomposition

Decompose oversized outbound adapter and persistence modules along external contract and storage boundary lines while preserving typed boundary errors.

- [x] `W03.P08.S73` - decompose AEAT sede declarations adapter by declaration workflow behind the outbound AEAT facade; `src/aeat/adapters/outbound/aeat/sede/_declarations.py src/aeat/adapters/outbound/aeat/sede/*.py`.
- [x] `W03.P08.S74` - verify AEAT sede declarations adapter behavior and facade imports after decomposition; `src/aeat/adapters/outbound/aeat/sede/tests src/aeat/entrypoints/cli/tests/test_live*`.
- [x] `W03.P08.S75` - decompose AEAT auth adapters by clave movil and authenticator workflow behind the outbound AEAT auth facade; `src/aeat/adapters/outbound/aeat/auth/_clave_movil.py src/aeat/adapters/outbound/aeat/auth/_authenticator.py src/aeat/adapters/outbound/aeat/auth/*.py`.
- [x] `W03.P08.S76` - verify AEAT auth adapter behavior and facade imports after decomposition; `src/aeat/adapters/outbound/aeat/auth/tests src/aeat/entrypoints/cli/_config/tests`.
- [x] `W03.P08.S77` - decompose Google calc sheets apply adapter by Sheets API write concern behind the outbound Google facade; `src/aeat/adapters/outbound/google/_calc_sheets_apply.py src/aeat/adapters/outbound/google/*.py`.
- [x] `W03.P08.S78` - verify Google calc sheets apply behavior and facade imports after decomposition; `src/aeat/adapters/outbound/google/tests src/aeat/entrypoints/cli/_config/tests/test_google*`.
- [x] `W03.P08.S79` - decompose SQL secure objects persistence by row, crypto, and repository concerns behind the storage facade; `src/aeat/adapters/persistence/storage/sql/secure_objects.py src/aeat/adapters/persistence/storage/sql/*.py`.
- [x] `W03.P08.S80` - verify SQL secure objects persistence behavior and facade imports after decomposition; `src/aeat/adapters/persistence/storage/sql/tests src/aeat/tests/test_storage_decimal_redaction_error_typing.py`.
- [x] `W03.P08.S81` - decompose master key storage adapter by derivation, rotation, and persistence concerns behind the storage facade; `src/aeat/adapters/persistence/storage/master_key/_master_key.py src/aeat/adapters/persistence/storage/master_key/*.py`.
- [x] `W03.P08.S82` - verify master key storage behavior and facade imports after decomposition; `src/aeat/adapters/persistence/storage/master_key/tests src/aeat/adapters/persistence/storage/tests`.

### Phase `W03.P11` - residual application root closure

Close application package and service roots that remain oversized after first-pass decomposition while preserving public package facades and keeping business logic out of entrypoints.

- [x] `W03.P11.S119` - decompose residual modelo application actions by natural-key work and revision workflow behind the modelo facade; `src/aeat/application/modelo/_actions.py src/aeat/application/modelo/*.py`.
- [x] `W03.P11.S120` - verify residual modelo application behavior and public facade imports after action decomposition; `src/aeat/application/modelo/tests src/aeat/entrypoints/cli/tests/test_modelo*`.
- [x] `W03.P11.S121` - decompose residual live package root exports into focused private modules behind the public live facade; `src/aeat/application/live/__init__.py src/aeat/application/live/*.py`.
- [x] `W03.P11.S122` - verify residual live package behavior and public facade imports after root decomposition; `src/aeat/application/live/tests src/aeat/entrypoints/cli/tests/test_live*`.
- [x] `W03.P11.S123` - decompose overview application root by calendar and filing summary services behind the overview facade; `src/aeat/application/overview/__init__.py src/aeat/application/overview/*.py`.
- [x] `W03.P11.S124` - verify overview application behavior and public facade imports after root decomposition; `src/aeat/application/overview/tests src/aeat/entrypoints/cli/tests/test_overview*`.
- [x] `W03.P11.S133` - extract residual modelo calculation and bucket-aggregation workflows behind the modelo application facade without moving policy to CLI; `src/aeat/application/modelo/_actions.py src/aeat/application/modelo/_calculation_actions.py src/aeat/application/modelo/_calculation_helpers.py src/aeat/application/modelo/tests`.
- [x] `W03.P11.S134` - verify residual modelo calculation extraction preserves behavior and public facade imports; `src/aeat/application/modelo/tests src/aeat/entrypoints/cli/tests/test_modelo*`.
- [x] `W03.P11.S135` - extract residual modelo verification predicates findings clean-state and workflow-gate orchestration behind the modelo application facade; `src/aeat/application/modelo/_actions.py src/aeat/application/modelo/_verification_actions.py src/aeat/application/modelo/_verification_helpers.py src/aeat/application/modelo/tests`.
- [x] `W03.P11.S136` - verify residual modelo verification extraction preserves reports gates and public facade imports; `src/aeat/application/modelo/tests src/aeat/entrypoints/cli/tests/test_modelo*`.
- [x] `W03.P11.S137` - extract residual modelo filing record list get file supersession workflow behind the modelo application facade; `src/aeat/application/modelo/_actions.py src/aeat/application/modelo/_filing_actions.py src/aeat/application/modelo/tests`.
- [x] `W03.P11.S138` - verify residual modelo filing extraction preserves filing records supersession and public facade imports; `src/aeat/application/modelo/tests src/aeat/entrypoints/cli/tests/test_modelo*`.
- [x] `W03.P11.S139` - extract residual modelo amendment and external filing import workflows behind the modelo application facade; `src/aeat/application/modelo/_actions.py src/aeat/application/modelo/_amendment_actions.py src/aeat/application/modelo/_external_import_actions.py src/aeat/application/modelo/tests`.
- [x] `W03.P11.S140` - verify residual modelo amendment import extraction leaves _actions under the 1250-line budget and preserves facade-only consumers; `src/aeat/application/modelo src/aeat/entrypoints/cli src/aeat/tests/test_codebase_size_budgets.py`.
- [x] `W03.P11.S141` - remove residual modelo application-internal reach-through to the _actions compatibility facade where focused backend modules already own the implementation; `src/aeat/application/modelo/_history.py src/aeat/application/modelo/_calculate_input.py src/aeat/application/modelo/_projection.py src/aeat/application/modelo/_result_summary.py src/aeat/application/modelo/_work_addressing.py src/aeat/application/modelo/_export.py src/aeat/application/modelo/_taxation_comparison.py`.
- [x] `W03.P11.S142` - verify residual modelo facade-bound import cleanup preserves application behavior boundary guards and _actions compatibility exports; `src/aeat/application/modelo/tests src/aeat/entrypoints/cli/tests/test_architecture_boundaries.py src/aeat/tests/test_codebase_size_budgets.py`.

## Wave `W04` - core and final static guard closure

Close core over-limit modules and replace shrinking legacy budgets with hard codebase-wide line and callable guards once all decomposition evidence is clean.

### Phase `W04.P09` - core module and hard guard closure

Decompose oversized core modules, then enforce hard codebase-wide module and callable budgets with no silent legacy growth.

- [x] `W04.P09.S83` - decompose core config module by settings source and validation concern behind the core config facade; `src/aeat/core/config.py src/aeat/core/*.py`.
- [x] `W04.P09.S84` - verify core config behavior and facade imports after decomposition; `src/aeat/core/tests src/aeat/tests`.
- [x] `W04.P09.S85` - decompose core error registry domain module behind the core errors facade; `src/aeat/core/errors/registry/_domain.py src/aeat/core/errors/registry/*.py`.
- [x] `W04.P09.S86` - verify core domain error registry behavior and facade imports after decomposition; `src/aeat/core/errors/tests src/aeat/core/tests`.
- [x] `W04.P09.S87` - decompose core error registry application module behind the core errors facade; `src/aeat/core/errors/registry/_application.py src/aeat/core/errors/registry/*.py`.
- [x] `W04.P09.S88` - verify core application error registry behavior and facade imports after decomposition; `src/aeat/core/errors/tests src/aeat/core/tests`.
- [x] `W04.P09.S89` - decompose core error registry adapters module behind the core errors facade; `src/aeat/core/errors/registry/_adapters.py src/aeat/core/errors/registry/*.py`.
- [x] `W04.P09.S90` - verify core adapter error registry behavior and facade imports after decomposition; `src/aeat/core/errors/tests src/aeat/core/tests`.
- [x] `W04.P09.S152` - repair broad core meta-test path and external-constant alias failures discovered during S86 verification; `src/aeat/core/tests/test_external_constants.py src/aeat/core/tests/test_file_permissions.py src/aeat/adapters/outbound/aeat/sede/_declarations.py src/aeat/core/tests`.
- [x] `W04.P09.S156` - decompose remaining oversized production modules before enabling hard 1250-line module guard; `src/aeat/adapters/outbound/aeat/auth/_authenticator.py src/aeat/adapters/outbound/aeat/auth/_clave_movil.py src/aeat/adapters/outbound/aeat/sede/_declarations.py src/aeat/core/config.py src/aeat/domain/calculations/registry/_record_design.py`.
- [x] `W04.P09.S153` - decompose remaining oversized CLI transport registrars without moving business logic into entrypoints; `src/aeat/entrypoints/cli/_config/_profile_bundle.py src/aeat/entrypoints/cli/_config/_repair_cli.py src/aeat/entrypoints/cli/_ledger.py src/aeat/entrypoints/cli/_ledger_evidence_cli.py src/aeat/entrypoints/cli/_ledger_read_cli.py src/aeat/entrypoints/cli/_modelo_iva_wallet_cli.py src/aeat/entrypoints/cli/_modelo_projection_cli.py`.
- [x] `W04.P09.S154` - decompose remaining oversized non-CLI production callables behind existing backend facades; `src/aeat/adapters/outbound/google/_calc_sheets_apply.py src/aeat/application/ledger/_actions_split_merge.py src/aeat/core/observability/_context.py src/aeat/domain/calculations/registry/_validate_revision_sections.py src/aeat/domain/iva_compensation/_reconciliation.py`.
- [x] `W04.P09.S155` - verify no-legacy hard module and callable budgets after production residual decomposition; `src/aeat/tests/test_codebase_size_budgets.py src/aeat`.
- [x] `W04.P09.S91` - replace shrinking legacy size budgets with hard codebase-wide 1250-line and callable-complexity guards; `src/aeat/tests src/aeat/entrypoints/cli/tests`.
- [x] `W04.P09.S92` - run final codebase monolith decomposition feature gate and refresh RAG index; `.vault/plan/2026-06-05-codebase-monolith-decomposition-plan.md src/aeat`.
- [x] `W04.P09.S157` - extract declarations-register production helpers and split the corresponding outbound adapter tests; `src/aeat/adapters/outbound/aeat/sede/_declarations.py src/aeat/adapters/outbound/aeat/sede/_declarations_diagnostics.py src/aeat/adapters/outbound/aeat/sede/_declarations_remote.py src/aeat/adapters/outbound/aeat/sede/tests/test_declarations.py src/aeat/adapters/outbound/aeat/sede/tests/test_declarations_part1.py src/aeat/adapters/outbound/aeat/sede/tests/test_declarations_part2.py src/aeat/adapters/outbound/aeat/sede/tests/test_declarations_part3.py src/aeat/adapters/outbound/aeat/sede/tests/_declarations_support.py src/aeat/adapters/outbound/aeat/sede/tests/conftest.py`.

## Wave `W05` - residual test and fixture monolith closure

Split oversized test modules and fixture generators into focused real-behavior surfaces so the hard module-size guard applies to production and test code without tautological test logic.

### Phase `W05.P12` - test module and fixture generator closure

Decompose oversized real-behavior tests and support generators by behavioral surface while preserving production imports and avoiding fake, stub, monkeypatch, skip, or xfail shortcuts.

- [x] `W05.P12.S125` - decompose oversized justificante fixture generator by fixture family and generation concern; `src/aeat/tests/fixtures/justificantes/_generate.py src/aeat/tests/fixtures/justificantes/*.py`.
- [x] `W05.P12.S126` - split oversized application and overview behavior tests by workflow without duplicating business logic; `src/aeat/application/ledger/tests/test_actions.py src/aeat/application/modelo/tests/test_file_flow.py src/aeat/application/overview/tests/test_calendar.py src/aeat/application/*/tests`.
- [x] `W05.P12.S127` - split oversized inbound and outbound adapter tests by external contract surface; `src/aeat/adapters/inbound/declaracion/tests/test_verification_chain.py src/aeat/adapters/inbound/declaracion/tests/test_parser_boundary.py src/aeat/adapters/outbound/aeat/sede/tests/test_declarations.py src/aeat/adapters/outbound/aeat/auth/tests/test_authenticator.py src/aeat/adapters/persistence/storage/sql/tests/test_secure_objects.py src/aeat/adapters/persistence/storage/tests/test_runtime_migrated_repositories.py`.
- [x] `W05.P12.S128` - split oversized registry tests by schema and referential-integrity concern; `src/aeat/domain/calculations/registry/tests/test_registry_schema.py src/aeat/domain/calculations/registry/tests/test_referential_integrity.py src/aeat/domain/calculations/registry/tests`.
- [x] `W05.P12.S129` - verify split test and fixture surfaces plus hard size-budget inventory; `src/aeat/tests/test_codebase_size_budgets.py src/aeat/tests/fixtures/justificantes src/aeat/application src/aeat/adapters src/aeat/domain/calculations/registry/tests`.
- [x] `W05.P12.S147` - split the current overview calendar taxpayer-model and entity-type regression group into a focused test module without duplicating calendar business logic; `src/aeat/application/overview/tests/test_calendar.py src/aeat/application/overview/tests/test_calendar_taxpayer_model.py`.
- [x] `W05.P12.S148` - split the current declaracion parser synthetic-fixture regression group into a focused test module without duplicating parser business logic; `src/aeat/adapters/inbound/declaracion/tests/test_parser_boundary.py src/aeat/adapters/inbound/declaracion/tests/test_parser_synthetic_fixtures.py`.
- [x] `W05.P12.S149` - verify the current overview/parser split surfaces and hard size-budget guard after residual test decomposition; `src/aeat/application/overview/tests src/aeat/adapters/inbound/declaracion/tests src/aeat/tests/test_codebase_size_budgets.py`.

### Phase `W05.P13` - residual hard guard closure

Re-run exact and semantic discovery after every residual decomposition row, close any remaining over-budget module explicitly, and finish only when the hard guard and plan validation pass.

- [x] `W05.P13.S130` - refresh exact fd rg and vaultspec-rag monolith inventory after residual decomposition; `src/aeat .vault/plan/2026-06-05-codebase-monolith-decomposition-plan.md`.
- [x] `W05.P13.S131` - execute final hard size and callable-complexity gates for all tracked Python modules; `src/aeat/tests/test_codebase_size_budgets.py src/aeat`.
- [x] `W05.P13.S132` - run final plan validation feature-surface gate and RAG refresh for monolith decomposition; `.vault/plan/2026-06-05-codebase-monolith-decomposition-plan.md src/aeat .vault/exec/2026-06-05-codebase-monolith-decomposition`.

## Description

Deliver the codebase-wide monolith decomposition objective: no Python module over 1250 lines and no cognitively high-scoring function left unbroken or unbounded by an explicit guard. This plan starts from current-state inventory rather than prior assumptions, then decomposes the remaining CLI roots through focused registrars and queues ADR-backed backend decomposition for application/domain/adapter/core modules where boundaries require design decisions.

The immediate execution path is conservative: keep CLI modules as transports, preserve top-level application facades for consumers, and ratchet static guards after every slice. Backend monoliths are not split by string-moving; each decomposition must preserve domain ownership, storage contracts, and public re-export surfaces.

## Parallelization

Inventory and semantic discovery may run in parallel with exact `fd`/`rg` discovery. File edits, plan mutations, and budget ratchets must stay serialized. CLI command group extractions can run independently by subgroup once their command surfaces and tests are identified. Backend application/domain decomposition must be ADR-bounded before implementation because public facade and ownership decisions are part of the change.

## Verification

The plan is complete only when current-state evidence proves no Python module in `src/aeat` exceeds 1250 lines, no tracked callable exceeds the accepted complexity/length budget, all broad static guards pass, focused behavior tests pass for every extracted surface, `vaultspec-core vault plan check` passes, and exact plus semantic discovery show command transports consume backend/application services rather than owning business policy.
