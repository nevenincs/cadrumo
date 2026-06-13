---
tags:
  - '#plan'
  - '#emit-envelope-schema-burndown'
date: '2026-05-31'
modified: '2026-05-31'
tier: L3
related:
  - '[[2026-04-25-json-output-contract-adr]]'
  - '[[2026-05-18-linkage-design-audit-plan]]'
  - '[[2026-05-15-linkage-design-audit-reference]]'
  - '[[2026-06-04-emit-envelope-schema-burndown-research]]'
---


<!-- RETIRED: W07 -->

# `emit-envelope-schema-burndown` plan

## Wave `W01` - _ledger.py burndown - 34 bare emit sites

Migrate all 20 ledger-command emit sites in _ledger.py to typed OutputSchema subclasses in _ledger_payloads.py and register each with @register_schema. Phases within this Wave are independent and can be parallelised. Authorised by the json-output-contract ADR and the closed linkage-design-audit plan (P09 envelope-migration phase).

### Phase `W01.P01` - ledger mutation verbs payload module

Author OutputSchema subclasses for ledger add, update, classify, allocate, attach, archive, stash, remove, reset, split, and merge in _ledger_payloads.py and migrate their emit sites.

- [x] `W01.P01.S01` - author LedgerAddResult OutputSchema subclass with @register_schema decorator for ledger.add; `src/aeat/entrypoints/cli/_ledger_payloads.py`.
- [x] `W01.P01.S02` - migrate ledger_add bare emit site to _emit_envelope using typed LedgerAddResult; `src/aeat/entrypoints/cli/_ledger.py`.
- [x] `W01.P01.S03` - author LedgerUpdateResult OutputSchema subclass with @register_schema decorator for ledger.update; `src/aeat/entrypoints/cli/_ledger_payloads.py`.
- [x] `W01.P01.S04` - migrate ledger_update bare emit site to _emit_envelope using typed LedgerUpdateResult; `src/aeat/entrypoints/cli/_ledger.py`.
- [x] `W01.P01.S05` - author LedgerClassifyResult OutputSchema subclass with @register_schema decorator for ledger.classify; `src/aeat/entrypoints/cli/_ledger_payloads.py`.
- [x] `W01.P01.S06` - migrate ledger_classify bare emit site to _emit_envelope using typed LedgerClassifyResult; `src/aeat/entrypoints/cli/_ledger.py`.
- [x] `W01.P01.S07` - author LedgerAllocateResult OutputSchema subclass with @register_schema decorator for ledger.allocate; `src/aeat/entrypoints/cli/_ledger_payloads.py`.
- [x] `W01.P01.S08` - migrate ledger_allocate bare emit site to _emit_envelope using typed LedgerAllocateResult; `src/aeat/entrypoints/cli/_ledger.py`.
- [x] `W01.P01.S09` - author LedgerAttachResult OutputSchema subclass with @register_schema decorator for ledger.attach; `src/aeat/entrypoints/cli/_ledger_payloads.py`.
- [x] `W01.P01.S10` - migrate ledger_attach bare emit site to _emit_envelope using typed LedgerAttachResult; `src/aeat/entrypoints/cli/_ledger.py`.
- [x] `W01.P01.S11` - author LedgerArchiveResult OutputSchema subclass with @register_schema decorator for ledger.archive; `src/aeat/entrypoints/cli/_ledger_payloads.py`.
- [x] `W01.P01.S12` - migrate ledger_archive bare emit site to _emit_envelope using typed LedgerArchiveResult; `src/aeat/entrypoints/cli/_ledger.py`.
- [x] `W01.P01.S13` - author LedgerStashResult OutputSchema subclass with @register_schema decorator for ledger.stash; `src/aeat/entrypoints/cli/_ledger_payloads.py`.
- [x] `W01.P01.S14` - migrate ledger_stash bare emit site to _emit_envelope using typed LedgerStashResult; `src/aeat/entrypoints/cli/_ledger.py`.
- [x] `W01.P01.S15` - author LedgerRemoveResult OutputSchema subclass with @register_schema decorator for ledger.remove; `src/aeat/entrypoints/cli/_ledger_payloads.py`.
- [x] `W01.P01.S16` - migrate ledger_remove bare emit site to _emit_envelope using typed LedgerRemoveResult; `src/aeat/entrypoints/cli/_ledger.py`.
- [x] `W01.P01.S17` - author LedgerResetResult OutputSchema subclass with @register_schema decorator for ledger.reset; `src/aeat/entrypoints/cli/_ledger_payloads.py`.
- [x] `W01.P01.S18` - migrate ledger_reset bare emit site to _emit_envelope using typed LedgerResetResult; `src/aeat/entrypoints/cli/_ledger.py`.
- [x] `W01.P01.S19` - author LedgerSplitResult OutputSchema subclass with @register_schema decorator for ledger.split; `src/aeat/entrypoints/cli/_ledger_payloads.py`.
- [x] `W01.P01.S20` - migrate ledger_split bare emit site to _emit_envelope using typed LedgerSplitResult; `src/aeat/entrypoints/cli/_ledger.py`.
- [x] `W01.P01.S21` - author LedgerMergeResult OutputSchema subclass with @register_schema decorator for ledger.merge; `src/aeat/entrypoints/cli/_ledger_payloads.py`.
- [x] `W01.P01.S22` - migrate ledger_merge bare emit site to _emit_envelope using typed LedgerMergeResult; `src/aeat/entrypoints/cli/_ledger.py`.

### Phase `W01.P02` - ledger query verbs payload classes

Author OutputSchema subclasses for ledger list, view, status, history, and categories in _ledger_payloads.py and migrate their emit sites.

- [x] `W01.P02.S23` - author LedgerListResult OutputSchema subclass with @register_schema decorator for ledger.list; `src/aeat/entrypoints/cli/_ledger_payloads.py`.
- [x] `W01.P02.S24` - migrate ledger_list bare emit site to _emit_envelope using typed LedgerListResult; `src/aeat/entrypoints/cli/_ledger.py`.
- [x] `W01.P02.S25` - author LedgerViewResult OutputSchema subclass with @register_schema decorator for ledger.view; `src/aeat/entrypoints/cli/_ledger_payloads.py`.
- [x] `W01.P02.S26` - migrate ledger_view bare emit site to _emit_envelope using typed LedgerViewResult; `src/aeat/entrypoints/cli/_ledger.py`.
- [x] `W01.P02.S27` - author LedgerStatusResult OutputSchema subclass with @register_schema decorator for ledger.status; `src/aeat/entrypoints/cli/_ledger_payloads.py`.
- [x] `W01.P02.S28` - migrate ledger_status bare emit site to _emit_envelope using typed LedgerStatusResult; `src/aeat/entrypoints/cli/_ledger.py`.
- [x] `W01.P02.S29` - author LedgerHistoryResult OutputSchema subclass with @register_schema decorator for ledger.history; `src/aeat/entrypoints/cli/_ledger_payloads.py`.
- [x] `W01.P02.S30` - migrate ledger_history bare emit site to _emit_envelope using typed LedgerHistoryResult; `src/aeat/entrypoints/cli/_ledger.py`.
- [x] `W01.P02.S31` - author LedgerCategoriesResult OutputSchema subclass with @register_schema decorator for ledger.categories; `src/aeat/entrypoints/cli/_ledger_payloads.py`.
- [x] `W01.P02.S32` - migrate ledger_categories bare emit site to _emit_envelope using typed LedgerCategoriesResult; `src/aeat/entrypoints/cli/_ledger.py`.

### Phase `W01.P03` - ledger import/export/review verb payload classes

Author OutputSchema subclasses for ledger export, import, track, and review in _ledger_payloads.py and migrate their emit sites.

- [x] `W01.P03.S33` - author LedgerExportResult OutputSchema subclass with @register_schema decorator for ledger.export; `src/aeat/entrypoints/cli/_ledger_payloads.py`.
- [x] `W01.P03.S34` - migrate ledger_export bare emit site to _emit_envelope using typed LedgerExportResult; `src/aeat/entrypoints/cli/_ledger.py`.
- [x] `W01.P03.S35` - author LedgerImportResult OutputSchema subclass with @register_schema decorator for ledger.import; `src/aeat/entrypoints/cli/_ledger_payloads.py`.
- [x] `W01.P03.S36` - migrate ledger_import bare emit site to _emit_envelope using typed LedgerImportResult; `src/aeat/entrypoints/cli/_ledger.py`.
- [x] `W01.P03.S37` - author LedgerTrackResult OutputSchema subclass with @register_schema decorator for ledger.track; `src/aeat/entrypoints/cli/_ledger_payloads.py`.
- [x] `W01.P03.S38` - migrate ledger_track bare emit site to _emit_envelope using typed LedgerTrackResult; `src/aeat/entrypoints/cli/_ledger.py`.
- [x] `W01.P03.S39` - author LedgerReviewResult OutputSchema subclass with @register_schema decorator for ledger.review; `src/aeat/entrypoints/cli/_ledger_payloads.py`.
- [x] `W01.P03.S40` - migrate ledger_review bare emit site to _emit_envelope using typed LedgerReviewResult; `src/aeat/entrypoints/cli/_ledger.py`.

### Phase `W01.P04` - MIGRATED_COMMANDS extension and surface-test re-baseline for ledger

Append all 20 ledger command paths to MIGRATED_COMMANDS in test_json_schema_conformance.py and re-baseline any ledger CLI surface tests that previously asserted the bare-payload shape.

- [x] `W01.P04.S41` - append all 20 ledger command paths to MIGRATED_COMMANDS; `src/aeat/entrypoints/cli/test_json_schema_conformance.py`.
- [x] `W01.P04.S42` - import _ledger_payloads as side-effect in test_json_schema_conformance so @register_schema decorators populate SCHEMA_REGISTRY before gate inspection; `src/aeat/entrypoints/cli/test_json_schema_conformance.py`.
- [x] `W01.P04.S43` - re-baseline ledger CLI surface tests that previously asserted bare-payload JSON shape against the envelope schema shape; `src/aeat/entrypoints/cli/test_ledger.py`.

## Wave `W02` - _config/__init__.py burndown - 26 bare emit sites

Migrate all 19 config-command emit sites in _config/__init__.py to typed OutputSchema subclasses in _config_payloads.py. Phases within this Wave are independent and can be parallelised. Depends on W01 only for the established payload-module naming convention.

### Phase `W02.P05` - repair-verb payload classes

Author OutputSchema subclasses for repair logs, quarantine, reset-state, and connectivity in _config_payloads.py and migrate their emit sites.

- [x] `W02.P05.S44` - author RepairLogsResult OutputSchema subclass with @register_schema decorator for config.repair.logs; `src/aeat/entrypoints/cli/_config_payloads.py`.
- [x] `W02.P05.S45` - migrate repair_logs bare emit site to _emit_envelope using typed RepairLogsResult; `src/aeat/entrypoints/cli/_config/__init__.py`.
- [x] `W02.P05.S46` - author RepairQuarantineResult OutputSchema subclass with @register_schema decorator for config.repair.quarantine; `src/aeat/entrypoints/cli/_config_payloads.py`.
- [x] `W02.P05.S47` - migrate repair_quarantine bare emit site to _emit_envelope using typed RepairQuarantineResult; `src/aeat/entrypoints/cli/_config/__init__.py`.
- [x] `W02.P05.S48` - author RepairResetStateResult OutputSchema subclass with @register_schema decorator for config.repair.reset_state; `src/aeat/entrypoints/cli/_config_payloads.py`.
- [x] `W02.P05.S49` - migrate repair_reset_state bare emit site to _emit_envelope using typed RepairResetStateResult; `src/aeat/entrypoints/cli/_config/__init__.py`.
- [x] `W02.P05.S50` - author RepairConnectivityResult OutputSchema subclass with @register_schema decorator for config.repair.connectivity; `src/aeat/entrypoints/cli/_config_payloads.py`.
- [x] `W02.P05.S51` - migrate repair_connectivity bare emit site to _emit_envelope using typed RepairConnectivityResult; `src/aeat/entrypoints/cli/_config/__init__.py`.

### Phase `W02.P06` - config and profile verb payload classes

Author OutputSchema subclasses for config list, config profile switch/show/delete/duplicate, config status, and config reset in _config_payloads.py and migrate their emit sites.

- [x] `W02.P06.S52` - author ConfigListResult OutputSchema subclass with @register_schema decorator for config.list; `src/aeat/entrypoints/cli/_config_payloads.py`.
- [x] `W02.P06.S53` - migrate config_list bare emit site to _emit_envelope using typed ConfigListResult; `src/aeat/entrypoints/cli/_config/__init__.py`.
- [x] `W02.P06.S54` - author ConfigProfileSwitchResult OutputSchema subclass with @register_schema decorator for config.profile.switch; `src/aeat/entrypoints/cli/_config_payloads.py`.
- [x] `W02.P06.S55` - migrate config_profile_switch bare emit site to _emit_envelope using typed ConfigProfileSwitchResult; `src/aeat/entrypoints/cli/_config/__init__.py`.
- [x] `W02.P06.S56` - author ConfigProfileShowResult OutputSchema subclass with @register_schema decorator for config.profile.show; `src/aeat/entrypoints/cli/_config_payloads.py`.
- [x] `W02.P06.S57` - migrate config_profile_show bare emit site to _emit_envelope using typed ConfigProfileShowResult; `src/aeat/entrypoints/cli/_config/__init__.py`.
- [x] `W02.P06.S58` - author ConfigProfileDeleteResult OutputSchema subclass with @register_schema decorator for config.profile.delete; `src/aeat/entrypoints/cli/_config_payloads.py`.
- [x] `W02.P06.S59` - migrate config_profile_delete bare emit site to _emit_envelope using typed ConfigProfileDeleteResult; `src/aeat/entrypoints/cli/_config/__init__.py`.
- [x] `W02.P06.S60` - author ConfigProfileDuplicateResult OutputSchema subclass with @register_schema decorator for config.profile.duplicate; `src/aeat/entrypoints/cli/_config_payloads.py`.
- [x] `W02.P06.S61` - migrate config_profile_duplicate bare emit site to _emit_envelope using typed ConfigProfileDuplicateResult; `src/aeat/entrypoints/cli/_config/__init__.py`.
- [x] `W02.P06.S62` - author ConfigStatusResult OutputSchema subclass with @register_schema decorator for config.status; `src/aeat/entrypoints/cli/_config_payloads.py`.
- [x] `W02.P06.S63` - migrate config_status bare emit site to _emit_envelope using typed ConfigStatusResult; `src/aeat/entrypoints/cli/_config/__init__.py`.
- [x] `W02.P06.S64` - author ConfigResetResult OutputSchema subclass with @register_schema decorator for config.reset; `src/aeat/entrypoints/cli/_config_payloads.py`.
- [x] `W02.P06.S65` - migrate config_reset bare emit site to _emit_envelope using typed ConfigResetResult; `src/aeat/entrypoints/cli/_config/__init__.py`.

### Phase `W02.P07` - auth and bucket verb payload classes

Author OutputSchema subclasses for auth providers, configure, status, test, login, clear, apoderado check, and bucket history in _config_payloads.py and migrate their emit sites.

- [x] `W02.P07.S66` - author AuthProvidersResult OutputSchema subclass with @register_schema decorator for config.auth.providers; `src/aeat/entrypoints/cli/_config_payloads.py`.
- [x] `W02.P07.S67` - migrate auth_providers bare emit site to _emit_envelope using typed AuthProvidersResult; `src/aeat/entrypoints/cli/_config/__init__.py`.
- [x] `W02.P07.S68` - author AuthConfigureResult OutputSchema subclass with @register_schema decorator for config.auth.configure; `src/aeat/entrypoints/cli/_config_payloads.py`.
- [x] `W02.P07.S69` - migrate auth_configure bare emit site to _emit_envelope using typed AuthConfigureResult; `src/aeat/entrypoints/cli/_config/__init__.py`.
- [x] `W02.P07.S70` - author AuthStatusResult OutputSchema subclass with @register_schema decorator for config.auth.status; `src/aeat/entrypoints/cli/_config_payloads.py`.
- [x] `W02.P07.S71` - migrate auth_status bare emit site to _emit_envelope using typed AuthStatusResult; `src/aeat/entrypoints/cli/_config/__init__.py`.
- [x] `W02.P07.S72` - author AuthTestResult OutputSchema subclass with @register_schema decorator for config.auth.test; `src/aeat/entrypoints/cli/_config_payloads.py`.
- [x] `W02.P07.S73` - migrate auth_test bare emit site to _emit_envelope using typed AuthTestResult; `src/aeat/entrypoints/cli/_config/__init__.py`.
- [x] `W02.P07.S74` - author AuthLoginResult OutputSchema subclass with @register_schema decorator for config.auth.login; `src/aeat/entrypoints/cli/_config_payloads.py`.
- [x] `W02.P07.S75` - migrate auth_login bare emit site to _emit_envelope using typed AuthLoginResult; `src/aeat/entrypoints/cli/_config/__init__.py`.
- [x] `W02.P07.S76` - author AuthClearResult OutputSchema subclass with @register_schema decorator for config.auth.clear; `src/aeat/entrypoints/cli/_config_payloads.py`.
- [x] `W02.P07.S77` - migrate auth_clear bare emit site to _emit_envelope using typed AuthClearResult; `src/aeat/entrypoints/cli/_config/__init__.py`.
- [x] `W02.P07.S78` - author ApoderadoCheckResult OutputSchema subclass with @register_schema decorator for config.apoderado.check; `src/aeat/entrypoints/cli/_config_payloads.py`.
- [x] `W02.P07.S79` - migrate apoderado_check bare emit site to _emit_envelope using typed ApoderadoCheckResult; `src/aeat/entrypoints/cli/_config/__init__.py`.
- [x] `W02.P07.S80` - author BucketHistoryResult OutputSchema subclass with @register_schema decorator for config.bucket.history; `src/aeat/entrypoints/cli/_config_payloads.py`.
- [x] `W02.P07.S81` - migrate bucket_history bare emit site to _emit_envelope using typed BucketHistoryResult; `src/aeat/entrypoints/cli/_config/__init__.py`.

### Phase `W02.P08` - MIGRATED_COMMANDS extension and surface-test re-baseline for config

Append all 19 config command paths to MIGRATED_COMMANDS and re-baseline affected config CLI surface tests.

- [x] `W02.P08.S82` - append all 19 config command paths to MIGRATED_COMMANDS; `src/aeat/entrypoints/cli/test_json_schema_conformance.py`.
- [x] `W02.P08.S83` - import _config_payloads as side-effect in test_json_schema_conformance so @register_schema decorators populate SCHEMA_REGISTRY; `src/aeat/entrypoints/cli/test_json_schema_conformance.py`.
- [x] `W02.P08.S84` - re-baseline config CLI surface tests that previously asserted bare-payload JSON shape; `src/aeat/entrypoints/cli/test_config_setter.py`.

## Wave `W03` - _app_live.py burndown - 23 bare emit sites

Migrate the 3 live-AEAT-status command emit sites in _app_live.py to typed OutputSchema subclasses in _app_live_payloads.py. These three commands each carry a high per-command emit count and each gets a dedicated Phase. Depends on W01 for convention only.

### Phase `W03.P09` - filed-list payload class and emit migration

Author the OutputSchema subclass for the filed-list command in _app_live_payloads.py and migrate its emit sites.

- [x] `W03.P09.S85` - author FiledListResult OutputSchema subclass with @register_schema decorator for app.live.filed.list; `src/aeat/entrypoints/cli/_app_live_payloads.py`.
- [x] `W03.P09.S86` - migrate all filed_list_cmd bare emit sites to _emit_envelope using typed FiledListResult; `src/aeat/entrypoints/cli/_app_live.py`.

### Phase `W03.P10` - filed-capture payload class and emit migration

Author the OutputSchema subclass for the filed-capture command in _app_live_payloads.py and migrate its emit sites.

- [x] `W03.P10.S87` - author FiledCaptureResult OutputSchema subclass with @register_schema decorator for app.live.filed.capture; `src/aeat/entrypoints/cli/_app_live_payloads.py`.
- [x] `W03.P10.S88` - migrate all filed_capture_cmd bare emit sites to _emit_envelope using typed FiledCaptureResult; `src/aeat/entrypoints/cli/_app_live.py`.

### Phase `W03.P11` - filed-capture-sources payload class and emit migration

Author the OutputSchema subclass for the filed-capture-sources command in _app_live_payloads.py and migrate its emit sites.

- [x] `W03.P11.S89` - author FiledCaptureSourcesResult OutputSchema subclass with @register_schema decorator for app.live.filed.capture.sources; `src/aeat/entrypoints/cli/_app_live_payloads.py`.
- [x] `W03.P11.S90` - migrate all filed_capture_sources_cmd bare emit sites to _emit_envelope using typed FiledCaptureSourcesResult; `src/aeat/entrypoints/cli/_app_live.py`.

### Phase `W03.P12` - MIGRATED_COMMANDS extension and surface-test re-baseline for app_live

Append the 3 app_live command paths to MIGRATED_COMMANDS and re-baseline affected _app_live CLI surface tests.

- [x] `W03.P12.S91` - append the 3 app_live command paths to MIGRATED_COMMANDS; `src/aeat/entrypoints/cli/test_json_schema_conformance.py`.
- [x] `W03.P12.S92` - import _app_live_payloads as side-effect in test_json_schema_conformance; `src/aeat/entrypoints/cli/test_json_schema_conformance.py`.
- [x] `W03.P12.S93` - re-baseline _app_live CLI surface tests that previously asserted bare-payload JSON shape; `src/aeat/entrypoints/cli/test_live_read_subgroups.py`.

## Wave `W04` - _modelo.py burndown - 24 bare emit sites

Extend _modelo_payloads.py with OutputSchema subclasses for the 24 remaining bare emit sites in _modelo.py. The 12 already-migrated modelo.work.* verbs are excluded. Phases are grouped by verb family: audit/history verbs, record-query verbs, registry-projection verbs, and remaining singleton verbs. Depends on W01-W03 for pattern stability.

### Phase `W04.P13` - modelo audit/history verb payload classes

Author OutputSchema subclasses for audit check, audit show, audit export, audit replay, work history, and work runs in _modelo_payloads.py and migrate their emit sites.

- [x] `W04.P13.S94` - author ModeloAuditCheckResult OutputSchema subclass with @register_schema decorator for modelo.audit.check; `src/aeat/entrypoints/cli/_modelo_payloads.py`.
- [x] `W04.P13.S95` - migrate audit_check bare emit site to _emit_envelope using typed ModeloAuditCheckResult; `src/aeat/entrypoints/cli/_modelo.py`.
- [x] `W04.P13.S96` - author ModeloAuditShowResult OutputSchema subclass with @register_schema decorator for modelo.audit.show; `src/aeat/entrypoints/cli/_modelo_payloads.py`.
- [x] `W04.P13.S97` - migrate audit_show bare emit site to _emit_envelope using typed ModeloAuditShowResult; `src/aeat/entrypoints/cli/_modelo.py`.
- [x] `W04.P13.S98` - author ModeloAuditExportResult OutputSchema subclass with @register_schema decorator for modelo.audit.export; `src/aeat/entrypoints/cli/_modelo_payloads.py`.
- [x] `W04.P13.S99` - migrate audit_export bare emit site to _emit_envelope using typed ModeloAuditExportResult; `src/aeat/entrypoints/cli/_modelo.py`.
- [x] `W04.P13.S100` - author ModeloAuditReplayResult OutputSchema subclass with @register_schema decorator for modelo.audit.replay; `src/aeat/entrypoints/cli/_modelo_payloads.py`.
- [x] `W04.P13.S101` - migrate audit_replay bare emit site to _emit_envelope using typed ModeloAuditReplayResult; `src/aeat/entrypoints/cli/_modelo.py`.
- [x] `W04.P13.S102` - author WorkHistoryResult OutputSchema subclass with @register_schema decorator for modelo.work.history; `src/aeat/entrypoints/cli/_modelo_payloads.py`.
- [x] `W04.P13.S103` - migrate work_history bare emit site to _emit_envelope using typed WorkHistoryResult; `src/aeat/entrypoints/cli/_modelo.py`.
- [x] `W04.P13.S104` - author WorkRunsResult OutputSchema subclass with @register_schema decorator for modelo.work.runs; `src/aeat/entrypoints/cli/_modelo_payloads.py`.
- [x] `W04.P13.S105` - migrate work_runs bare emit site to _emit_envelope using typed WorkRunsResult; `src/aeat/entrypoints/cli/_modelo.py`.

### Phase `W04.P14` - modelo record-query verb payload classes

Author OutputSchema subclasses for filing record list, filing record show, filing record import, verification report list, and verification report show in _modelo_payloads.py and migrate their emit sites.

- [x] `W04.P14.S106` - author FilingRecordListResult OutputSchema subclass with @register_schema decorator for modelo.filing_record.list; `src/aeat/entrypoints/cli/_modelo_payloads.py`.
- [x] `W04.P14.S107` - migrate filing_record_list bare emit site to _emit_envelope using typed FilingRecordListResult; `src/aeat/entrypoints/cli/_modelo.py`.
- [x] `W04.P14.S108` - author FilingRecordShowResult OutputSchema subclass with @register_schema decorator for modelo.filing_record.show; `src/aeat/entrypoints/cli/_modelo_payloads.py`.
- [x] `W04.P14.S109` - migrate filing_record_show bare emit site to _emit_envelope using typed FilingRecordShowResult; `src/aeat/entrypoints/cli/_modelo.py`.
- [x] `W04.P14.S110` - author FilingRecordImportResult OutputSchema subclass with @register_schema decorator for modelo.filing_record.import; `src/aeat/entrypoints/cli/_modelo_payloads.py`.
- [x] `W04.P14.S111` - migrate filing_record_import bare emit site to _emit_envelope using typed FilingRecordImportResult; `src/aeat/entrypoints/cli/_modelo.py`.
- [x] `W04.P14.S112` - author VerificationReportListResult OutputSchema subclass with @register_schema decorator for modelo.verification_report.list; `src/aeat/entrypoints/cli/_modelo_payloads.py`.
- [x] `W04.P14.S113` - migrate verification_report_list bare emit site to _emit_envelope using typed VerificationReportListResult; `src/aeat/entrypoints/cli/_modelo.py`.
- [x] `W04.P14.S114` - author VerificationReportShowResult OutputSchema subclass with @register_schema decorator for modelo.verification_report.show; `src/aeat/entrypoints/cli/_modelo_payloads.py`.
- [x] `W04.P14.S115` - migrate verification_report_show bare emit site to _emit_envelope using typed VerificationReportShowResult; `src/aeat/entrypoints/cli/_modelo.py`.

### Phase `W04.P15` - modelo registry-projection verb payload classes

Author OutputSchema subclasses for list modelos, describe modelo, casillas, bindings list, bindings preview, and formulas in _modelo_payloads.py and migrate their emit sites.

- [x] `W04.P15.S116` - author ModeloListResult OutputSchema subclass with @register_schema decorator for modelo.list; `src/aeat/entrypoints/cli/_modelo_payloads.py`.
- [x] `W04.P15.S117` - migrate list_modelos bare emit site to _emit_envelope using typed ModeloListResult; `src/aeat/entrypoints/cli/_modelo.py`.
- [x] `W04.P15.S118` - author ModeloDescribeResult OutputSchema subclass with @register_schema decorator for modelo.describe; `src/aeat/entrypoints/cli/_modelo_payloads.py`.
- [x] `W04.P15.S119` - migrate describe_modelo bare emit site to _emit_envelope using typed ModeloDescribeResult; `src/aeat/entrypoints/cli/_modelo.py`.
- [x] `W04.P15.S120` - author ModeloCasillasResult OutputSchema subclass with @register_schema decorator for modelo.casillas; `src/aeat/entrypoints/cli/_modelo_payloads.py`.
- [x] `W04.P15.S121` - migrate casillas bare emit site to _emit_envelope using typed ModeloCasillasResult; `src/aeat/entrypoints/cli/_modelo.py`.
- [x] `W04.P15.S122` - author ModeloBindingsListResult OutputSchema subclass with @register_schema decorator for modelo.bindings.list; `src/aeat/entrypoints/cli/_modelo_payloads.py`.
- [x] `W04.P15.S123` - migrate bindings_list bare emit site to _emit_envelope using typed ModeloBindingsListResult; `src/aeat/entrypoints/cli/_modelo.py`.
- [x] `W04.P15.S124` - author ModeloBindingsPreviewResult OutputSchema subclass with @register_schema decorator for modelo.bindings.preview; `src/aeat/entrypoints/cli/_modelo_payloads.py`.
- [x] `W04.P15.S125` - migrate bindings_preview bare emit site to _emit_envelope using typed ModeloBindingsPreviewResult; `src/aeat/entrypoints/cli/_modelo.py`.
- [x] `W04.P15.S126` - author FormulasResult OutputSchema subclass with @register_schema decorator for modelo.formulas; `src/aeat/entrypoints/cli/_modelo_payloads.py`.
- [x] `W04.P15.S127` - migrate formulas bare emit site to _emit_envelope using typed FormulasResult; `src/aeat/entrypoints/cli/_modelo.py`.

### Phase `W04.P16` - modelo remaining singleton verb payload classes

Author OutputSchema subclasses for modelo export, modelo compare, modelo history, modelo project, modelo readiness, iva wallet balance, iva wallet seed, and work resume in _modelo_payloads.py and migrate their emit sites.

- [x] `W04.P16.S128` - author ModeloExportResult OutputSchema subclass with @register_schema decorator for modelo.export; `src/aeat/entrypoints/cli/_modelo_payloads.py`.
- [x] `W04.P16.S129` - migrate modelo_export_verb bare emit site to _emit_envelope using typed ModeloExportResult; `src/aeat/entrypoints/cli/_modelo.py`.
- [x] `W04.P16.S130` - author ModeloCompareResult OutputSchema subclass with @register_schema decorator for modelo.compare; `src/aeat/entrypoints/cli/_modelo_payloads.py`.
- [x] `W04.P16.S131` - migrate modelo_compare bare emit site to _emit_envelope using typed ModeloCompareResult; `src/aeat/entrypoints/cli/_modelo.py`.
- [x] `W04.P16.S132` - author ModeloHistoryResult OutputSchema subclass with @register_schema decorator for modelo.history; `src/aeat/entrypoints/cli/_modelo_payloads.py`.
- [x] `W04.P16.S133` - migrate modelo_history bare emit site to _emit_envelope using typed ModeloHistoryResult; `src/aeat/entrypoints/cli/_modelo.py`.
- [x] `W04.P16.S134` - author ModeloProjectResult OutputSchema subclass with @register_schema decorator for modelo.project; `src/aeat/entrypoints/cli/_modelo_payloads.py`.
- [x] `W04.P16.S135` - migrate modelo_project bare emit site to _emit_envelope using typed ModeloProjectResult; `src/aeat/entrypoints/cli/_modelo.py`.
- [x] `W04.P16.S136` - author ModeloReadinessResult OutputSchema subclass with @register_schema decorator for modelo.readiness; `src/aeat/entrypoints/cli/_modelo_payloads.py`.
- [x] `W04.P16.S137` - migrate modelo_readiness bare emit site to _emit_envelope using typed ModeloReadinessResult; `src/aeat/entrypoints/cli/_modelo.py`.
- [x] `W04.P16.S138` - author IvaWalletBalanceResult OutputSchema subclass with @register_schema decorator for modelo.iva_wallet.balance; `src/aeat/entrypoints/cli/_modelo_payloads.py`.
- [x] `W04.P16.S139` - migrate iva_wallet_balance_cmd bare emit site to _emit_envelope using typed IvaWalletBalanceResult; `src/aeat/entrypoints/cli/_modelo.py`.
- [x] `W04.P16.S140` - author IvaWalletSeedResult OutputSchema subclass with @register_schema decorator for modelo.iva_wallet.seed; `src/aeat/entrypoints/cli/_modelo_payloads.py`.
- [x] `W04.P16.S141` - migrate iva_wallet_seed_cmd bare emit site to _emit_envelope using typed IvaWalletSeedResult; `src/aeat/entrypoints/cli/_modelo.py`.
- [x] `W04.P16.S142` - author WorkResumeResult OutputSchema subclass with @register_schema decorator for modelo.work.resume; `src/aeat/entrypoints/cli/_modelo_payloads.py`.
- [x] `W04.P16.S143` - migrate work_resume bare emit site to _emit_envelope using typed WorkResumeResult; `src/aeat/entrypoints/cli/_modelo.py`.
- [x] `W04.P16.S144` - author ModeloAggregateResult OutputSchema subclass with @register_schema decorator for modelo.aggregate; `src/aeat/entrypoints/cli/_modelo_payloads.py`.
- [x] `W04.P16.S145` - migrate aggregate_modelo bare emit site to _emit_envelope using typed ModeloAggregateResult; `src/aeat/entrypoints/cli/_modelo.py`.

### Phase `W04.P17` - MIGRATED_COMMANDS extension and surface-test re-baseline for modelo

Append all newly migrated modelo command paths to MIGRATED_COMMANDS and re-baseline affected modelo CLI surface tests.

- [x] `W04.P17.S146` - append all newly migrated modelo command paths to MIGRATED_COMMANDS; `src/aeat/entrypoints/cli/test_json_schema_conformance.py`.
- [x] `W04.P17.S147` - re-baseline modelo CLI surface tests that previously asserted bare-payload JSON shape; `src/aeat/entrypoints/cli/test_modelo.py`.

## Wave `W05` - small-module burndown - 29 bare emit sites across 7 modules

Migrate remaining bare emit sites: _overview.py (7), _registry_corpus.py (7), _config/_google.py (4), _config/_profile_census.py (4), __init__.py (4), registry.py (2), _review.py (1). Each module is its own Phase with a dedicated _payloads.py file. Depends on all preceding Waves.

### Phase `W05.P18` - _overview.py payload classes - 7 emit sites

Author OutputSchema subclasses for the 7 overview command emit sites in _overview_payloads.py, register each, and migrate the emit sites.

- [x] `W05.P18.S148` - author OverviewStatusResult OutputSchema subclass with @register_schema decorator for overview.status; `src/aeat/entrypoints/cli/_overview_payloads.py`.
- [x] `W05.P18.S149` - migrate all overview_status bare emit sites to _emit_envelope using typed OverviewStatusResult; `src/aeat/entrypoints/cli/_overview.py`.
- [x] `W05.P18.S150` - append overview command paths to MIGRATED_COMMANDS and import _overview_payloads as side-effect; `src/aeat/entrypoints/cli/test_json_schema_conformance.py`.
- [x] `W05.P18.S151` - re-baseline overview CLI surface tests that previously asserted bare-payload JSON shape; `src/aeat/entrypoints/cli/test_overview.py`.

### Phase `W05.P19` - _registry_corpus.py payload classes - 7 emit sites

Author OutputSchema subclasses for the 7 registry-corpus command emit sites in _registry_corpus_payloads.py, register each, and migrate the emit sites.

- [x] `W05.P19.S152` - author CitationListResult OutputSchema subclass with @register_schema decorator for registry_corpus.citations.list; `src/aeat/entrypoints/cli/_registry_corpus_payloads.py`.
- [x] `W05.P19.S153` - migrate list_citations_cmd bare emit site to _emit_envelope using typed CitationListResult; `src/aeat/entrypoints/cli/_registry_corpus.py`.
- [x] `W05.P19.S154` - author CitationShowResult OutputSchema subclass with @register_schema decorator for registry_corpus.citations.show; `src/aeat/entrypoints/cli/_registry_corpus_payloads.py`.
- [x] `W05.P19.S155` - migrate show_citation_cmd bare emit site to _emit_envelope using typed CitationShowResult; `src/aeat/entrypoints/cli/_registry_corpus.py`.
- [x] `W05.P19.S156` - author CitationVerifyResult OutputSchema subclass with @register_schema decorator for registry_corpus.citations.verify; `src/aeat/entrypoints/cli/_registry_corpus_payloads.py`.
- [x] `W05.P19.S157` - migrate verify_citations_cmd bare emit site to _emit_envelope using typed CitationVerifyResult; `src/aeat/entrypoints/cli/_registry_corpus.py`.
- [x] `W05.P19.S158` - author ManualListResult OutputSchema subclass with @register_schema decorator for registry_corpus.manuals.list; `src/aeat/entrypoints/cli/_registry_corpus_payloads.py`.
- [x] `W05.P19.S159` - migrate list_manuals_cmd bare emit site to _emit_envelope using typed ManualListResult; `src/aeat/entrypoints/cli/_registry_corpus.py`.
- [x] `W05.P19.S160` - author ManualShowResult OutputSchema subclass with @register_schema decorator for registry_corpus.manuals.show; `src/aeat/entrypoints/cli/_registry_corpus_payloads.py`.
- [x] `W05.P19.S161` - migrate show_manual_cmd bare emit site to _emit_envelope using typed ManualShowResult; `src/aeat/entrypoints/cli/_registry_corpus.py`.
- [x] `W05.P19.S162` - author ManualRulesListResult OutputSchema subclass with @register_schema decorator for registry_corpus.manuals.rules.list; `src/aeat/entrypoints/cli/_registry_corpus_payloads.py`.
- [x] `W05.P19.S163` - migrate list_manual_rules_cmd bare emit site to _emit_envelope using typed ManualRulesListResult; `src/aeat/entrypoints/cli/_registry_corpus.py`.
- [x] `W05.P19.S164` - author ManualVerifyResult OutputSchema subclass with @register_schema decorator for registry_corpus.manuals.verify; `src/aeat/entrypoints/cli/_registry_corpus_payloads.py`.
- [x] `W05.P19.S165` - migrate verify_manual_cmd bare emit site to _emit_envelope using typed ManualVerifyResult; `src/aeat/entrypoints/cli/_registry_corpus.py`.
- [x] `W05.P19.S166` - append registry-corpus command paths to MIGRATED_COMMANDS and import _registry_corpus_payloads as side-effect; `src/aeat/entrypoints/cli/test_json_schema_conformance.py`.
- [x] `W05.P19.S167` - re-baseline registry-corpus CLI surface tests that previously asserted bare-payload JSON shape; `src/aeat/entrypoints/cli/test_registry_corpus.py`.

### Phase `W05.P20` - _config/_google.py payload classes - 4 emit sites

Author OutputSchema subclasses for the 4 google-config command emit sites in _config/_google_payloads.py, register each, and migrate the emit sites.

- [x] `W05.P20.S168` - author GoogleRegisterResult OutputSchema subclass with @register_schema decorator for config.google.register; `src/aeat/entrypoints/cli/_config/_google_payloads.py`.
- [x] `W05.P20.S169` - migrate google_register bare emit site to _emit_envelope using typed GoogleRegisterResult; `src/aeat/entrypoints/cli/_config/_google.py`.
- [x] `W05.P20.S170` - author GoogleLoginResult OutputSchema subclass with @register_schema decorator for config.google.login; `src/aeat/entrypoints/cli/_config/_google_payloads.py`.
- [x] `W05.P20.S171` - migrate google_login bare emit site to _emit_envelope using typed GoogleLoginResult; `src/aeat/entrypoints/cli/_config/_google.py`.
- [x] `W05.P20.S172` - author GoogleStatusResult OutputSchema subclass with @register_schema decorator for config.google.status; `src/aeat/entrypoints/cli/_config/_google_payloads.py`.
- [x] `W05.P20.S173` - migrate google_status bare emit site to _emit_envelope using typed GoogleStatusResult; `src/aeat/entrypoints/cli/_config/_google.py`.
- [x] `W05.P20.S174` - author GoogleLogoutResult OutputSchema subclass with @register_schema decorator for config.google.logout; `src/aeat/entrypoints/cli/_config/_google_payloads.py`.
- [x] `W05.P20.S175` - migrate google_logout bare emit site to _emit_envelope using typed GoogleLogoutResult; `src/aeat/entrypoints/cli/_config/_google.py`.
- [x] `W05.P20.S176` - append google-config command paths to MIGRATED_COMMANDS and import _config._google_payloads as side-effect; `src/aeat/entrypoints/cli/test_json_schema_conformance.py`.
- [x] `W05.P20.S177` - re-baseline google CLI surface tests that previously asserted bare-payload JSON shape; `src/aeat/entrypoints/cli/_config/test_google_sync_push.py`.

### Phase `W05.P21` - _config/_profile_census.py payload classes - 4 emit sites

Author OutputSchema subclasses for the 4 census command emit sites in _config/_profile_census_payloads.py, register each, and migrate the emit sites.

- [x] `W05.P21.S178` - author CensusRefreshResult OutputSchema subclass with @register_schema decorator for config.census.refresh; `src/aeat/entrypoints/cli/_config/_profile_census_payloads.py`.
- [x] `W05.P21.S179` - migrate census_refresh bare emit site to _emit_envelope using typed CensusRefreshResult; `src/aeat/entrypoints/cli/_config/_profile_census.py`.
- [x] `W05.P21.S180` - author CensusShowResult OutputSchema subclass with @register_schema decorator for config.census.show; `src/aeat/entrypoints/cli/_config/_profile_census_payloads.py`.
- [x] `W05.P21.S181` - migrate census_show bare emit site to _emit_envelope using typed CensusShowResult; `src/aeat/entrypoints/cli/_config/_profile_census.py`.
- [x] `W05.P21.S182` - author CensusCompareResult OutputSchema subclass with @register_schema decorator for config.census.compare; `src/aeat/entrypoints/cli/_config/_profile_census_payloads.py`.
- [x] `W05.P21.S183` - migrate census_compare bare emit site to _emit_envelope using typed CensusCompareResult; `src/aeat/entrypoints/cli/_config/_profile_census.py`.
- [x] `W05.P21.S184` - author CensusApplyResult OutputSchema subclass with @register_schema decorator for config.census.apply; `src/aeat/entrypoints/cli/_config/_profile_census_payloads.py`.
- [x] `W05.P21.S185` - migrate census_apply bare emit site to _emit_envelope using typed CensusApplyResult; `src/aeat/entrypoints/cli/_config/_profile_census.py`.
- [x] `W05.P21.S186` - append census command paths to MIGRATED_COMMANDS and import _config._profile_census_payloads as side-effect; `src/aeat/entrypoints/cli/test_json_schema_conformance.py`.

### Phase `W05.P22` - __init__.py payload classes - 4 emit sites

Author OutputSchema subclasses for the 4 root-CLI emit sites in _root_payloads.py, register each, and migrate the emit sites in _root_landing.py and __init__.py.

- [x] `W05.P22.S187` - author RootStatusResult OutputSchema subclass with @register_schema decorator for root.status; `src/aeat/entrypoints/cli/_root_payloads.py`.
- [x] `W05.P22.S188` - author AppRootResult OutputSchema subclass with @register_schema decorator for root.app; `src/aeat/entrypoints/cli/_root_payloads.py`.
- [x] `W05.P22.S189` - migrate _root and _app_root bare emit sites to _emit_envelope using typed root payload classes; `src/aeat/entrypoints/cli/__init__.py`.
- [x] `W05.P22.S190` - append root command paths to MIGRATED_COMMANDS and import _root_payloads as side-effect; `src/aeat/entrypoints/cli/test_json_schema_conformance.py`.
- [x] `W05.P22.S191` - re-baseline root CLI surface tests that previously asserted bare-payload JSON shape; `src/aeat/entrypoints/cli/test_root_help_shape.py`.

### Phase `W05.P23` - registry.py payload classes - 2 emit sites

Author OutputSchema subclasses for the 2 registry command emit sites in _registry_payloads.py, register each, and migrate the emit sites.

- [x] `W05.P23.S192` - author RegistryInspectResult OutputSchema subclass with @register_schema decorator for registry.inspect; `src/aeat/entrypoints/cli/_registry_payloads.py`.
- [x] `W05.P23.S193` - migrate inspect_registry_cmd bare emit site to _emit_envelope using typed RegistryInspectResult; `src/aeat/entrypoints/cli/registry.py`.
- [x] `W05.P23.S194` - author RegistryVerifyResult OutputSchema subclass with @register_schema decorator for registry.verify; `src/aeat/entrypoints/cli/_registry_payloads.py`.
- [x] `W05.P23.S195` - migrate verify_registry_cmd bare emit site to _emit_envelope using typed RegistryVerifyResult; `src/aeat/entrypoints/cli/registry.py`.
- [x] `W05.P23.S196` - append registry command paths to MIGRATED_COMMANDS and import _registry_payloads as side-effect; `src/aeat/entrypoints/cli/test_json_schema_conformance.py`.
- [x] `W05.P23.S197` - re-baseline registry CLI surface tests that previously asserted bare-payload JSON shape; `src/aeat/entrypoints/cli/test_registry_cli.py`.

### Phase `W05.P24` - _review.py payload class - 1 emit site

Extend _review_payloads.py with the OutputSchema subclass for the review view command emit site and migrate the emit site (review queue is already migrated).

- [x] `W05.P24.S198` - extend _review_payloads.py with ReviewViewResult OutputSchema subclass with @register_schema decorator for review.view; `src/aeat/entrypoints/cli/_review_payloads.py`.
- [x] `W05.P24.S199` - migrate review_show bare emit site to _emit_envelope using typed ReviewViewResult; `src/aeat/entrypoints/cli/_review.py`.
- [x] `W05.P24.S200` - append review.view to MIGRATED_COMMANDS; `src/aeat/entrypoints/cli/test_json_schema_conformance.py`.

### Phase `W05.P25` - MIGRATED_COMMANDS extension and surface-test re-baseline for small modules

Append all small-module command paths to MIGRATED_COMMANDS and re-baseline any affected CLI surface tests for overview, registry corpus, google, census, root, registry, and review commands.

- [x] `W05.P25.S201` - verify SCHEMA_REGISTRY contains entries for all small-module commands by running the conformance gate parametrised over every newly registered path; `src/aeat/entrypoints/cli/test_json_schema_conformance.py`.
- [x] `W05.P25.S202` - re-baseline any remaining CLI surface tests across overview, registry-corpus, google, census, root, registry, and review that asserted bare-payload shape; `src/aeat/entrypoints/cli/test_cli_surface.py`.

## Wave `W06` - enforcement gate - exhaustive MIGRATED_COMMANDS and zero bare emit sites

Tighten the conformance gate: expand MIGRATED_COMMANDS to enumerate every registered schema path, remove the partial-migration allow-list guard, and assert zero bare _emit(ctx call sites remain in CLI entrypoint modules. The _emit helpers in application/wizard/_runner.py and core/observability test_sink files are not CLI transport and are explicitly excluded. Must land after all preceding Waves are fully closed.

### Phase `W06.P26` - exhaustive MIGRATED_COMMANDS and gate tightening

Assert MIGRATED_COMMANDS equals the full set of registered schema paths; remove the partial-migration guard comment; verify the tightened gate passes for all migrated commands.

- [x] `W06.P26.S203` - assert MIGRATED_COMMANDS equals the full key set of SCHEMA_REGISTRY with a clear failure message listing any gap; `src/aeat/entrypoints/cli/test_json_schema_conformance.py`.
- [x] `W06.P26.S204` - remove the partial-migration allow-list guard comment from test_json_schema_conformance and tighten the parametrised gate to iterate SCHEMA_REGISTRY keys directly; `src/aeat/entrypoints/cli/test_json_schema_conformance.py`.
- [x] `W06.P26.S205` - run the full json-conformance gate and confirm every registered schema path passes the envelope round-trip; `src/aeat/entrypoints/cli/test_json_schema_conformance.py`.

### Phase `W06.P27` - zero-bare-emit structural assertion

Add a structural pytest that walks CLI entrypoint modules under src/aeat/entrypoints/cli/ and asserts zero remaining bare _emit(ctx call sites, with an explicit exclusion list for non-transport _emit helpers in wizard and observability modules.

- [x] `W06.P27.S206` - author test_zero_bare_emit_sites that walks CLI entrypoint modules under src/aeat/entrypoints/cli/ and asserts zero bare _emit(ctx call sites remain; `src/aeat/entrypoints/cli/test_json_schema_conformance.py`.
- [x] `W06.P27.S207` - document the explicit exclusion list for non-transport _emit functions in application/wizard/_runner.py and core/observability test_sink files in the structural assertion docstring; `src/aeat/entrypoints/cli/test_json_schema_conformance.py`.
- [x] `W06.P27.S208` - run the full CLI test suite and confirm all gates are green; `src/aeat/entrypoints/cli/test_json_schema_conformance.py`.
