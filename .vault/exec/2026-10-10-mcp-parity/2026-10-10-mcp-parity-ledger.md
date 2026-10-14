---
tags:
  - '#exec'
  - '#mcp-parity'
date: '2026-10-10'
modified: '2026-10-14'
body_schema: 'body-v2'
body_hash: 'sha256:12fcef356ff41a35ccac6c508edb8467b8e71fd0e229456a8f6b73bedc9d0d3a'
related:
  - "[[2026-10-10-mcp-parity-plan]]"
---
# `mcp-parity` ledger

## Changes

- `S10` `summary:` `Plan status=checked; original change rows: M 33; distinct path cells: 33. Detailed paths remain in archive.`
  Affected path families (unique path counts): src/cadrumo_harness/_data=33
  Representative paths: src/cadrumo_harness/_data/agent/README.md
- `S10` `verify:` `Archived historical verification rows: pass=2; latest recorded outcome=pass; summary only, not a fresh run.` -> `pass`
- `S10` `by:` `vaultspec-standard-executor`
- `S04` `summary:` `Plan status=checked; original change rows: M 9; distinct path cells: 9. Detailed paths remain in archive.`
  Affected path families (unique path counts): src/cadrumo/application=6, docs/technical=1,
  src/cadrumo/adapters=1, src/cadrumo/entrypoints=1
  Representative paths: src/cadrumo/application/user_profile/automation_operations.py;
  docs/technical/articles/027-local-reader-provisioning-workstation-health-and-application-contracts.md
- `S04` `verify:` `Archived historical verification rows: pass=5; latest recorded outcome=pass; summary only, not a fresh run.` -> `pass`
- `S04` `by:` `vaultspec-standard-executor`
- `S08` `summary:` `Plan status=checked; original change rows: M 6, A 3; distinct path cells: 9. Detailed paths remain in archive.`
  Affected path families (unique path counts): src/cadrumo_harness/mcp=8,
  src/cadrumo_harness/_data=1
  Representative paths: src/cadrumo_harness/mcp/admitted_operations.py;
  src/cadrumo_harness/_data/agent/rules/cadrumo-operator-operating-rules.md
- `S08` `verify:` `Archived historical verification rows: pass=5; latest recorded outcome=pass; summary only, not a fresh run.` -> `pass`
- `S08` `by:` `vaultspec-standard-executor`
- `S01` `summary:` `Plan status=checked; original change rows: A 5, M 5; distinct path cells: 8. Detailed paths remain in archive.`
  Affected path families (unique path counts): src/cadrumo/application=4, src/cadrumo/entrypoints=3,
  .vault/audit=1
  Representative paths: src/cadrumo/application/operations/mcp_admission.py;
  src/cadrumo/entrypoints/tests/test_operation_mcp_admission.py
- `S01` `verify:` `Archived historical verification rows: fail=1, pass=15; latest recorded outcome=pass; summary only, not a fresh run.` -> `pass`
- `S01` `by:` `vaultspec-high-executor`
- `S07` `summary:` `Plan status=checked; original change rows: A 2, M 10; distinct path cells: 12. Detailed paths remain in archive.`
  Affected path families (unique path counts): src/cadrumo/application=8, src/cadrumo/core=2,
  .vault/reference=1, src/cadrumo/entrypoints=1
  Representative paths: src/cadrumo/application/modelo/reconciliation_import_operation.py;
  src/cadrumo/core/path_confinement.py
- `S07` `verify:` `Archived historical verification rows: pass=6; latest recorded outcome=pass; summary only, not a fresh run.` -> `pass`
- `S07` `by:` `vaultspec-high-executor`
- `S15` `summary:` `Plan status=checked; original change rows: M 2, A 1; distinct path cells: 3. Detailed paths remain in archive.`
  Affected path families (unique path counts): src/cadrumo/adapters=2, .vault/reference=1
  Representative paths:
  src/cadrumo/adapters/persistence/storage/master_key/profile_worker_custody.py;
  .vault/reference/2026-10-10-mcp-parity-sign-in-doors-reference.md
- `S15` `verify:` `Archived historical verification rows: pass=6; latest recorded outcome=pass; summary only, not a fresh run.` -> `pass`
- `S15` `by:` `vaultspec-high-executor`
- `S05` `summary:` `Plan status=checked; original change rows: M 4, A 2; distinct path cells: 6. Detailed paths remain in archive.`
  Affected path families (unique path counts): src/cadrumo/application=5, src/cadrumo/entrypoints=1
  Representative paths: src/cadrumo/application/user_profile/operation_access_policy.py;
  src/cadrumo/entrypoints/runtime/tests/test_submission_commit_admission.py
- `S05` `verify:` `Archived historical verification rows: fail=1, pass=7; latest recorded outcome=pass; summary only, not a fresh run.` -> `pass`
- `S05` `by:` `vaultspec-high-executor`
- `S09` `summary:` `Plan status=checked; original change rows: A 7, M 5; distinct path cells: 12. Detailed paths remain in archive.`
  Affected path families (unique path counts): src/cadrumo/entrypoints=10, src/cadrumo/application=2
  Representative paths: src/cadrumo/entrypoints/cli/command_operation_table.py;
  src/cadrumo/application/operator_surface/command_operations.py
- `S09` `verify:` `Archived historical verification rows: pass=6; latest recorded outcome=pass; summary only, not a fresh run.` -> `pass`
- `S09` `by:` `vaultspec-high-executor`
- `S27` `summary:` `Plan status=checked; original change rows: M 5; distinct path cells: 5. Detailed paths remain in archive.`
  Affected path families (unique path counts): src/cadrumo/application=5
  Representative paths: src/cadrumo/application/ledger/ratios_operation.py
- `S27` `verify:` `Archived historical verification rows: pass=6; latest recorded outcome=pass; summary only, not a fresh run.` -> `pass`
- `S27` `by:` `vaultspec-standard-executor`
- `S06` `summary:` `Plan status=checked; original change rows: A 7, M 27; distinct path cells: 34. Detailed paths remain in archive.`
  Affected path families (unique path counts): src/cadrumo/adapters=7, src/cadrumo/application=7,
  src/cadrumo/entrypoints=6, src/cadrumo_harness/mcp=6, docs/locales/*=3, dev/quality=2,
  dev/smoke=1, docs/how-to=1, docs/technical=1
  Representative paths: src/cadrumo/adapters/local_runtime/tests/test_login_surface_frame.py;
  src/cadrumo/application/operations/mcp_surfaces.py
- `S06` `verify:` `Archived historical verification rows: pass=10, fail=1; latest recorded outcome=fail; summary only, not a fresh run.` -> `fail`
- `S06` `by:` `vaultspec-high-executor`
- `S29` `summary:` `Plan status=checked; original change rows: M 3, A 1; distinct path cells: 4. Detailed paths remain in archive.`
  Affected path families (unique path counts): src/cadrumo/application=3, src/cadrumo/entrypoints=1
  Representative paths: src/cadrumo/application/ledger/evidence_followup_registration.py;
  src/cadrumo/entrypoints/tests/test_ledger_evidence_mcp_frontends.py
- `S29` `verify:` `Archived historical verification rows: pass=7; latest recorded outcome=pass; summary only, not a fresh run.` -> `pass`
- `S29` `by:` `vaultspec-standard-executor`
- `S28` `summary:` `Plan status=checked; original change rows: A 4, M 32; distinct path cells: 36. Detailed paths remain in archive.`
  Affected path families (unique path counts): src/cadrumo/application=35, src/cadrumo/entrypoints=1
  Representative paths: src/cadrumo/application/modelo/tests/test_calculation_detail_projection.py;
  src/cadrumo/entrypoints/tests/test_operation_mcp_admission.py
- `S28` `verify:` `Archived historical verification rows: pass=7; latest recorded outcome=pass; summary only, not a fresh run.` -> `pass`
- `S28` `by:` `vaultspec-standard-executor`
- `S02` `summary:` `Plan status=checked; original change rows: M 11; distinct path cells: 11. Detailed paths remain in archive.`
  Affected path families (unique path counts): src/cadrumo/application=10, src/cadrumo/entrypoints=1
  Representative paths: src/cadrumo/application/invoices/catalogue_remove_operation.py;
  src/cadrumo/entrypoints/tests/test_operation_mcp_admission.py
- `S02` `verify:` `Archived historical verification rows: pass=8; latest recorded outcome=pass; summary only, not a fresh run.` -> `pass`
- `S02` `by:` `vaultspec-high-executor`
- `S03` `summary:` `Plan status=checked; original change rows: M 6; distinct path cells: 6. Detailed paths remain in archive.`
  Affected path families (unique path counts): src/cadrumo/application=4, src/cadrumo/entrypoints=2
  Representative paths: src/cadrumo/application/user_profile/profile_operation_access.py;
  src/cadrumo/entrypoints/tests/test_censal_access_policy.py
- `S03` `verify:` `Archived historical verification rows: pass=8; latest recorded outcome=pass; summary only, not a fresh run.` -> `pass`
- `S03` `by:` `vaultspec-high-executor`
- `S12` `summary:` `Plan status=checked; original change rows: M 2, A 2; distinct path cells: 4. Detailed paths remain in archive.`
  Affected path families (unique path counts): src/cadrumo/entrypoints=4
  Representative paths: src/cadrumo/entrypoints/runtime/profile_connection_admission.py
- `S12` `verify:` `Archived historical verification rows: pass=5; latest recorded outcome=pass; summary only, not a fresh run.` -> `pass`
- `S12` `by:` `vaultspec-high-executor`
- `S13` `summary:` `Plan status=checked; original change rows: M 24, A 2; distinct path cells: 26. Detailed paths remain in archive.`
  Affected path families (unique path counts): src/cadrumo_harness/mcp=14, docs/technical=2,
  src/cadrumo/application=2, src/cadrumo_harness/_data=2, dev/agent_eval=1, dev/packaging=1,
  docs/how-to=1, docs/workstation-setup.md=1, src/cadrumo/entrypoints=1,
  src/cadrumo_harness/_workspace.py=1
  Representative paths: src/cadrumo_harness/mcp/runtime_adapter.py;
  docs/technical/articles/187-filing-skills-and-the-mcp-operator-harness.md
- `S13` `verify:` `Archived historical verification rows: pass=7; latest recorded outcome=pass; summary only, not a fresh run.` -> `pass`
- `S13` `by:` `vaultspec-high-executor`
- `S14` `summary:` `Plan status=checked; original change rows: M 1, A 2; distinct path cells: 3. Detailed paths remain in archive.`
  Affected path families (unique path counts): src/cadrumo_harness/mcp=2, src/cadrumo/entrypoints=1
  Representative paths: src/cadrumo_harness/mcp/runtime_adapter.py;
  src/cadrumo/entrypoints/runtime/tests/test_mcp_sign_in_adapter.py
- `S14` `verify:` `Archived historical verification rows: pass=2; latest recorded outcome=pass; summary only, not a fresh run.` -> `pass`
- `S14` `by:` `vaultspec-high-executor`
- `S17` `summary:` `Plan status=checked; original change rows: M 1, A 1; distinct path cells: 2. Detailed paths remain in archive.`
  Affected path families (unique path counts): src/cadrumo/entrypoints=2
  Representative paths: src/cadrumo/entrypoints/runtime/profile_connection_sessions.py
- `S17` `verify:` `Archived historical verification rows: pass=3; latest recorded outcome=pass; summary only, not a fresh run.` -> `pass`
- `S17` `by:` `vaultspec-high-executor`
- `S16` `summary:` `Plan status=checked; original change rows: M 6; distinct path cells: 6. Detailed paths remain in archive.`
  Affected path families (unique path counts): src/cadrumo/adapters=3, src/cadrumo/application=2,
  src/cadrumo/entrypoints=1
  Representative paths: src/cadrumo/adapters/persistence/storage/custody/acceleration_receipt.py;
  src/cadrumo/application/user_profile/login_session.py
- `S16` `verify:` `Archived historical verification rows: pass=5; latest recorded outcome=pass; summary only, not a fresh run.` -> `pass`
- `S16` `by:` `vaultspec-standard-executor`
- `S11` `summary:` `Plan status=checked; original change rows: M 2; distinct path cells: 2. Detailed paths remain in archive.`
  Affected path families (unique path counts): src/cadrumo/application=1,
  src/cadrumo_harness/_data=1
  Representative paths: src/cadrumo/application/operations/mcp_admission.py;
  src/cadrumo_harness/_data/agent/rules/cadrumo-operator-lifecycle-ordering.md
- `S11` `verify:` `Archived historical verification rows: pass=2; latest recorded outcome=pass; summary only, not a fresh run.` -> `pass`
- `S46` `summary:` `Plan status=checked; original change rows: M 18, A 6; distinct path cells: 24. Detailed paths remain in archive.`
  Affected path families (unique path counts): src/cadrumo/application=17, src/cadrumo/entrypoints=7
  Representative paths: src/cadrumo/application/ledger/evidence_read_operation.py;
  src/cadrumo/entrypoints/operation_composition.py
- `S46` `verify:` `Archived historical verification rows: pass=9; latest recorded outcome=pass; summary only, not a fresh run.` -> `pass`
- `S46` `by:` `vaultspec-high-executor`
- `S37` `summary:` `Plan status=checked; original change rows: A 6, M 40; distinct path cells: 44. Detailed paths remain in archive.`
  Affected path families (unique path counts): src/cadrumo/application=27,
  src/cadrumo/entrypoints=14, dev/quality=2, .vault/adr=1
  Representative paths: src/cadrumo/application/operations/execution_actor.py;
  src/cadrumo/entrypoints/tests/test_modelo_work_mcp_admission.py
- `S37` `verify:` `Archived historical verification rows: pass=33; latest recorded outcome=pass; summary only, not a fresh run.` -> `pass`
- `S37` `by:` `vaultspec-high-executor`
- `S38` `summary:` `Plan status=checked; original change rows: M 3; distinct path cells: 3. Detailed paths remain in archive.`
  Affected path families (unique path counts): src/cadrumo/application=3
  Representative paths: src/cadrumo/application/modelo/operation_definitions.py
- `S38` `verify:` `Archived historical verification rows: pass=2; latest recorded outcome=pass; summary only, not a fresh run.` -> `pass`
- `S38` `by:` `vaultspec-high-executor`
- `S45` `summary:` `Plan status=checked; original change rows: M 160, A 4; distinct path cells: 164. Detailed paths remain in archive.`
  Affected path families (unique path counts): src/cadrumo/application=139, src/cadrumo/adapters=14,
  src/cadrumo_harness/mcp=5, src/cadrumo/entrypoints=3, dev/quality=2, src/cadrumo_harness/_data=1
  Representative paths: src/cadrumo/application/actividad_asset/registered_operations.py;
  src/cadrumo/adapters/local_runtime/tests/test_operation_process_scope.py
- `S45` `verify:` `Archived historical verification rows: pass=10; latest recorded outcome=pass; summary only, not a fresh run.` -> `pass`
- `S45` `by:` `vaultspec-high-executor`
- `S30` `summary:` `Plan status=checked; original change rows: M 24, A 4; distinct path cells: 25. Detailed paths remain in archive.`
  Affected path families (unique path counts): src/cadrumo/application=12,
  src/cadrumo/entrypoints=8, docs/locales/*=3, docs/how-to=1, src/cadrumo/domain=1
  Representative paths: src/cadrumo/application/ledger/classify_patch.py;
  src/cadrumo/entrypoints/cli/_ledger.py
- `S30` `verify:` `Archived historical verification rows: pass=19; latest recorded outcome=pass; summary only, not a fresh run.` -> `pass`
- `S30` `by:` `vaultspec-high-executor`
- `S32` `summary:` `Plan status=retired; original change rows: M 9, A 1; distinct path cells: 9. Detailed paths remain in archive.`
  Affected path families (unique path counts): src/cadrumo/application=6, src/cadrumo/entrypoints=3
  Representative paths: src/cadrumo/application/ledger/bulk_classify_operation.py;
  src/cadrumo/entrypoints/tests/test_ledger_classification_actor_by_frontend.py
- `S32` `verify:` `Archived historical verification rows: pass=19; latest recorded outcome=pass; summary only, not a fresh run.` -> `pass`
- `S32` `by:` `vaultspec-high-executor`
- `S33` `summary:` `Plan status=checked; original change rows: M 10; distinct path cells: 10. Detailed paths remain in archive.`
  Affected path families (unique path counts): src/cadrumo/application=7, src/cadrumo/entrypoints=2,
  src/cadrumo/adapters=1
  Representative paths: src/cadrumo/application/ledger/ratios_operation.py;
  src/cadrumo/entrypoints/operation_composition.py
- `S33` `verify:` `Archived historical verification rows: pass=9; latest recorded outcome=pass; summary only, not a fresh run.` -> `pass`
- `S33` `by:` `vaultspec-high-executor`
- `S34` `summary:` `Plan status=checked; original change rows: M 4, A 1; distinct path cells: 5. Detailed paths remain in archive.`
  Affected path families (unique path counts): src/cadrumo/entrypoints=3, src/cadrumo/application=2
  Representative paths: src/cadrumo/entrypoints/tests/test_ledger_row_mutation_mcp_admission.py;
  src/cadrumo/application/ledger/attachment_mutation_operation.py
- `S34` `verify:` `Archived historical verification rows: pass=9; latest recorded outcome=pass; summary only, not a fresh run.` -> `pass`
- `S34` `by:` `vaultspec-high-executor`
- `S35` `summary:` `Plan status=checked; original change rows: M 47, A 13; distinct path cells: 50. Detailed paths remain in archive.`
  Affected path families (unique path counts): src/cadrumo/application=22,
  src/cadrumo/entrypoints=12, src/cadrumo/adapters=6, src/cadrumo/domain=5, src/cadrumo/locales=4,
  .vault/audit=1
  Representative paths: src/cadrumo/application/ledger/split_operation.py;
  src/cadrumo/entrypoints/cli/tests/test_runtime_ledger_split.py
- `S35` `verify:` `Archived historical verification rows: pass=62; latest recorded outcome=pass; summary only, not a fresh run.` -> `pass`
- `S35` `by:` `vaultspec-standard-executor`
- `S42` `summary:` `Plan status=checked; original change rows: M 42, A 11; distinct path cells: 52. Detailed paths remain in archive.`
  Affected path families (unique path counts): src/cadrumo/application=34,
  src/cadrumo/entrypoints=12, dev/quality=2, src/cadrumo/adapters=2, src/cadrumo/core=2
  Representative paths: src/cadrumo/application/ledger/evidence_mutation_operation.py;
  src/cadrumo/entrypoints/cli/_ledger_evidence_cli.py
- `S42` `verify:` `Archived historical verification rows: pass=29; latest recorded outcome=pass; summary only, not a fresh run.` -> `pass`
- `S42` `by:` `vaultspec-high-executor`
- `S44` `summary:` `Plan status=checked; original change rows: M 11, A 1; distinct path cells: 12. Detailed paths remain in archive.`
  Affected path families (unique path counts): src/cadrumo/application=8, src/cadrumo/entrypoints=3,
  .vault/adr=1
  Representative paths: src/cadrumo/application/modelo/local_observation_operation.py;
  src/cadrumo/entrypoints/tests/test_modelo_local_records_mcp_admission.py
- `S44` `verify:` `Archived historical verification rows: pass=10; latest recorded outcome=pass; summary only, not a fresh run.` -> `pass`
- `S44` `by:` `vaultspec-high-executor`
- `S19` `summary:` `Plan status=checked; original change rows: M 2; distinct path cells: 2. Detailed paths remain in archive.`
  Affected path families (unique path counts): src/cadrumo/entrypoints=2
  Representative paths: src/cadrumo/entrypoints/runtime/tests/test_mcp_sign_in_adapter.py
- `S19` `verify:` `Archived historical verification rows: pass=4; latest recorded outcome=pass; summary only, not a fresh run.` -> `pass`
- `S19` `by:` `vaultspec-standard-executor`
- `S47` `summary:` `Plan status=checked; original change rows: D 16, M 90, A 20; distinct path cells: 126. Detailed paths remain in archive.`
  Affected path families (unique path counts): src/cadrumo/entrypoints=42, src/cadrumo/_data=37,
  src/cadrumo/application=29, src/cadrumo/adapters=16, .vault/plan=1, src/cadrumo/tests=1
  Representative paths: src/cadrumo/entrypoints/cli/_ledger_evidence_cli.py;
  src/cadrumo/_data/manual_corpus_text/aeat_official/disenos_registro/modelo_180/files/01-180-orden-hap-1732-2014-actualizado-por-orden-hfp-1284-2023-de-28-de-noviembre-251-kb-pdf.pdf.corpus_text.json
- `S47` `verify:` `Archived historical verification rows: pass=10; latest recorded outcome=pass; summary only, not a fresh run.` -> `pass`
- `S47` `by:` `vaultspec-high-executor`
- `S48` `summary:` `Plan status=checked; original change rows: M 89, D 7, A 5; distinct path cells: 101. Detailed paths remain in archive.`
  Affected path families (unique path counts): src/cadrumo/application=86,
  src/cadrumo/entrypoints=10, src/cadrumo/adapters=3, src/cadrumo/domain=2
  Representative paths: src/cadrumo/application/inventory/registered_operation.py;
  src/cadrumo/entrypoints/tests/ledger_persons_work_test_support.py
- `S48` `verify:` `Archived historical verification rows: pass=10; latest recorded outcome=pass; summary only, not a fresh run.` -> `pass`
- `S48` `by:` `vaultspec-high-executor`
- `S49` `summary:` `Plan status=checked; original change rows: M 110, D 2, A 1; distinct path cells: 113. Detailed paths remain in archive.`
  Affected path families (unique path counts): src/cadrumo/application=109,
  src/cadrumo/entrypoints=4
  Representative paths: src/cadrumo/application/diagnostics_operation.py;
  src/cadrumo/entrypoints/tests/test_modelo_local_records_mcp_admission.py
- `S49` `verify:` `Archived historical verification rows: pass=10; latest recorded outcome=pass; summary only, not a fresh run.` -> `pass`
- `S49` `by:` `vaultspec-high-executor`
- `S50` `summary:` `Plan status=checked; original change rows: M 79, D 1, A 7; distinct path cells: 87. Detailed paths remain in archive.`
  Affected path families (unique path counts): src/cadrumo/application=41,
  src/cadrumo/entrypoints=17, src/cadrumo_harness/mcp=15, src/cadrumo/adapters=8, dev/agent_eval=6
  Representative paths: src/cadrumo/application/auth/apoderado_operation.py;
  src/cadrumo/entrypoints/runtime/bootstrap_delete.py
- `S50` `verify:` `Archived historical verification rows: pass=10; latest recorded outcome=pass; summary only, not a fresh run.` -> `pass`
- `S50` `by:` `vaultspec-high-executor`
- `S51` `summary:` `Plan status=checked; original change rows: M 35; distinct path cells: 35. Detailed paths remain in archive.`
  Affected path families (unique path counts): src/cadrumo_harness/_data=30, docs/locales/*=3,
  docs/how-to=1, docs/technical=1
  Representative paths: src/cadrumo_harness/_data/agent/README.md;
  docs/locales/ca/LC_MESSAGES/how-to/connect-an-agent.po
- `S51` `verify:` `Archived historical verification rows: pass=10; latest recorded outcome=pass; summary only, not a fresh run.` -> `pass`
- `S51` `by:` `vaultspec-high-executor`
- `S52` `summary:` `Plan status=checked; original change rows: A 12, M 6; distinct path cells: 18. Detailed paths remain in archive.`
  Affected path families (unique path counts): src/cadrumo/entrypoints=10,
  src/cadrumo/application=5, src/cadrumo/adapters=3
  Representative paths: src/cadrumo/entrypoints/runtime/installation_door.py;
  src/cadrumo/application/runtime/installation_requests.py
- `S52` `verify:` `Archived historical verification rows: pass=3; latest recorded outcome=pass; summary only, not a fresh run.` -> `pass`
- `S52` `by:` `vaultspec-high-executor`
- `S57` `summary:` `Plan status=checked; original change rows: A 5, D 3, M 20; distinct path cells: 28. Detailed paths remain in archive.`
  Affected path families (unique path counts): src/cadrumo/entrypoints=21,
  src/cadrumo/application=4, src/cadrumo_harness/mcp=3
  Representative paths: src/cadrumo/entrypoints/cli/config/tests/test_apoderado_scopes_payload.py;
  src/cadrumo/application/reference_catalogue.py
- `S57` `verify:` `Archived historical verification rows: pass=3; latest recorded outcome=pass; summary only, not a fresh run.` -> `pass`
- `S57` `by:` `vaultspec-high-executor`
- `S53` `summary:` `Plan status=checked; original change rows: M 12, A 13; distinct path cells: 25. Detailed paths remain in archive.`
  Affected path families (unique path counts): src/cadrumo/adapters=11, src/cadrumo/application=9,
  src/cadrumo/entrypoints=5
  Representative paths: src/cadrumo/adapters/local_runtime/worker_authorization.py;
  src/cadrumo/application/local_reader_contracts.py
- `S53` `verify:` `Archived historical verification rows: pass=5; latest recorded outcome=pass; summary only, not a fresh run.` -> `pass`
- `S53` `by:` `vaultspec-high-executor`
- `S54` `summary:` `Plan status=checked; original change rows: M 5, D 1, A 13; distinct path cells: 19. Detailed paths remain in archive.`
  Affected path families (unique path counts): src/cadrumo/entrypoints=12, src/cadrumo/application=7
  Representative paths: src/cadrumo/entrypoints/cli/common.py;
  src/cadrumo/application/connectivity_probe.py
- `S54` `verify:` `Archived historical verification rows: pass=1; latest recorded outcome=pass; summary only, not a fresh run.` -> `pass`
- `S54` `by:` `vaultspec-high-executor`
- `S55` `summary:` `Plan status=checked; original change rows: M 37, D 1, A 8; distinct path cells: 42. Detailed paths remain in archive.`
  Affected path families (unique path counts): src/cadrumo/entrypoints=25, src/cadrumo/adapters=8,
  src/cadrumo/application=8, src/cadrumo/core=1
  Representative paths: src/cadrumo/entrypoints/cli/config/_storage_command_specs.py;
  src/cadrumo/adapters/local_runtime/installation_client.py
- `S55` `verify:` `Archived historical verification rows: pass=7; latest recorded outcome=pass; summary only, not a fresh run.` -> `pass`
- `S55` `by:` `vaultspec-high-executor`
- `S56` `summary:` `Plan status=checked; original change rows: M 17, A 15; distinct path cells: 32. Detailed paths remain in archive.`
  Affected path families (unique path counts): src/cadrumo/entrypoints=20,
  src/cadrumo/application=12
  Representative paths: src/cadrumo/entrypoints/cli/_profile_authentication_contract.py;
  src/cadrumo/application/runtime/installation_requests.py
- `S56` `verify:` `Archived historical verification rows: pass=1; latest recorded outcome=pass; summary only, not a fresh run.` -> `pass`
- `S56` `by:` `vaultspec-high-executor`
- `S58` `summary:` `Plan status=checked; original change rows: M 12, A 6; distinct path cells: 18. Detailed paths remain in archive.`
  Affected path families (unique path counts): src/cadrumo/entrypoints=10, src/cadrumo/application=8
  Representative paths: src/cadrumo/entrypoints/cli/_modelo_review_package_cli.py;
  src/cadrumo/application/live/filed_data_capture.py
- `S58` `verify:` `Archived historical verification rows: pass=1; latest recorded outcome=pass; summary only, not a fresh run.` -> `pass`
- `S58` `by:` `vaultspec-high-executor`
- `S60` `summary:` `Plan status=checked; original change rows: M 30, A 40; distinct path cells: 66. Detailed paths remain in archive.`
  Affected path families (unique path counts): src/cadrumo/entrypoints=60, src/cadrumo/locales=4,
  dev/acceptance=1, dev/tui=1
  Representative paths: src/cadrumo/entrypoints/tui/app.py; src/cadrumo/locales/en/common.yml
- `S60` `verify:` `Archived historical verification rows: pass=10; latest recorded outcome=pass; summary only, not a fresh run.` -> `pass`
- `S60` `by:` `vaultspec-high-executor`
- `S59` `summary:` `Plan status=checked; original change rows: M 8, A 5; distinct path cells: 13. Detailed paths remain in archive.`
  Affected path families (unique path counts): src/cadrumo_harness/mcp=6, docs/locales/*=3,
  src/cadrumo/application=2, docs/how-to=1, src/cadrumo/entrypoints=1
  Representative paths: src/cadrumo_harness/mcp/runtime_cleanup.py;
  docs/locales/ca/LC_MESSAGES/how-to/connect-an-agent.po
- `S59` `verify:` `Archived historical verification rows: pass=6; latest recorded outcome=pass; summary only, not a fresh run.` -> `pass`
- `S59` `by:` `vaultspec-high-executor`
- `S62` `summary:` `Plan status=checked; original change rows: M 30, A 11; distinct path cells: 40. Detailed paths remain in archive.`
  Affected path families (unique path counts): src/cadrumo_harness/mcp=25,
  src/cadrumo_harness/_data=5, src/cadrumo/entrypoints=3, src/cadrumo_harness/tests=3,
  src/cadrumo/application=2, src/cadrumo_harness/_workspace.py=1, src/cadrumo_harness/resources.py=1
  Representative paths: src/cadrumo_harness/mcp/admitted_operations.py;
  src/cadrumo_harness/_data/agent/README.md
- `S62` `verify:` `Archived historical verification rows: pass=13; latest recorded outcome=pass; summary only, not a fresh run.` -> `pass`
- `S62` `by:` `vaultspec-high-executor`
- `S39` `summary:` `Plan status=checked; original change rows: A 3, M 4; distinct path cells: 6. Detailed paths remain in archive.`
  Affected path families (unique path counts): src/cadrumo/entrypoints=3,
  src/cadrumo_harness/_data=2, src/cadrumo_harness/_workspace.py=1
  Representative paths:
  src/cadrumo/entrypoints/tests/test_declaration_through_mcp_equals_command_line.py;
  src/cadrumo_harness/_data/agent/README.md
- `S39` `verify:` `Archived historical verification rows: pass=14; latest recorded outcome=pass; summary only, not a fresh run.` -> `pass`
- `S39` `by:` `vaultspec-high-executor`
- `S61` `summary:` `Plan status=checked; original change rows: M 32, A 11; distinct path cells: 41. Detailed paths remain in archive.`
  Affected path families (unique path counts): src/cadrumo/entrypoints=27,
  src/cadrumo/application=6, dev/quality=5, dev/harness_data=3
  Representative paths: src/cadrumo/entrypoints/cli/command_operation_table.py;
  src/cadrumo/application/diagnostics_repair_documents.py
- `S61` `verify:` `Archived historical verification rows: pass=14; latest recorded outcome=pass; summary only, not a fresh run.` -> `pass`
- `S61` `by:` `vaultspec-high-executor`
- `S63` `summary:` `Plan status=checked; original change rows: M 75, A 30, D 2; distinct path cells: 99. Detailed paths remain in archive.`
  Affected path families (unique path counts): src/cadrumo/entrypoints=21,
  src/cadrumo_harness/mcp=19, src/cadrumo_harness/_data=18, src/cadrumo/application=15,
  dev/agent_eval=6, dev/quality=3, docs/locales/*=3, src/cadrumo/adapters=3, src/cadrumo/core=3,
  src/cadrumo_harness/tests=3, docs/technical=2, src/cadrumo/domain=2, docs/how-to=1
  Representative paths: src/cadrumo/entrypoints/cli/registered_operation_errors.py;
  src/cadrumo_harness/mcp/admitted_operations.py
- `S63` `verify:` `Archived historical verification rows: pass=31; latest recorded outcome=pass; summary only, not a fresh run.` -> `pass`
- `S63` `by:` `vaultspec-high-executor`
- `S64` `summary:` `Plan status=checked; original change rows: M 44, D 12, A 2; distinct path cells: 57. Detailed paths remain in archive.`
  Affected path families (unique path counts): src/cadrumo_harness/mcp=28,
  src/cadrumo/entrypoints=12, dev/agent_eval=9, dev/quality=3, src/cadrumo/application=3,
  dev/packaging=1, src/cadrumo_harness/_data=1
  Representative paths: src/cadrumo_harness/mcp/admitted_operations.py;
  src/cadrumo/entrypoints/cli/tests/command_frontend_counterparts.py
- `S64` `verify:` `Archived historical verification rows: pass=6; latest recorded outcome=pass; summary only, not a fresh run.` -> `pass`
- `S65` `summary:` `Plan status=checked; original change rows: M 36, A 3; distinct path cells: 39. Detailed paths remain in archive.`
  Affected path families (unique path counts): src/cadrumo/entrypoints=27,
  src/cadrumo/application=5, docs/locales/*=3, src/cadrumo_harness/mcp=3, docs/how-to=1
  Representative paths: src/cadrumo/entrypoints/runtime/profile_connection_operations.py;
  src/cadrumo/application/user_profile/access_contracts.py
- `S65` `verify:` `Archived historical verification rows: pass=7; latest recorded outcome=pass; summary only, not a fresh run.` -> `pass`
- `S66` `summary:` `Plan status=checked; original change rows: M 6, A 1; distinct path cells: 7. Detailed paths remain in archive.`
  Affected path families (unique path counts): src/cadrumo/entrypoints=6, src/cadrumo/application=1
  Representative paths: src/cadrumo/entrypoints/runtime/profile_connection_sessions.py;
  src/cadrumo/application/user_profile/login_session.py
- `S66` `verify:` `Archived historical verification rows: fail=1, pass=3; latest recorded outcome=pass; summary only, not a fresh run.` -> `pass`
- `S67` `summary:` `Plan status=checked; original change rows: M 26, D 20, A 1; distinct path cells: 47. Detailed paths remain in archive.`
  Affected path families (unique path counts): src/cadrumo_harness/mcp=18,
  src/cadrumo_harness/_data=15, src/cadrumo/entrypoints=5, dev/quality=3,
  src/cadrumo_harness/tests=3, dev/agent_eval=2, dev/harness_data=1
  Representative paths: src/cadrumo_harness/mcp/admitted_operations.py;
  src/cadrumo_harness/_data/operation_contracts/app.jsonl
- `S67` `verify:` `Archived historical verification rows: pass=4; latest recorded outcome=pass; summary only, not a fresh run.` -> `pass`
- `S69` `summary:` `Plan status=checked; original change rows: M 28; distinct path cells: 28. Detailed paths remain in archive.`
  Affected path families (unique path counts): docs/locales/*=12, docs/technical=5,
  src/cadrumo_harness/_data=5, docs/how-to=3, docs/reference=1, src/cadrumo/entrypoints=1,
  src/cadrumo_harness/mcp=1
  Representative paths: docs/locales/ca/LC_MESSAGES/how-to/connect-an-agent.po;
  docs/technical/architecture.md
- `S69` `verify:` `Archived historical verification rows: pass=1, fail=1; latest recorded outcome=fail; summary only, not a fresh run.` -> `fail`
- `S70` `summary:` `Plan status=checked; original change rows: M 3, A 1; distinct path cells: 4. Detailed paths remain in archive.`
  Affected path families (unique path counts): src/cadrumo_harness/mcp=3, src/cadrumo/entrypoints=1
  Representative paths: src/cadrumo_harness/mcp/runtime_adapter.py;
  src/cadrumo/entrypoints/runtime/tests/test_mcp_one_signed_in_profile.py
- `S70` `verify:` `Archived historical verification rows: pass=2; latest recorded outcome=pass; summary only, not a fresh run.` -> `pass`
- `S18` `summary:` `Plan status=checked; original change rows: M 1; distinct path cells: 1. Detailed paths remain in archive.`
  Affected path families (unique path counts): .vault/adr=1
  Representative paths: .vault/adr/2026-10-04-application-sign-in-adr.md
- `S18` `verify:` `Archived historical verification rows: pass=1; latest recorded outcome=pass; summary only, not a fresh run.` -> `pass`
- `S71` `summary:` `Plan status=checked; original change rows: M 53, A 3, R 1; distinct path cells: 56. Detailed paths remain in archive.`
  Affected path families (unique path counts): src/cadrumo/entrypoints=23,
  src/cadrumo_harness/mcp=9, src/cadrumo/locales=8, src/cadrumo/application=6,
  src/cadrumo/adapters=5, src/cadrumo_harness/_data=3, dev/acceptance=1, dev/quality=1
  Representative paths: src/cadrumo/entrypoints/cli/_profile_authentication_gate.py;
  src/cadrumo_harness/mcp/admitted_operations.py
- `S71` `verify:` `Archived historical verification rows: pass=6, fail=5; latest recorded outcome=fail; summary only, not a fresh run.` -> `fail`
- `S72` `summary:` `Plan status=checked; original change rows: A 6, M 50; distinct path cells: 53. Detailed paths remain in archive.`
  Affected path families (unique path counts): src/cadrumo/entrypoints=25,
  src/cadrumo/application=8, src/cadrumo/locales=8, docs/locales/*=3, src/cadrumo_harness/_data=3,
  .vault/adr=2, src/cadrumo/adapters=2, docs/how-to=1, src/cadrumo_harness/mcp=1
  Representative paths:
  src/cadrumo/entrypoints/cli/config/tests/test_runtime_automation_agent_key.py;
  src/cadrumo/application/user_profile/automation_agent_key.py
- `S72` `verify:` `Archived historical verification rows: pass=9, fail=4; latest recorded outcome=fail; summary only, not a fresh run.` -> `fail`
- `S73` `summary:` `Plan status=checked; original change rows: M 4; distinct path cells: 4. Detailed paths remain in archive.`
  Affected path families (unique path counts): dev/agent_eval=4
  Representative paths: dev/agent_eval/live/access.py
- `S73` `verify:` `Archived historical verification rows: pass=2; latest recorded outcome=pass; summary only, not a fresh run.` -> `pass`

## Notes

- Summary semantics: `summary:` labels preserve Step coverage, while the parser reports zero native path-change rows. Original operation and domain counts appear above; exact path-per-row history and verification commands are in `<local-archive>/markdown-originals-2026-10-14.tar.gz` (manifest: `<temp>/cadrumo-markdown-condensation-2026-10-14/manifest.json`).


- `S08` The subject-reference form could not be stated from inside the harness and moved to its own Step. One existing result-page test was already failing at HEAD on a stale page-size literal and is corrected here.
- `S01` The import-boundary gate fails for reasons outside this Step: two private cross-package findings under dev/packaging and a stale generated module inventory; all 15 contracts are kept and no chain involves these files. The inventory entries for the new modules are regenerated in a separate commit. Twelve MCP-listed operations are not proven through their real resolver and are pinned in a named set; the no-submission assertion covers what operations, tools and commands declare and cannot see executor or adapter behaviour.
- `S07` Not delivered here and carried to the file-exchange Step: root confinement of the reconciliation import, for want of any existing setting, and a bytes entry for the declaracion parser, which is still parsed by path between two verified reads. The POSIX branch of the guard has not executed; tests ran on Windows only. The strict checkers were not run on these files with a working invocation.
- `S15` Still reachable and not introduced here: a key read after the latest lease expiry and before the custody poll closes the session; a retire that finds no session when two root leases are still listed at that moment; and a lease installed or refreshed while a section is held, which is not covered until the last section exits. The worker can refresh only key leases, so extending a sign-in will need a way to move a human lease deadline. Tests do not cover held sections or the real worker loop.
- `S05` The 18 failures in the wide run are not from this Step. Two (session owner, worker drain) pass when run alone. Ten are the machine: the test child interpreter sees a stale cadrumo 0.5.1 install in the base Python while the environment is 0.6.0, so the runtime refuses with a version mismatch before announcing ready (supervised runtime, headless load, console interrupt). Three operation-provenance cases fail in the test process on a storage route mismatch, and three grant-change cases fail because the runtime now retires the key session when its grant changes and the test predates that; neither path is touched by this feature, and no earlier run of those files exists to compare. Three operations (filed list, filed discover, census preview) are now refused at submission for a scope without commit where they used to complete when the provider session was reusable.
- `S09` The manifest assertion added to `test_command_surface_beside_retired_state.py` cannot run on this machine: that test setup creates a directory beside the checkout and a copy left on 2026-10-05 makes it fail before the assertion, as it does at HEAD. The claim is proven by a new test of the real emitter in `test_command_operation_join.py.` Eight tests in `test_cli_surface.py` fail with `runtime_unavailable` and are unrelated. Seventeen operations list the command line as a frontend although no command submits them. The generated import inventory entries for the two new product modules are added with the next regeneration.
- `S27` Checklist per operation, by reading: resolver present and frontend-agnostic; no command-line safeguard missing from the operation; no person-act field; no host path; results are typed data with no bytes, secrets or keys; executors read only and reach no network. The command line defaults the year and an MCP caller must supply it. The rule list result includes the stored creator string of each rule. A wide command-line run selected by keyword was still running at close and is not evidence for this Step.
- `S06` Two files carry another session uncommitted changes; only the surface lines are committed from them (three in `access_contracts.py,` two in `profile_host.py).` The one format finding and the one noqa in those files are in the other session lines. Not built here: status still reports the unnarrowed scope on a narrowed surface; there is no single end-to-end test with a real worker, the chain is covered in three pieces; the packaged plugin launch line never names a surface. Four listed read-only operations rest on the over-declared effects set. The how-to translations for the new paragraph follow separately.
- `S06` The five docs failures are in other pages and none concerns the agent connection guide: catalogue drift in how-to/profile-setup and reference/identity-and-naming, a composed Catalan root difference in filing-calendar and identity-and-naming, and a sequence golden for how-to/irpf-lifecycle whose command-line frames were refused while frontend sets were being edited by a running Step. The Hungarian wording for an agent that should only look is the translator own reading.
- `S29` Four of the eight reads are admitted: attachment queue, attachment view, consent list and review list. Not admitted, each for a reason found in its result or executor: evidence list and view return the host path the operator typed; review view returns text taken verbatim from the document; reader readiness sends requests to the configured local-model endpoint, which settings can point off this machine, and its decision row now records that it reaches the network. A further Step gives these agent-facing projections.
- `S28` Eighteen of twenty-three reads admitted. Not admitted: `modelo.filing_record.view` and profile.history return an open payload, and the three Google configuration reads have a human-only resolver; a further Step gives them agent-facing projections. The first pass withheld results carrying notes, reasons and actor labels the person typed; that reading of the checklist was stricter than the owner rule and was corrected in the plan. Five of the admitted operations cannot be admitted by the generic resolver probe and are in its not-proven set; each has its own test through the real resolver.
- `S02` Refused on MCP until the approval step exists: ledger.invoice.remove and auth.session.reset whole; the six writing actions of `ledger.own_account;` declare and remove of `modelo.m360_solicitud;` the three prorrata elections. The other five prorrata operations, auth.session.logout and the reads of the mixed definitions keep MCP. The off-machine read of ledger.evidence.extract is not covered by the invariant because that definition does not list MCP yet. Native command-line suites that need a running runtime could not run on this machine.
- `S03` The plan asked for the census review confirmation to move into the operation. That is not possible without changing the response contract for every review: apply, reject and inspect evaluate as one access action and carry no intent. The review leaves MCP whole until the approval step carries that intent; the census preview stays open. A capability can be written through user-profile.field-mutation and through user-profile.patch; both routes are refused on MCP. The other six profile writers have no route to a capability. Committed together with S02 because both share the invariant in one test file.
- `S13` Found while proving the door in a real server process: the login-session port was never composed there, so the resume failed with an invariant error reported as an unavailable runtime. The server now composes it, an invariant failure has its own refusal code, and a test starts the server as a fresh process. Three installed-command tests in the oracle file fail on this machine with `runtime_unavailable` from the stale base-Python install; they do not exercise this Step. The translations of the two user pages are re-synced for es, ca and hu.
- `S16` Traced first: a process of the same account in a different OS login could have the stored sign-in deleted by presenting any 32 bytes, because the login mismatch deleted before the proof was checked. The proof is now checked first for that one refusal; refusals that are facts about the stored record still delete at once. No session owning the sign-in work was reachable to settle it with, and the change removes no protection: the genuine proof under another login still deletes. One existing expectation changed with it: a record whose login binding was rewritten on disk now reads as tampered and is kept, as any other corrupt record is.
- `S46` Eight of the nine reads are open. Evidence list and view are served by ledger.evidence.query, which returns the stored file name in place of the typed host path; the review view by ledger.evidence.review.summary, which withholds every free-text draft field and says so per row; profile.history by profile.history.timeline. Reader readiness returns the endpoint as scheme, host and port only. The filing record view returns typed rows at result version 2. Google folder view and status no longer require commit rights or a human-only session. Also made consistent: ledger.history released the same open event payload on MCP and is now served by ledger.history.typed. Not admitted: config.google.probe, whose result detail is the provider failure text. Open for the owner: the review summary also withholds short identifiers read from the document (tax id, invoice number, date).
- `S37` Create, calculate and rename are open to MCP. The applicability gate was already in the create operation with a typed bypass, and the only recalculation confirmation is the terminal interface own prompt, kept there; recalculating deletes nothing, so the result now names the revision it replaced. Refused on MCP until the approval step exists: a calculation that states its own inputs, and one that states the joint-return election or the Modelo 390 attestation. modelo.work.amend is not admitted and is re-ruled behind approval: it verifies, records a local filing and retires the record it corrects in one act. The actor recorded for an MCP execution is derived from the admitting session and the typed one is ignored. Eleven failures in the wide run are outside this Step: six command-line tests report `runtime_unavailable` from the stale base-Python install; one asserts a message wording the catalogue no longer has; one fails in the IVA wallet gate and three in storage readiness, all in tests and code this Step did not touch, and all fail the same way run alone.
- `S38` Read end to end: verification reads and writes the local profile store only. Its provider step constructs local objects with no browser or session, the readiness probes are skipped, and no network or subprocess call is reachable. Admitted with the actor taken from the session.
- `S45` Every definition now declares where its subject comes from: 247 the admitted profile, 15 a request field, 6 the work unit that owns a stored record the request names, 1 a field or the profile, 1 a fixed literal. The declaration is in the public contract and its digest, the manifest version is 3, describe and search state it, and the MCP execute tool derives the subject so a client need not supply it. Each family keeps its own check; the declaration is held to it by running every real resolver and executor on the derived subject and on an altered one. Not done here and left as a follow-on: one central guard reading the declaration, and replacing the subject builders of the command line and terminal interface. Outside this Step and failing at HEAD: two failure-log tests assert a traceback another commit stopped logging; four form-layout tests; four IVA wallet tests reporting no usable authority; an M184 error-context key; an M100 export version; and a bulk-classify save count.
- `S37` Follow-up to this Step: seven more operations already open to MCP recorded a caller-typed actor and now take it from the session for an agent: operator IVA, the classification and split reviews, ledger.link, the inventory closing-authority record, the reconciliation import and pull, and the counterparty confirmation. A closing-authority record retried from a different agent session has a different fingerprint and is refused as a conflict.
- `S30` Moved into the operations: the IRPF category must be in the published taxonomy (add, update, classify); the two-decimal limit on update and classify; a blank reason on classify; blank or null description, notes, date, amount, currency and direction on update. Update now answers a refused edit as a validation refusal with no effect, as classify did. Everything else the command line checked was already in the request models or the domain. No frontend list or decision row changed: admission waits on the replay-identity and provenance decisions. Still a failure and not a refusal: state-dependent errors of add, which deliberately keeps its effect unknown, and an unknown own account on update.
- `S32` The resolver refused every frontend but the command line for no reason the code holds; the request carries the classification table as text, not a path. The stored actor is taken from the session for an agent.
- `S33` Set and unset are each recorded as an event and undo one another; their events hard-coded the actor operator and now carry the session label for an agent. Rule add is admitted. Rule apply is admitted except with reaffirm outside a dry run, which overwrites classifications made by hand with no earlier value stored and is refused on MCP until the approval step exists. Reported, not changed: an unset that fails after its write leaves the override cleared with no event, and a retry is refused as having no override.
- `S34` Attach takes identifiers of stored evidence only and detach removes only the link, keeping bytes and manifest. A purchase-evidence link cannot be cleared by detach.
- `S35` No confirmation moved: the only safeguard was the command-line yes flag, kept there. Archive, stash and restore are events over rows that stay stored, and their results now say what they replaced and which operation reverses it. Exclude cleared the business share without recording it; its event now stores the previous value. A manual split keeps the parent stored but only the approval-bound merge recombines it; admitted, with the result naming that. Found and not fixed here: restore has no guard for rows a merge archived and can reactivate them beside the merged row.
- `S42` Evidence update changes descriptive and amount fields only and is no route to confirmation; an agent result carries the file name and not the directory. The invoice intake is typed, not interactive and not a draft promotion; its creation event carries the session label for an agent, which is the only mark on amounts an agent states. The participation rebuild regenerates a derived index. Extraction is admitted for a reader on this machine: the off-machine variant is refused on MCP at the resolver, and because a reader counted as local by provider name alone while its endpoint is a setting, the executor refuses an agent read unless the endpoint is loopback. An agent result carries the review-summary projection and no draft text. Outside these Steps and failing as before: the seven entrypoint tests named under S45, fourteen command-line tests reporting `runtime_unavailable` from the stale base-Python install, and one bulk-classify command test that expects an English message and receives the Spanish one.
- `S44` Local observations and Modelo 145 create and validate are open to MCP. Refused for an agent until the approval step exists: clearing an observation, which keeps no copy of the figure; recording over the observation of a pending local filing, which replaces it; and a Modelo 145 draft that fills the worker signature block or the payer acknowledgement. Not admitted and re-ruled behind approval: `modelo.filing_record.import,` because every writing outcome leaves a record marked as confirmed by the tax agency and in force, it can confirm or retire a pending local filing, and with the register source typed values and a typed reference suffice with no stored receipt. Found and left: recording over a pending filing observation destroys it on every frontend although the module says nothing is destroyed.
- `S01` Follow-up to the first phase review. Every operation the read-only local surface lists is now resolved through its real resolver and required to hold no commit action and to be admitted at submission. A tested table names each request and result field of an MCP-open operation that carries a host path, so an unrecorded one fails and the file-exchange Step removes what it settles; the capture operations were read and only record and echo their root. The two model reviews are recorded as reaching the network. Workflow run reads release an allow-listed set of detail fields, and the projection of details carrying an enumeration member, which failed validation, is repaired.
- `S42` Follow-up found while closing the review. The two model reviews send the person transaction and evidence text to the reader endpoint, which a setting can point at another host; an agent review is now refused unless the endpoint is on this machine, by the one check the extraction uses. The reconciliation import, list and pull results and the local authentication read gave an agent a host path; an agent now receives the file name and a flag that the directory was withheld. Stored records and other frontends are unchanged.
- `S35` Follow-up: restore refused nothing for rows a merge had replaced, so an original could be reactivated beside the merged row and counted twice. Restore now refuses while the row that replaced it is active, in both directions, and stays allowed once that row is archived.
- `S37` Follow-up: invoice add and update recorded a fixed actor for every frontend and now record the session label for an agent; bulk classification recorded a file command as its source for an agent, who sends the table and no file, and now records the operation.
- `S19` Each clause is proven with a real runtime, session authority, encrypted profile, IPC and MCP adapter, with the profile worker as a separate process; only the native login, the keychain and the runtime clock are ports. Idle expiry is shown in two halves because the clock seam moves the runtime and not the worker: a live session is retired when the runtime clock passes the idle deadline, and a stored sign-in sixteen minutes old is refused, removed and replaced only by a new sign-in. No test shows one live session crossing the deadline and its stored record then expiring by itself. The fresh-process test that starts a child runtime and the installed server also passes on this machine.
- `S42` Second review. A request to a loopback endpoint is now sent by a client that ignores environment and system proxy configuration and follows no redirect, chosen from the address about to be used; the guard and the adapter share one definition of a loopback endpoint, strict about credentials where a read is authorised. The adapter still resolves its endpoint when it sends, as the product always did, so nothing forces it to match the settings the guard read if they change in between. Separately, a reader on the MCP frontend is released a result, a result page, a review projection or error detail only for an operation whose stored admission names MCP; a replay from MCP of an operation admitted elsewhere returns its receipt and no content; and a resumed operation is sealed and attributed by its stored admission. The typed ledger history gives its currency field the canonical annotation.
- `S32` Second review, Step reopened. Bulk classification is the write of single classification for many rows, so it no longer lists MCP and waits with single classification, add and update on the replay-identity and provenance decisions; the four rows carry one prerequisite that says so. Each bulk row now passes through the code single classification uses on every frontend: an unknown category, a six-decimal amount, a share on a row that is not mixed and a mixed row without a share each fail that row.
- `S35` Second review. A manual split is not reversible by an agent: the parent keeps its classification, evidence and attachments and only the approval-bound merge recombines it. An agent split of a parent that carries a classification made by hand, linked evidence, a linked invoice or attachments is refused in the executor before any effect; other parents split as before.
- `S37` Second review. Inventory create, movement and valuation record the session label for an agent. A census over the registry fails when a definition open to MCP has an attribution field that no named test proves is session-derived, and when an entry goes stale.
- `S30` Third review. The command line capped every decimal at two digits, share and rate included, and moving its rules into the operations carried that cap with them. A share and a rate are fractions between 0 and 1 with no scale bound, as the domain and the registry rates require; money keeps two digits. Fixed in the operations for classify, add and update, on the command line including allocate and the model command, and in the terminal interface. The classification guide states it, with its three catalogues.
- `S35` Third review. The protection of a hand classification keyed on a last-writer stamp that IVA derivation rewrites and that the model reviews, exclude and detach went round. The row now records the origin of its classification, changed only by a write that changes the classification or its tax figures; older rows read as the person when classified and not rule-stamped. An execution admitted on MCP is refused, before any effect, IVA derivation, both model reviews at the request and at the commit, the manual split and exclude on a row whose classification is the person, replacing an existing invoice link, and detaching evidence an agent did not link. The two census entries for the reviews now point at a test that reads the stored actor. Left for the owner: an agent archiving or stashing the person row, and an agent replacing a usage ratio the person set.
- `S35` Fourth review. A person who confirmed an agent, rule or model classification with the same value, or only completed a field such as the counterparty country, did not become its owner. A person write that names any field of one declared set now takes the row whether or not a value changes, the no-change paths record it as a classification event, and a test holds the set equal to what the classification, update and bulk patches can set. An agent is refused archiving or stashing a row whose classification is the person, and restoring a row whose archived or stashed state the person set. The review commit reads the stored row before any effect. Two entrypoint cases failed under load in the 45-minute parallel run and pass alone.
- `S35` Correction: the four rows for src/cadrumo/locales/{ca,en,es,hu}/common.yml under this Step were logged in error. Those catalogue changes belong to another session and are not part of this Step or its commit.
- `S35` Fifth review. A confirmation whose values compare equal now writes the stored row back with only its origin, stamp, reason, lineage and modification time replaced, and passes the finalised-revision guard only when the transaction identifier and the row fingerprint are unchanged; before, restating 500.00 as 500 moved the fingerprint and turned a verified revision stale. Bulk confirmation agrees with single. An agent is refused linking purchase evidence to a row the person classified, since the link changes how the row is calculated. Two command-line cases errored at setup under load and pass alone. Outside this Step, the seven entrypoint failures named under S45 and the command-line test that expects an English message.
- `S35` Sixth review, which passed the sealed-row fix. Closed after it: a blank purchase evidence identifier is absent and takes nothing; evidence can be attached to a sealed row a rule stamped, because the evidence-only decision no longer compares a stamp the fingerprint does not cover; a refused confirmation that carries a new reason names the differing field; and two test-hygiene points. Left for the owner: whether the filing fingerprint gains the purchase-evidence link in a new field-set version.
- `S47` The per-operation list of frontends is removed from the definition and the public contract, so every one of the 270 operations is submittable from the command line, the terminal interface and MCP (before: 263, 191 and 165); the manifest version is 4. The rulings table is deleted and the two facts the opt-in surface needs live in their own module. New tests hold parity: every operation resolves alike on the three frontends for the same request, and a source scan fails on a comparison of a frontend inside an access path. Failing outside this phase and shown to fail at the last commit too: fifteen terminal-interface tests, 218 command-line tests beside 373 that report the stale base-Python install, and fourteen agent-evaluation tests; eighteen export tests cannot find a corpus file another session renamed.
- `S48` Removed: the guard on rows the person classified and its backstops in the writers, the refusal of an agent read when the reader is not on this machine, the off-machine and reaffirm refusals, the own-account and prorrata refusals, the reduced extract and evidence results, and the single-frontend resolvers. Agents add, update, classify, allocate, merge, remove, reset, import and export as the command line does, with the session recorded as the actor. A directory import is expanded by the operation and an invoice import computes its digest when the caller gives none. Kept as facts: the recorded origin of a classification and the loopback client that ignores proxies.
- `S49` Removed: the refusals of an explicit calculation and of the election and attestation inputs, of clearing an observation and recording over a pending one, of the signed Modelo 145 block, of the Modelo 360 writes, the reduced reconciliation results, and the single-frontend checks in audit, Modelo 036, review package, quickfile, borrador and workstation check. The local reader provisioning operation has a resolver. Thirteen operations newly reachable by an agent record the session as the actor, each proven. Left as it is: export.google-sheets has no resolver and no frontend can submit it.
- `S50` Removed: the capability refusals, the reduced authentication read, the rule that an MCP reader gets only results admitted on MCP, and the frontend conditions on typed secrets, the workbench result, session inventory, automation decisions, sign-out, locking and login methods, in the runtime and in the local runtime client. The execute tool carries a typed secret on the protected frame and typed operator input; a session tool lists, locks, denies automation, signs out, signs in with a password, resumes, resets and changes the password and deletes a profile; lifecycle notices reach an MCP connection. A retired or lost key session authenticates anew once and the runtime answer stands, which restored the revocation reason on MCP. Session-kind checks are unchanged.
- `S51` The connection guide, one technical article and the packaged agent rules, personas and skills no longer say that MCP refuses or withholds anything or that an approval screen exists. They say an agent runs every operation the command line can, and keep as the agent's own conduct that it tells the person and waits for the go-ahead before a destructive act. The statements that nothing is ever filed with the tax agency are unchanged. The connection guide's three catalogues are re-synced.
- `S47` Correction: rows logged under this Step for paths under `src/cadrumo/_data/manual_corpus_text,` `src/cadrumo/_data/registry,` src/cadrumo/adapters/inbound/declaracion/tests and src/cadrumo/tests/fixtures were logged in error. Those changes belong to another session and are not part of this Step or its commit.
- `S52` The door only: no act is registered in the installed composition, and the import inventory and the command table are regenerated once, in S61, when every family has landed. The command line keeps its in-process work.
- `S57` The authority tool keeps every field it returned before and adds the command line's; the metadata inventories are regenerated once, in S61.
- `S53` The command line keeps its in-process work. The worker asks the runtime to start the model server, since a server it started itself ends with it; shown on Windows with the real spawn and scope, by reading only on Linux and macOS. The three new operations and the start instruction go live when S61 wires them into composition.
- `S54` Four operations for the repair work that needs a profile and three acts for the work that needs none; the command and its operation or act call the same application function. The command path of a remedy is resolved in the application from a record of the catalogue's targets that a test holds to the command graph, so the runtime prints the same remedy without importing the command line. Also here: the gate against tax agency write verbs declares the portal catalogue's payment category, which the authority tool enumerates since S57 and only reads.
- `S55` Storage and reset acts, each reply the JSON the command prints. Acts carry their own deadline and a timed out reset reports an unknown outcome read by `reset_status.` The command line did the reset in its own process and could delete a profile's files under a hosted worker; with a runtime reachable it now sends the act, which drains the hosted profiles first, and with none it works in process as before.
- `S56` Profile list, archive inspect and import, and recovery enrolment as acts; recovery revocation and a censo certificate import with preview as operations; the archive export target checks and the delete preflight lifted so a direct client gets them. Replies carry real identifiers and the command line redacts when it prints. The cold profile listing no longer loads the runtime client. Logged here too: the door's models file and its tests, which all four families changed.
- `S58` Review package and report document verification as acts. The report verification operation hashes the bytes it reads when no digest is given. Reconciliation takes the work by coordinates and the observation by the identifier the capture returns, so any client runs capture then reconcile; captures only read.
- `S60` Three native launcher tests and eight sign-in and registration tests fail at the sign-in screen as they did at the last commit. Review interactions were not run on a real runtime here, since each needs Google, a model or a census specimen. The catalogue hunks of another session's two desktop keys are left uncommitted.
- `S59` The installation tool derives its actions and arguments from the act table and the request models. A recovery code minted through MCP is held under a reference in the protected credential store and is never a tool result. The guide for connecting an agent and its three catalogues describe both.
- `S62` A secret can be named by reference beside the typed argument, an unknown outcome is a result and not a tool error, each tool declares the protocol hints, and the handshake-free revision is tested beside the legacy one. Logged here too: the result tool returning a refused operation's recorded detail, the fault names on an invalid request, the profile patch vocabulary on describe, the plugin shipping the generated reference, and the absolute path rule of the audit bundle export. Not run on this machine: the two cases against the real Windows credential store, skipped with error 1312 in this logon session and marked for just test-os-keychain. Results carry no source-kind tag; that earlier ruling is not built here.
- `S39` One quarterly (Modelo 130, 2025 1T) and one annual (Modelo 100, 2025 0A) declaration prepared through MCP tools only equal the command line's on real runtimes with password-protected profiles: ledger rows, every casilla value with its provenance, the verification verdict, a refused verification's code and facts, and the exported bytes. Run alone it passed 2 of 2 here and 2 of 2 in an independent run by another session; beside other native-runtime suites it lost the worker connection at arbitrary steps, never on a comparison. The agent text and the plugin pointer describe the three-column reference.
- `S61` The registry composes the nine new operations and the installed runtime serves all nineteen acts. The gate over 335 executable commands: 274 submit an operation, 13 send a runtime request or an act, 44 work in process with a declared counterpart, 4 have nothing to share, none is left over; it proves a counterpart exists, and sameness rests on each family's parity test. Each surface name is pinned to its tool list. The entrypoint module inventory was long stale, so its regeneration carries unrelated lines. `profile_host.py` is committed for its two lines only, and the aggregate import inventory without another session's dev lines. Open from this work: five tests of `dev/agent_eval/tests/test_mcp_runtime_authority.py` fail since the authority query was rewritten in S57; they are being repaired next.
- `S63` Discovery with no session answers from a generated contract document of 279 operations in fifteen parts, split because the repository bounds an added file at 500 KB. A sessionless reply carries session none; a call on a dead or denied lease now answers from the document, while execute, observe and result stay fenced. A fault's location carries payload member names, so for a mapping-typed field it carries its keys; the financial-input path still answers a bare invalid. Not rerun: the strict type lane. A full wheel build was not run; inclusion of the document is shown by the build backend's own file listing. Failing in `dev/agent_eval` and not from this step: two session-lock parity tests, three golden files where the command line reports no runtime, and the suggestion command conformance count.
- `S55` Reopened by the phase review and closed again. The reset and storage acts run on the root the runtime serves; shown with a runtime over one root while ambient settings name another, whose tree stays byte for byte. In an installed runtime the two cannot differ, since the manager clears the child's environment and pins the root. The command line falls back to in-process work only when the endpoint is absent. An error after a handler's change began settles as failed with effect unknown. Not run on macOS, where a socket left by a crashed runtime reads as indeterminate and the reset says to run again until a runtime clears it.
- `S39` Review follow-up. The proof asserts the stored origin of a classification as its second intended difference, compares event payloads with identifiers named by role, and compares notices where both sides produce them. Alone: quarterly passed in 155 s and annual in 322 s; one whole-file run lost the command line's cold start to a runtime that was unavailable under other load.
- `S60` Review follow-up. The Operations form carries an optional replay key for the operations that can take one, derived from the fact the MCP execute tool uses. The terminal interface composes the operation registry once, in the installed session, and hands it down; a gate that only that module composes it passes again.
- `S61` Review follow-up. Each in-process pair of the counterpart gate names the test that holds the command's output to its counterpart's, and the gate fails if the test does not exist; pairs with no such test are declared unproven with a reason (the bare command and the session-door commands). A reached operation with no access resolver fails the gate; export.google-sheets is the declared exception, a retired template no frontend can submit. The writers of the two generated documents moved to `dev/harness_data;` the render and read logic stays beside the staleness tests because shipped code may not import dev.
- `S62` Review follow-up. A one-use held secret is taken last, immediately before it is sent, under the store's cross-process lock, so a call refused locally or made with no runtime does not spend it and two processes cannot both receive it. A failed changing act answers as unresolved with the act that reads its outcome.
- `S63` Review follow-up. A registry-wide test fails on a request validator whose message interpolates anything but a field name or a constant; it found eleven and each now names the field and the rule without the value, among them the tax identity and date parsers many request models share.
- `S63` Reversal of the validator rewording logged above under this Step: the twelve files are byte-identical to their content before it, checked by object hash, and the scan is deleted. A fault carries the validator's message as the command line shows it and never pydantic's input, context or link. A registered error raised while a worker decodes a request no longer ends the worker; it is answered as invalid with the error's code and message. Left as it was: when the command line builds a request in process and pydantic wraps the refusal, it prints its generic validation boundary with the path and the kind of rule, which predates this work.
- `S63` The financial-input path and an access resolver that raises during admission no longer end the worker; each answers invalid with the registered code and message and the session serves on. Three row validators on the financial path quote the operand's value in their message and are left as they are, since the command line prints them. Open and recorded in the audit: a registered error from a resolver on an action after admission still escapes the loop.
- `S63` Reads answer instead of ending the worker when an access resolver raises: observation, result, result page, review projection and review inspection go through one place. Shown through the real runtime with the work unit removed from the encrypted store behind a running worker, since no frontend act removes one. A plain error from a resolver on a fresh submission answers a bare invalid, shown at the authority level only. Open: start, resume, cancel, detach, apply and reject still end the worker when their access resolution raises.
- `S64` Pre-existing failures outside MCP in the entrypoints lane (modelo 184/303 calculation, ledger bulk classify) and in `dev/agent_eval/tests/test_mcp_frontend_session_lock_parity.py` (key session expiry precedes the human one); a session-mode discovery search hit `runtime_deadline_exceeded` under load and is reworked in S67
- `S65` Another session's sweep commit e292d394b3 took this Step's in-progress production changes and `test_mcp_frontend_person_acts.py;` this Step's commit carries the remaining files
- `S66` Remaining runtime failures are unchanged with the S66 call disabled `(test_grant_change,` provenance) or are deadline and WinError 1312 environment failures; `test_profile_connections` and `test_optional_automation_custody` moved off the MCP frontend after the S65 refusals
- `S67` Folds in the orchestrator-requested keychain fact and remedy from tui-c2 (31def9f426): `runtime_admission` carries SignInRefusal.keychain, `sign_in_refusal_facts` reports `sign_in_keychain,` and a refusal that names it carries the logon remedy instead of the sign-in one; `sign_in_remedy` takes the reply's facts to choose
- `S67` The shipped operation contract document, its generator and the sessionless discovery module are removed: with no session nothing but status answers, so nothing reads them
- `S69` Docs drift gate still fails on how-to/profile-setup.md and reference/identity-and-naming.md, pages this Step did not touch; connect-an-agent's separate-storage section, added untranslated by another session, is translated here so the page is complete
- `S69` The surface pins, the agent command reference and the removal of the shipped contract document were regenerated in S64 and S67 where the tool list changed
- `S69` no-SSH ruling follow-up, commit b71f20ca21
- `S65` defect fix after close: search failed on person acts; commit 07b729934c; harness 300 pass, 1 keychain-logon env failure
- `S70` commit a408f4b773; proof sits beside the runtime fixtures; key route proven by the sign-in adapter credential-reference test; harness has 1 keychain-logon environment failure
- `S65` off-host consent made a person act after live reproduction; commit 3f15f3bdcc; consent surface string unchanged, reported
- `S64` alias removal after import authority finding; commit 84206fbc9d
- `S18` vault check all passes for application-sign-in and mcp-purpose-authentication; mcp-parity reports two pre-existing schema errors (agent-inside and attended-live-sign-in ADRs link no evidence record in related)
- `S71` harness: 1 failure, `test_installed_sign_in_resume` fresh installed process, outside the disclosure path; sign-in suites: framing and lease-transfer fixtures fixed and rerun green, `mcp_operation_discovery` and `mcp_attended_adapter` pass serially (load timeouts); CLI/TUI: specs test fixed, remaining 4 (installed TUI child AttributeError `subscribe_lifecycle_notices,` native session inventory, `runtime_login` prompt) do not reach the disclosure code; boundaries: 15 contracts kept, 2 new test-scoped sibling edges from `test_disclosure_summary.py` `(cli_runner,` `tui.disclosure_pages)` await ratchet approval, the rest pre-existing; `frontend_client.py` hunks were swept into fa4f7dc9c5 by another session
- `S71` boundaries: the two `test_disclosure_summary` sibling edges are gone (new unapproved 144 to 142, none disclosure); the remaining failures are 188 hard findings, 142 ratchet occurrences and a `dev.agent_eval.live` `__main__` load failure, none from S71
- `S72` Inventory and review count-and-page summaries (b) not built: S71's `page_disclosures` is not in HEAD, and an agent key now stores category grants (about 8 KB, mostly the explicit operation list), so the measured blocker is gone; the operation list still caps the inventory at a few agent grants.
- `S72` Follow-up: an agent key stores one grant of every agent operation; its proposal is 721 bytes (about 47 KB listed, about 8 KB with category grants alone). Inventory and review count disclosures by category and page the full list. Ten-key test once refused an approval with `REFUSED_AUTOMATION_ADMINISTRATION` under heavy concurrent load, as the single-key test did once earlier; not reproduced in 30 later approvals.
- `S73` The live run itself awaits the operator's interactive desktop logon: floor access-api-key on this host reports unavailable `credential_store_unavailable` (exit 3), measured on the stale staged package. `dev/agent_eval/tests` has 7 failures from the unmounted config sign-in-hold family, independent of this step.
