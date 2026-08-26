{
  "receipt_schema_version": 1,
  "artifact_kind": "modelo_workspace_action_denominator",
  "generator": "dev/quality/modelo_workspace_action_denominator.py",
  "generated_at_head": "458592d6275f6e9a541b1ba348cac107e3eb8dc9",
  "candidate_source": [
    "cadrumo.entrypoints.cli.command_api.command_spec_nodes",
    "cadrumo.application.operator_actions.OPERATOR_ACTION_CATALOGUE"
  ],
  "row_count": 78,
  "rows_digest": "sha256:78760c72a72ce2ea7122c3acaa2584d84cceb9a1ad686fd7c48367637df2b035",
  "disposition_tally": {
    "c4_mutation_pending": 31,
    "c1_or_c2_read_pending": 43,
    "flow_owned": 2,
    "deferred": 1,
    "c1_bounded_review": 1
  },
  "rows": [
    {
      "action_identity": "modelo.aggregate",
      "disposition": "c4_mutation_pending",
      "command_key": "app_modelo_aggregate",
      "write_route": "profile-bound",
      "side_effects": [
        "local-state"
      ],
      "has_action_catalogue_entry": false,
      "owning_authority": "tui-interface W06.P12c",
      "reason": "direct-effect mutation; no lifecycle control before C3/C4 receipts are green",
      "evidence_reference": ".vault/adr/2026-08-24-tui-modelo-workspace-interface-adr.md",
      "reopening_condition": "reopens once C3/C4 receipts are green and this is enrolled as a C4 action"
    },
    {
      "action_identity": "modelo.audit.check",
      "disposition": "c1_or_c2_read_pending",
      "command_key": "app_modelo_audit_check",
      "write_route": "none",
      "side_effects": [
        "none"
      ],
      "has_action_catalogue_entry": false,
      "owning_authority": "tui-interface W05.P10/W05.P11",
      "reason": "read-only query, not yet migrated to a C1 or C2 destination",
      "evidence_reference": ".vault/adr/2026-08-24-tui-modelo-workspace-interface-adr.md",
      "reopening_condition": "reopens on migration to a numbered C1/C2 destination in the same commit"
    },
    {
      "action_identity": "modelo.audit.export",
      "disposition": "c4_mutation_pending",
      "command_key": "app_modelo_audit_export",
      "write_route": "profile-bound",
      "side_effects": [
        "local-state"
      ],
      "has_action_catalogue_entry": false,
      "owning_authority": "tui-interface W06.P12c",
      "reason": "direct-effect mutation; no lifecycle control before C3/C4 receipts are green",
      "evidence_reference": ".vault/adr/2026-08-24-tui-modelo-workspace-interface-adr.md",
      "reopening_condition": "reopens once C3/C4 receipts are green and this is enrolled as a C4 action"
    },
    {
      "action_identity": "modelo.audit.view",
      "disposition": "c1_or_c2_read_pending",
      "command_key": "app_modelo_audit_view",
      "write_route": "none",
      "side_effects": [
        "none"
      ],
      "has_action_catalogue_entry": false,
      "owning_authority": "tui-interface W05.P10/W05.P11",
      "reason": "read-only query, not yet migrated to a C1 or C2 destination",
      "evidence_reference": ".vault/adr/2026-08-24-tui-modelo-workspace-interface-adr.md",
      "reopening_condition": "reopens on migration to a numbered C1/C2 destination in the same commit"
    },
    {
      "action_identity": "modelo.bindings.list",
      "disposition": "c1_or_c2_read_pending",
      "command_key": "app_modelo_bindings_list",
      "write_route": "none",
      "side_effects": [
        "none"
      ],
      "has_action_catalogue_entry": true,
      "owning_authority": "tui-interface W05.P10/W05.P11",
      "reason": "read-only query, not yet migrated to a C1 or C2 destination",
      "evidence_reference": ".vault/adr/2026-08-24-tui-modelo-workspace-interface-adr.md",
      "reopening_condition": "reopens on migration to a numbered C1/C2 destination in the same commit"
    },
    {
      "action_identity": "modelo.bindings.resolve",
      "disposition": "c1_or_c2_read_pending",
      "command_key": "app_modelo_bindings_resolve",
      "write_route": "none",
      "side_effects": [
        "none"
      ],
      "has_action_catalogue_entry": false,
      "owning_authority": "tui-interface W05.P10/W05.P11",
      "reason": "read-only query, not yet migrated to a C1 or C2 destination",
      "evidence_reference": ".vault/adr/2026-08-24-tui-modelo-workspace-interface-adr.md",
      "reopening_condition": "reopens on migration to a numbered C1/C2 destination in the same commit"
    },
    {
      "action_identity": "modelo.casilla",
      "disposition": "c1_or_c2_read_pending",
      "command_key": "app_modelo_casilla",
      "write_route": "none",
      "side_effects": [
        "none"
      ],
      "has_action_catalogue_entry": false,
      "owning_authority": "tui-interface W05.P10/W05.P11",
      "reason": "read-only query, not yet migrated to a C1 or C2 destination",
      "evidence_reference": ".vault/adr/2026-08-24-tui-modelo-workspace-interface-adr.md",
      "reopening_condition": "reopens on migration to a numbered C1/C2 destination in the same commit"
    },
    {
      "action_identity": "modelo.casillas",
      "disposition": "c1_or_c2_read_pending",
      "command_key": "app_modelo_casillas",
      "write_route": "none",
      "side_effects": [
        "none"
      ],
      "has_action_catalogue_entry": false,
      "owning_authority": "tui-interface W05.P10/W05.P11",
      "reason": "read-only query, not yet migrated to a C1 or C2 destination",
      "evidence_reference": ".vault/adr/2026-08-24-tui-modelo-workspace-interface-adr.md",
      "reopening_condition": "reopens on migration to a numbered C1/C2 destination in the same commit"
    },
    {
      "action_identity": "modelo.compare",
      "disposition": "c1_or_c2_read_pending",
      "command_key": "app_modelo_compare",
      "write_route": "none",
      "side_effects": [
        "none"
      ],
      "has_action_catalogue_entry": false,
      "owning_authority": "tui-interface W05.P10/W05.P11",
      "reason": "read-only query, not yet migrated to a C1 or C2 destination",
      "evidence_reference": ".vault/adr/2026-08-24-tui-modelo-workspace-interface-adr.md",
      "reopening_condition": "reopens on migration to a numbered C1/C2 destination in the same commit"
    },
    {
      "action_identity": "modelo.describe",
      "disposition": "c1_or_c2_read_pending",
      "command_key": "app_modelo_describe",
      "write_route": "none",
      "side_effects": [
        "none"
      ],
      "has_action_catalogue_entry": true,
      "owning_authority": "tui-interface W05.P10/W05.P11",
      "reason": "read-only query, not yet migrated to a C1 or C2 destination",
      "evidence_reference": ".vault/adr/2026-08-24-tui-modelo-workspace-interface-adr.md",
      "reopening_condition": "reopens on migration to a numbered C1/C2 destination in the same commit"
    },
    {
      "action_identity": "modelo.export",
      "disposition": "c4_mutation_pending",
      "command_key": "app_modelo_export",
      "write_route": "profile-bound",
      "side_effects": [
        "local-state"
      ],
      "has_action_catalogue_entry": false,
      "owning_authority": "tui-interface W06.P12c",
      "reason": "direct-effect mutation; no lifecycle control before C3/C4 receipts are green",
      "evidence_reference": ".vault/adr/2026-08-24-tui-modelo-workspace-interface-adr.md",
      "reopening_condition": "reopens once C3/C4 receipts are green and this is enrolled as a C4 action"
    },
    {
      "action_identity": "modelo.filing_record.import",
      "disposition": "c4_mutation_pending",
      "command_key": "app_modelo_filing_record_import",
      "write_route": "profile-bound",
      "side_effects": [
        "local-state"
      ],
      "has_action_catalogue_entry": false,
      "owning_authority": "tui-interface W06.P12c",
      "reason": "direct-effect mutation; no lifecycle control before C3/C4 receipts are green",
      "evidence_reference": ".vault/adr/2026-08-24-tui-modelo-workspace-interface-adr.md",
      "reopening_condition": "reopens once C3/C4 receipts are green and this is enrolled as a C4 action"
    },
    {
      "action_identity": "modelo.filing_record.list",
      "disposition": "c1_or_c2_read_pending",
      "command_key": "app_modelo_filing_record_list",
      "write_route": "none",
      "side_effects": [
        "none"
      ],
      "has_action_catalogue_entry": true,
      "owning_authority": "tui-interface W05.P10/W05.P11",
      "reason": "read-only query, not yet migrated to a C1 or C2 destination",
      "evidence_reference": ".vault/adr/2026-08-24-tui-modelo-workspace-interface-adr.md",
      "reopening_condition": "reopens on migration to a numbered C1/C2 destination in the same commit"
    },
    {
      "action_identity": "modelo.filing_record.observe_local",
      "disposition": "c4_mutation_pending",
      "command_key": "app_modelo_filing_record_observe_local",
      "write_route": "profile-bound",
      "side_effects": [
        "local-state"
      ],
      "has_action_catalogue_entry": false,
      "owning_authority": "tui-interface W06.P12c",
      "reason": "direct-effect mutation; no lifecycle control before C3/C4 receipts are green",
      "evidence_reference": ".vault/adr/2026-08-24-tui-modelo-workspace-interface-adr.md",
      "reopening_condition": "reopens once C3/C4 receipts are green and this is enrolled as a C4 action"
    },
    {
      "action_identity": "modelo.filing_record.view",
      "disposition": "c1_or_c2_read_pending",
      "command_key": "app_modelo_filing_record_view",
      "write_route": "none",
      "side_effects": [
        "none"
      ],
      "has_action_catalogue_entry": false,
      "owning_authority": "tui-interface W05.P10/W05.P11",
      "reason": "read-only query, not yet migrated to a C1 or C2 destination",
      "evidence_reference": ".vault/adr/2026-08-24-tui-modelo-workspace-interface-adr.md",
      "reopening_condition": "reopens on migration to a numbered C1/C2 destination in the same commit"
    },
    {
      "action_identity": "modelo.formulas",
      "disposition": "c1_or_c2_read_pending",
      "command_key": "app_modelo_formulas",
      "write_route": "none",
      "side_effects": [
        "none"
      ],
      "has_action_catalogue_entry": false,
      "owning_authority": "tui-interface W05.P10/W05.P11",
      "reason": "read-only query, not yet migrated to a C1 or C2 destination",
      "evidence_reference": ".vault/adr/2026-08-24-tui-modelo-workspace-interface-adr.md",
      "reopening_condition": "reopens on migration to a numbered C1/C2 destination in the same commit"
    },
    {
      "action_identity": "modelo.history",
      "disposition": "c1_or_c2_read_pending",
      "command_key": "app_modelo_history",
      "write_route": "none",
      "side_effects": [
        "none"
      ],
      "has_action_catalogue_entry": false,
      "owning_authority": "tui-interface W05.P10/W05.P11",
      "reason": "read-only query, not yet migrated to a C1 or C2 destination",
      "evidence_reference": ".vault/adr/2026-08-24-tui-modelo-workspace-interface-adr.md",
      "reopening_condition": "reopens on migration to a numbered C1/C2 destination in the same commit"
    },
    {
      "action_identity": "modelo.iva_wallet.balance",
      "disposition": "c1_or_c2_read_pending",
      "command_key": "app_modelo_iva_wallet_balance",
      "write_route": "none",
      "side_effects": [
        "none"
      ],
      "has_action_catalogue_entry": false,
      "owning_authority": "tui-interface W05.P10/W05.P11",
      "reason": "read-only query, not yet migrated to a C1 or C2 destination",
      "evidence_reference": ".vault/adr/2026-08-24-tui-modelo-workspace-interface-adr.md",
      "reopening_condition": "reopens on migration to a numbered C1/C2 destination in the same commit"
    },
    {
      "action_identity": "modelo.iva_wallet.correct",
      "disposition": "c4_mutation_pending",
      "command_key": "app_modelo_iva_wallet_correct",
      "write_route": "profile-bound",
      "side_effects": [
        "local-state"
      ],
      "has_action_catalogue_entry": false,
      "owning_authority": "tui-interface W06.P12c",
      "reason": "direct-effect mutation; no lifecycle control before C3/C4 receipts are green",
      "evidence_reference": ".vault/adr/2026-08-24-tui-modelo-workspace-interface-adr.md",
      "reopening_condition": "reopens once C3/C4 receipts are green and this is enrolled as a C4 action"
    },
    {
      "action_identity": "modelo.iva_wallet.override",
      "disposition": "c4_mutation_pending",
      "command_key": "app_modelo_iva_wallet_override",
      "write_route": "profile-bound",
      "side_effects": [
        "local-state"
      ],
      "has_action_catalogue_entry": false,
      "owning_authority": "tui-interface W06.P12c",
      "reason": "direct-effect mutation; no lifecycle control before C3/C4 receipts are green",
      "evidence_reference": ".vault/adr/2026-08-24-tui-modelo-workspace-interface-adr.md",
      "reopening_condition": "reopens once C3/C4 receipts are green and this is enrolled as a C4 action"
    },
    {
      "action_identity": "modelo.iva_wallet.seed",
      "disposition": "c4_mutation_pending",
      "command_key": "app_modelo_iva_wallet_seed",
      "write_route": "profile-bound",
      "side_effects": [
        "local-state"
      ],
      "has_action_catalogue_entry": false,
      "owning_authority": "tui-interface W06.P12c",
      "reason": "direct-effect mutation; no lifecycle control before C3/C4 receipts are green",
      "evidence_reference": ".vault/adr/2026-08-24-tui-modelo-workspace-interface-adr.md",
      "reopening_condition": "reopens once C3/C4 receipts are green and this is enrolled as a C4 action"
    },
    {
      "action_identity": "modelo.list",
      "disposition": "c1_or_c2_read_pending",
      "command_key": "app_modelo_list",
      "write_route": "none",
      "side_effects": [
        "none"
      ],
      "has_action_catalogue_entry": false,
      "owning_authority": "tui-interface W05.P10/W05.P11",
      "reason": "read-only query, not yet migrated to a C1 or C2 destination",
      "evidence_reference": ".vault/adr/2026-08-24-tui-modelo-workspace-interface-adr.md",
      "reopening_condition": "reopens on migration to a numbered C1/C2 destination in the same commit"
    },
    {
      "action_identity": "modelo.m036.alta",
      "disposition": "c4_mutation_pending",
      "command_key": "app_modelo_m036_alta",
      "write_route": "profile-bound",
      "side_effects": [
        "local-state"
      ],
      "has_action_catalogue_entry": false,
      "owning_authority": "tui-interface W06.P12c",
      "reason": "direct-effect mutation; no lifecycle control before C3/C4 receipts are green",
      "evidence_reference": ".vault/adr/2026-08-24-tui-modelo-workspace-interface-adr.md",
      "reopening_condition": "reopens once C3/C4 receipts are green and this is enrolled as a C4 action"
    },
    {
      "action_identity": "modelo.m036.baja",
      "disposition": "c4_mutation_pending",
      "command_key": "app_modelo_m036_baja",
      "write_route": "profile-bound",
      "side_effects": [
        "local-state"
      ],
      "has_action_catalogue_entry": false,
      "owning_authority": "tui-interface W06.P12c",
      "reason": "direct-effect mutation; no lifecycle control before C3/C4 receipts are green",
      "evidence_reference": ".vault/adr/2026-08-24-tui-modelo-workspace-interface-adr.md",
      "reopening_condition": "reopens once C3/C4 receipts are green and this is enrolled as a C4 action"
    },
    {
      "action_identity": "modelo.m036.list",
      "disposition": "c1_or_c2_read_pending",
      "command_key": "app_modelo_m036_list",
      "write_route": "none",
      "side_effects": [
        "none"
      ],
      "has_action_catalogue_entry": false,
      "owning_authority": "tui-interface W05.P10/W05.P11",
      "reason": "read-only query, not yet migrated to a C1 or C2 destination",
      "evidence_reference": ".vault/adr/2026-08-24-tui-modelo-workspace-interface-adr.md",
      "reopening_condition": "reopens on migration to a numbered C1/C2 destination in the same commit"
    },
    {
      "action_identity": "modelo.m036.modificacion",
      "disposition": "c4_mutation_pending",
      "command_key": "app_modelo_m036_modificacion",
      "write_route": "profile-bound",
      "side_effects": [
        "local-state"
      ],
      "has_action_catalogue_entry": false,
      "owning_authority": "tui-interface W06.P12c",
      "reason": "direct-effect mutation; no lifecycle control before C3/C4 receipts are green",
      "evidence_reference": ".vault/adr/2026-08-24-tui-modelo-workspace-interface-adr.md",
      "reopening_condition": "reopens once C3/C4 receipts are green and this is enrolled as a C4 action"
    },
    {
      "action_identity": "modelo.m036.view",
      "disposition": "c1_or_c2_read_pending",
      "command_key": "app_modelo_m036_view",
      "write_route": "none",
      "side_effects": [
        "none"
      ],
      "has_action_catalogue_entry": false,
      "owning_authority": "tui-interface W05.P10/W05.P11",
      "reason": "read-only query, not yet migrated to a C1 or C2 destination",
      "evidence_reference": ".vault/adr/2026-08-24-tui-modelo-workspace-interface-adr.md",
      "reopening_condition": "reopens on migration to a numbered C1/C2 destination in the same commit"
    },
    {
      "action_identity": "modelo.m145.create",
      "disposition": "c4_mutation_pending",
      "command_key": "app_modelo_m145_create",
      "write_route": "profile-bound",
      "side_effects": [
        "local-state"
      ],
      "has_action_catalogue_entry": false,
      "owning_authority": "tui-interface W06.P12c",
      "reason": "direct-effect mutation; no lifecycle control before C3/C4 receipts are green",
      "evidence_reference": ".vault/adr/2026-08-24-tui-modelo-workspace-interface-adr.md",
      "reopening_condition": "reopens once C3/C4 receipts are green and this is enrolled as a C4 action"
    },
    {
      "action_identity": "modelo.m145.export",
      "disposition": "c4_mutation_pending",
      "command_key": "app_modelo_m145_export",
      "write_route": "profile-bound",
      "side_effects": [
        "local-state"
      ],
      "has_action_catalogue_entry": false,
      "owning_authority": "tui-interface W06.P12c",
      "reason": "direct-effect mutation; no lifecycle control before C3/C4 receipts are green",
      "evidence_reference": ".vault/adr/2026-08-24-tui-modelo-workspace-interface-adr.md",
      "reopening_condition": "reopens once C3/C4 receipts are green and this is enrolled as a C4 action"
    },
    {
      "action_identity": "modelo.m145.mark_delivered_to_payer",
      "disposition": "c4_mutation_pending",
      "command_key": "app_modelo_m145_mark_delivered_to_payer",
      "write_route": "profile-bound",
      "side_effects": [
        "local-state"
      ],
      "has_action_catalogue_entry": false,
      "owning_authority": "tui-interface W06.P12c",
      "reason": "direct-effect mutation; no lifecycle control before C3/C4 receipts are green",
      "evidence_reference": ".vault/adr/2026-08-24-tui-modelo-workspace-interface-adr.md",
      "reopening_condition": "reopens once C3/C4 receipts are green and this is enrolled as a C4 action"
    },
    {
      "action_identity": "modelo.m145.mark_locally_completed",
      "disposition": "c4_mutation_pending",
      "command_key": "app_modelo_m145_mark_locally_completed",
      "write_route": "profile-bound",
      "side_effects": [
        "local-state"
      ],
      "has_action_catalogue_entry": false,
      "owning_authority": "tui-interface W06.P12c",
      "reason": "direct-effect mutation; no lifecycle control before C3/C4 receipts are green",
      "evidence_reference": ".vault/adr/2026-08-24-tui-modelo-workspace-interface-adr.md",
      "reopening_condition": "reopens once C3/C4 receipts are green and this is enrolled as a C4 action"
    },
    {
      "action_identity": "modelo.m145.validate",
      "disposition": "c1_or_c2_read_pending",
      "command_key": "app_modelo_m145_validate",
      "write_route": "none",
      "side_effects": [
        "none"
      ],
      "has_action_catalogue_entry": false,
      "owning_authority": "tui-interface W05.P10/W05.P11",
      "reason": "read-only query, not yet migrated to a C1 or C2 destination",
      "evidence_reference": ".vault/adr/2026-08-24-tui-modelo-workspace-interface-adr.md",
      "reopening_condition": "reopens on migration to a numbered C1/C2 destination in the same commit"
    },
    {
      "action_identity": "modelo.project",
      "disposition": "c1_or_c2_read_pending",
      "command_key": "app_modelo_project",
      "write_route": "none",
      "side_effects": [
        "none"
      ],
      "has_action_catalogue_entry": false,
      "owning_authority": "tui-interface W05.P10/W05.P11",
      "reason": "read-only query, not yet migrated to a C1 or C2 destination",
      "evidence_reference": ".vault/adr/2026-08-24-tui-modelo-workspace-interface-adr.md",
      "reopening_condition": "reopens on migration to a numbered C1/C2 destination in the same commit"
    },
    {
      "action_identity": "modelo.readiness",
      "disposition": "c1_or_c2_read_pending",
      "command_key": "app_modelo_readiness",
      "write_route": "none",
      "side_effects": [
        "none"
      ],
      "has_action_catalogue_entry": false,
      "owning_authority": "tui-interface W05.P10/W05.P11",
      "reason": "read-only query, not yet migrated to a C1 or C2 destination",
      "evidence_reference": ".vault/adr/2026-08-24-tui-modelo-workspace-interface-adr.md",
      "reopening_condition": "reopens on migration to a numbered C1/C2 destination in the same commit"
    },
    {
      "action_identity": "modelo.reconcile.history",
      "disposition": "c1_or_c2_read_pending",
      "command_key": "app_modelo_reconcile_history",
      "write_route": "none",
      "side_effects": [
        "none"
      ],
      "has_action_catalogue_entry": false,
      "owning_authority": "tui-interface W05.P10/W05.P11",
      "reason": "read-only query, not yet migrated to a C1 or C2 destination",
      "evidence_reference": ".vault/adr/2026-08-24-tui-modelo-workspace-interface-adr.md",
      "reopening_condition": "reopens on migration to a numbered C1/C2 destination in the same commit"
    },
    {
      "action_identity": "modelo.reconcile.import",
      "disposition": "c4_mutation_pending",
      "command_key": "app_modelo_reconcile_import",
      "write_route": "profile-bound",
      "side_effects": [
        "local-state"
      ],
      "has_action_catalogue_entry": false,
      "owning_authority": "tui-interface W06.P12c",
      "reason": "direct-effect mutation; no lifecycle control before C3/C4 receipts are green",
      "evidence_reference": ".vault/adr/2026-08-24-tui-modelo-workspace-interface-adr.md",
      "reopening_condition": "reopens once C3/C4 receipts are green and this is enrolled as a C4 action"
    },
    {
      "action_identity": "modelo.reconcile.pull",
      "disposition": "c4_mutation_pending",
      "command_key": "app_modelo_reconcile_pull",
      "write_route": "profile-bound",
      "side_effects": [
        "browser",
        "local-state",
        "network"
      ],
      "has_action_catalogue_entry": false,
      "owning_authority": "tui-interface W06.P12c",
      "reason": "direct-effect mutation; no lifecycle control before C3/C4 receipts are green",
      "evidence_reference": ".vault/adr/2026-08-24-tui-modelo-workspace-interface-adr.md",
      "reopening_condition": "reopens once C3/C4 receipts are green and this is enrolled as a C4 action"
    },
    {
      "action_identity": "modelo.requires",
      "disposition": "c1_or_c2_read_pending",
      "command_key": "app_modelo_requires",
      "write_route": "none",
      "side_effects": [
        "none"
      ],
      "has_action_catalogue_entry": false,
      "owning_authority": "tui-interface W05.P10/W05.P11",
      "reason": "read-only query, not yet migrated to a C1 or C2 destination",
      "evidence_reference": ".vault/adr/2026-08-24-tui-modelo-workspace-interface-adr.md",
      "reopening_condition": "reopens on migration to a numbered C1/C2 destination in the same commit"
    },
    {
      "action_identity": "modelo.review_package.build",
      "disposition": "c4_mutation_pending",
      "command_key": "app_modelo_review_package_build",
      "write_route": "profile-bound",
      "side_effects": [
        "local-state"
      ],
      "has_action_catalogue_entry": false,
      "owning_authority": "tui-interface W06.P12c",
      "reason": "direct-effect mutation; no lifecycle control before C3/C4 receipts are green",
      "evidence_reference": ".vault/adr/2026-08-24-tui-modelo-workspace-interface-adr.md",
      "reopening_condition": "reopens once C3/C4 receipts are green and this is enrolled as a C4 action"
    },
    {
      "action_identity": "modelo.review_package.counter_sign",
      "disposition": "c4_mutation_pending",
      "command_key": "app_modelo_review_package_counter_sign",
      "write_route": "profile-bound",
      "side_effects": [
        "local-state"
      ],
      "has_action_catalogue_entry": false,
      "owning_authority": "tui-interface W06.P12c",
      "reason": "direct-effect mutation; no lifecycle control before C3/C4 receipts are green",
      "evidence_reference": ".vault/adr/2026-08-24-tui-modelo-workspace-interface-adr.md",
      "reopening_condition": "reopens once C3/C4 receipts are green and this is enrolled as a C4 action"
    },
    {
      "action_identity": "modelo.review_package.decrypt",
      "disposition": "c4_mutation_pending",
      "command_key": "app_modelo_review_package_decrypt",
      "write_route": "profile-bound",
      "side_effects": [
        "local-state"
      ],
      "has_action_catalogue_entry": false,
      "owning_authority": "tui-interface W06.P12c",
      "reason": "direct-effect mutation; no lifecycle control before C3/C4 receipts are green",
      "evidence_reference": ".vault/adr/2026-08-24-tui-modelo-workspace-interface-adr.md",
      "reopening_condition": "reopens once C3/C4 receipts are green and this is enrolled as a C4 action"
    },
    {
      "action_identity": "modelo.review_package.encrypt_feedback",
      "disposition": "c1_or_c2_read_pending",
      "command_key": "app_modelo_review_package_encrypt_feedback",
      "write_route": "none",
      "side_effects": [
        "local-state"
      ],
      "has_action_catalogue_entry": false,
      "owning_authority": "tui-interface W05.P10/W05.P11",
      "reason": "read-only query, not yet migrated to a C1 or C2 destination",
      "evidence_reference": ".vault/adr/2026-08-24-tui-modelo-workspace-interface-adr.md",
      "reopening_condition": "reopens on migration to a numbered C1/C2 destination in the same commit"
    },
    {
      "action_identity": "modelo.review_package.encrypt_for_recipient",
      "disposition": "c1_or_c2_read_pending",
      "command_key": "app_modelo_review_package_encrypt_for_recipient",
      "write_route": "none",
      "side_effects": [
        "local-state"
      ],
      "has_action_catalogue_entry": false,
      "owning_authority": "tui-interface W05.P10/W05.P11",
      "reason": "read-only query, not yet migrated to a C1 or C2 destination",
      "evidence_reference": ".vault/adr/2026-08-24-tui-modelo-workspace-interface-adr.md",
      "reopening_condition": "reopens on migration to a numbered C1/C2 destination in the same commit"
    },
    {
      "action_identity": "modelo.review_package.import_feedback",
      "disposition": "c4_mutation_pending",
      "command_key": "app_modelo_review_package_import_feedback",
      "write_route": "profile-bound",
      "side_effects": [
        "local-state"
      ],
      "has_action_catalogue_entry": false,
      "owning_authority": "tui-interface W06.P12c",
      "reason": "direct-effect mutation; no lifecycle control before C3/C4 receipts are green",
      "evidence_reference": ".vault/adr/2026-08-24-tui-modelo-workspace-interface-adr.md",
      "reopening_condition": "reopens once C3/C4 receipts are green and this is enrolled as a C4 action"
    },
    {
      "action_identity": "modelo.review_package.sign",
      "disposition": "c4_mutation_pending",
      "command_key": "app_modelo_review_package_sign",
      "write_route": "profile-bound",
      "side_effects": [
        "local-state"
      ],
      "has_action_catalogue_entry": false,
      "owning_authority": "tui-interface W06.P12c",
      "reason": "direct-effect mutation; no lifecycle control before C3/C4 receipts are green",
      "evidence_reference": ".vault/adr/2026-08-24-tui-modelo-workspace-interface-adr.md",
      "reopening_condition": "reopens once C3/C4 receipts are green and this is enrolled as a C4 action"
    },
    {
      "action_identity": "modelo.review_package.verify",
      "disposition": "c1_or_c2_read_pending",
      "command_key": "app_modelo_review_package_verify",
      "write_route": "none",
      "side_effects": [
        "none"
      ],
      "has_action_catalogue_entry": false,
      "owning_authority": "tui-interface W05.P10/W05.P11",
      "reason": "read-only query, not yet migrated to a C1 or C2 destination",
      "evidence_reference": ".vault/adr/2026-08-24-tui-modelo-workspace-interface-adr.md",
      "reopening_condition": "reopens on migration to a numbered C1/C2 destination in the same commit"
    },
    {
      "action_identity": "modelo.review_package.verify_receipt",
      "disposition": "c1_or_c2_read_pending",
      "command_key": "app_modelo_review_package_verify_receipt",
      "write_route": "none",
      "side_effects": [
        "none"
      ],
      "has_action_catalogue_entry": false,
      "owning_authority": "tui-interface W05.P10/W05.P11",
      "reason": "read-only query, not yet migrated to a C1 or C2 destination",
      "evidence_reference": ".vault/adr/2026-08-24-tui-modelo-workspace-interface-adr.md",
      "reopening_condition": "reopens on migration to a numbered C1/C2 destination in the same commit"
    },
    {
      "action_identity": "modelo.review_package.verify_signature",
      "disposition": "c1_or_c2_read_pending",
      "command_key": "app_modelo_review_package_verify_signature",
      "write_route": "none",
      "side_effects": [
        "none"
      ],
      "has_action_catalogue_entry": false,
      "owning_authority": "tui-interface W05.P10/W05.P11",
      "reason": "read-only query, not yet migrated to a C1 or C2 destination",
      "evidence_reference": ".vault/adr/2026-08-24-tui-modelo-workspace-interface-adr.md",
      "reopening_condition": "reopens on migration to a numbered C1/C2 destination in the same commit"
    },
    {
      "action_identity": "modelo.spreadsheet.calculate",
      "disposition": "c4_mutation_pending",
      "command_key": "app_modelo_spreadsheet_calculate",
      "write_route": "profile-bound",
      "side_effects": [
        "google",
        "local-state"
      ],
      "has_action_catalogue_entry": false,
      "owning_authority": "tui-interface W06.P12c",
      "reason": "direct-effect mutation; no lifecycle control before C3/C4 receipts are green",
      "evidence_reference": ".vault/adr/2026-08-24-tui-modelo-workspace-interface-adr.md",
      "reopening_condition": "reopens once C3/C4 receipts are green and this is enrolled as a C4 action"
    },
    {
      "action_identity": "modelo.spreadsheet.pull",
      "disposition": "c4_mutation_pending",
      "command_key": "app_modelo_spreadsheet_pull",
      "write_route": "profile-bound",
      "side_effects": [
        "google",
        "local-state"
      ],
      "has_action_catalogue_entry": false,
      "owning_authority": "tui-interface W06.P12c",
      "reason": "direct-effect mutation; no lifecycle control before C3/C4 receipts are green",
      "evidence_reference": ".vault/adr/2026-08-24-tui-modelo-workspace-interface-adr.md",
      "reopening_condition": "reopens once C3/C4 receipts are green and this is enrolled as a C4 action"
    },
    {
      "action_identity": "modelo.spreadsheet.push",
      "disposition": "c4_mutation_pending",
      "command_key": "app_modelo_spreadsheet_push",
      "write_route": "profile-bound",
      "side_effects": [
        "google",
        "local-state"
      ],
      "has_action_catalogue_entry": false,
      "owning_authority": "tui-interface W06.P12c",
      "reason": "direct-effect mutation; no lifecycle control before C3/C4 receipts are green",
      "evidence_reference": ".vault/adr/2026-08-24-tui-modelo-workspace-interface-adr.md",
      "reopening_condition": "reopens once C3/C4 receipts are green and this is enrolled as a C4 action"
    },
    {
      "action_identity": "modelo.spreadsheet.verify",
      "disposition": "c1_or_c2_read_pending",
      "command_key": "app_modelo_spreadsheet_verify",
      "write_route": "none",
      "side_effects": [
        "google"
      ],
      "has_action_catalogue_entry": false,
      "owning_authority": "tui-interface W05.P10/W05.P11",
      "reason": "read-only query, not yet migrated to a C1 or C2 destination",
      "evidence_reference": ".vault/adr/2026-08-24-tui-modelo-workspace-interface-adr.md",
      "reopening_condition": "reopens on migration to a numbered C1/C2 destination in the same commit"
    },
    {
      "action_identity": "modelo.support_matrix",
      "disposition": "c1_or_c2_read_pending",
      "command_key": "app_modelo_support_matrix",
      "write_route": "none",
      "side_effects": [
        "none"
      ],
      "has_action_catalogue_entry": false,
      "owning_authority": "tui-interface W05.P10/W05.P11",
      "reason": "read-only query, not yet migrated to a C1 or C2 destination",
      "evidence_reference": ".vault/adr/2026-08-24-tui-modelo-workspace-interface-adr.md",
      "reopening_condition": "reopens on migration to a numbered C1/C2 destination in the same commit"
    },
    {
      "action_identity": "modelo.verification_report.list",
      "disposition": "c1_or_c2_read_pending",
      "command_key": "app_modelo_verification_report_list",
      "write_route": "none",
      "side_effects": [
        "none"
      ],
      "has_action_catalogue_entry": true,
      "owning_authority": "tui-interface W05.P10/W05.P11",
      "reason": "read-only query, not yet migrated to a C1 or C2 destination",
      "evidence_reference": ".vault/adr/2026-08-24-tui-modelo-workspace-interface-adr.md",
      "reopening_condition": "reopens on migration to a numbered C1/C2 destination in the same commit"
    },
    {
      "action_identity": "modelo.verification_report.view",
      "disposition": "c1_or_c2_read_pending",
      "command_key": "app_modelo_verification_report_view",
      "write_route": "none",
      "side_effects": [
        "none"
      ],
      "has_action_catalogue_entry": false,
      "owning_authority": "tui-interface W05.P10/W05.P11",
      "reason": "read-only query, not yet migrated to a C1 or C2 destination",
      "evidence_reference": ".vault/adr/2026-08-24-tui-modelo-workspace-interface-adr.md",
      "reopening_condition": "reopens on migration to a numbered C1/C2 destination in the same commit"
    },
    {
      "action_identity": "modelo.work.amend",
      "disposition": "c4_mutation_pending",
      "command_key": "app_modelo_work_amend",
      "write_route": "profile-bound",
      "side_effects": [
        "local-state"
      ],
      "has_action_catalogue_entry": false,
      "owning_authority": "tui-interface W06.P12c",
      "reason": "direct-effect mutation; no lifecycle control before C3/C4 receipts are green",
      "evidence_reference": ".vault/adr/2026-08-24-tui-modelo-workspace-interface-adr.md",
      "reopening_condition": "reopens once C3/C4 receipts are green and this is enrolled as a C4 action"
    },
    {
      "action_identity": "modelo.work.amend_wizard",
      "disposition": "flow_owned",
      "command_key": "app_modelo_work_amend_wizard",
      "write_route": "profile-bound",
      "side_effects": [
        "local-state"
      ],
      "has_action_catalogue_entry": false,
      "owning_authority": "tui-architecture guided flows",
      "reason": "guided-wizard command; owned by a flow renderer, not a Workspace destination",
      "evidence_reference": ".vault/adr/2026-08-24-tui-modelo-workspace-interface-adr.md",
      "reopening_condition": "reopens only if C4 assigns this wizard a distinct disposition"
    },
    {
      "action_identity": "modelo.work.calculate",
      "disposition": "c4_mutation_pending",
      "command_key": "app_modelo_work_calculate",
      "write_route": "profile-bound",
      "side_effects": [
        "local-state"
      ],
      "has_action_catalogue_entry": true,
      "owning_authority": "tui-interface W06.P12c",
      "reason": "direct-effect mutation; no lifecycle control before C3/C4 receipts are green",
      "evidence_reference": ".vault/adr/2026-08-24-tui-modelo-workspace-interface-adr.md",
      "reopening_condition": "reopens once C3/C4 receipts are green and this is enrolled as a C4 action"
    },
    {
      "action_identity": "modelo.work.compare_taxation",
      "disposition": "c1_or_c2_read_pending",
      "command_key": "app_modelo_work_compare_taxation",
      "write_route": "none",
      "side_effects": [
        "none"
      ],
      "has_action_catalogue_entry": false,
      "owning_authority": "tui-interface W05.P10/W05.P11",
      "reason": "read-only query, not yet migrated to a C1 or C2 destination",
      "evidence_reference": ".vault/adr/2026-08-24-tui-modelo-workspace-interface-adr.md",
      "reopening_condition": "reopens on migration to a numbered C1/C2 destination in the same commit"
    },
    {
      "action_identity": "modelo.work.create",
      "disposition": "deferred",
      "command_key": "app_modelo_work_create",
      "write_route": "profile-bound",
      "side_effects": [
        "local-state"
      ],
      "has_action_catalogue_entry": true,
      "owning_authority": "work-lifecycle ownership",
      "reason": "work-unit lifecycle creation is owned outside this interface plan",
      "evidence_reference": ".vault/plan/2026-08-11-tui-interface-plan.md",
      "reopening_condition": "reopens only if a future accepted decision moves this into scope"
    },
    {
      "action_identity": "modelo.work.dependencies",
      "disposition": "c1_or_c2_read_pending",
      "command_key": "app_modelo_work_dependencies",
      "write_route": "none",
      "side_effects": [
        "none"
      ],
      "has_action_catalogue_entry": false,
      "owning_authority": "tui-interface W05.P10/W05.P11",
      "reason": "read-only query, not yet migrated to a C1 or C2 destination",
      "evidence_reference": ".vault/adr/2026-08-24-tui-modelo-workspace-interface-adr.md",
      "reopening_condition": "reopens on migration to a numbered C1/C2 destination in the same commit"
    },
    {
      "action_identity": "modelo.work.discard",
      "disposition": "c4_mutation_pending",
      "command_key": "app_modelo_work_discard",
      "write_route": "profile-bound",
      "side_effects": [
        "local-state"
      ],
      "has_action_catalogue_entry": false,
      "owning_authority": "tui-interface W06.P12c",
      "reason": "direct-effect mutation; no lifecycle control before C3/C4 receipts are green",
      "evidence_reference": ".vault/adr/2026-08-24-tui-modelo-workspace-interface-adr.md",
      "reopening_condition": "reopens once C3/C4 receipts are green and this is enrolled as a C4 action"
    },
    {
      "action_identity": "modelo.work.file",
      "disposition": "c4_mutation_pending",
      "command_key": "app_modelo_work_file",
      "write_route": "profile-bound",
      "side_effects": [
        "local-state"
      ],
      "has_action_catalogue_entry": true,
      "owning_authority": "tui-interface W06.P12c",
      "reason": "direct-effect mutation; no lifecycle control before C3/C4 receipts are green",
      "evidence_reference": ".vault/adr/2026-08-24-tui-modelo-workspace-interface-adr.md",
      "reopening_condition": "reopens once C3/C4 receipts are green and this is enrolled as a C4 action"
    },
    {
      "action_identity": "modelo.work.history",
      "disposition": "c1_or_c2_read_pending",
      "command_key": "app_modelo_work_history",
      "write_route": "none",
      "side_effects": [
        "none"
      ],
      "has_action_catalogue_entry": false,
      "owning_authority": "tui-interface W05.P10/W05.P11",
      "reason": "read-only query, not yet migrated to a C1 or C2 destination",
      "evidence_reference": ".vault/adr/2026-08-24-tui-modelo-workspace-interface-adr.md",
      "reopening_condition": "reopens on migration to a numbered C1/C2 destination in the same commit"
    },
    {
      "action_identity": "modelo.work.list",
      "disposition": "c1_or_c2_read_pending",
      "command_key": "app_modelo_work_list",
      "write_route": "none",
      "side_effects": [
        "none"
      ],
      "has_action_catalogue_entry": true,
      "owning_authority": "tui-interface W05.P10/W05.P11",
      "reason": "read-only query, not yet migrated to a C1 or C2 destination",
      "evidence_reference": ".vault/adr/2026-08-24-tui-modelo-workspace-interface-adr.md",
      "reopening_condition": "reopens on migration to a numbered C1/C2 destination in the same commit"
    },
    {
      "action_identity": "modelo.work.observations",
      "disposition": "c1_or_c2_read_pending",
      "command_key": "app_modelo_work_observations",
      "write_route": "none",
      "side_effects": [
        "none"
      ],
      "has_action_catalogue_entry": false,
      "owning_authority": "tui-interface W05.P10/W05.P11",
      "reason": "read-only query, not yet migrated to a C1 or C2 destination",
      "evidence_reference": ".vault/adr/2026-08-24-tui-modelo-workspace-interface-adr.md",
      "reopening_condition": "reopens on migration to a numbered C1/C2 destination in the same commit"
    },
    {
      "action_identity": "modelo.work.preview_maritime_exemption",
      "disposition": "c1_or_c2_read_pending",
      "command_key": "app_modelo_work_preview_maritime_exemption",
      "write_route": "none",
      "side_effects": [
        "none"
      ],
      "has_action_catalogue_entry": false,
      "owning_authority": "tui-interface W05.P10/W05.P11",
      "reason": "read-only query, not yet migrated to a C1 or C2 destination",
      "evidence_reference": ".vault/adr/2026-08-24-tui-modelo-workspace-interface-adr.md",
      "reopening_condition": "reopens on migration to a numbered C1/C2 destination in the same commit"
    },
    {
      "action_identity": "modelo.work.rename",
      "disposition": "c4_mutation_pending",
      "command_key": "app_modelo_work_rename",
      "write_route": "profile-bound",
      "side_effects": [
        "local-state"
      ],
      "has_action_catalogue_entry": false,
      "owning_authority": "tui-interface W06.P12c",
      "reason": "direct-effect mutation; no lifecycle control before C3/C4 receipts are green",
      "evidence_reference": ".vault/adr/2026-08-24-tui-modelo-workspace-interface-adr.md",
      "reopening_condition": "reopens once C3/C4 receipts are green and this is enrolled as a C4 action"
    },
    {
      "action_identity": "modelo.work.resume",
      "disposition": "c1_or_c2_read_pending",
      "command_key": "app_modelo_work_resume",
      "write_route": "none",
      "side_effects": [
        "none"
      ],
      "has_action_catalogue_entry": false,
      "owning_authority": "tui-interface W05.P10/W05.P11",
      "reason": "read-only query, not yet migrated to a C1 or C2 destination",
      "evidence_reference": ".vault/adr/2026-08-24-tui-modelo-workspace-interface-adr.md",
      "reopening_condition": "reopens on migration to a numbered C1/C2 destination in the same commit"
    },
    {
      "action_identity": "modelo.work.review",
      "disposition": "c1_bounded_review",
      "command_key": "app_modelo_work_review",
      "write_route": "none",
      "side_effects": [
        "none"
      ],
      "has_action_catalogue_entry": false,
      "owning_authority": "tui-architecture W04.P10.S104",
      "reason": "canonically relocated to the C1 bounded-review destination",
      "evidence_reference": ".vault/audit/2026-08-11-casilla-schema-s23-modelo-work-review-audit.md",
      "reopening_condition": "never reopens: terminal C1 disposition"
    },
    {
      "action_identity": "modelo.work.revision",
      "disposition": "c1_or_c2_read_pending",
      "command_key": "app_modelo_work_revision",
      "write_route": "none",
      "side_effects": [
        "none"
      ],
      "has_action_catalogue_entry": false,
      "owning_authority": "tui-interface W05.P10/W05.P11",
      "reason": "read-only query, not yet migrated to a C1 or C2 destination",
      "evidence_reference": ".vault/adr/2026-08-24-tui-modelo-workspace-interface-adr.md",
      "reopening_condition": "reopens on migration to a numbered C1/C2 destination in the same commit"
    },
    {
      "action_identity": "modelo.work.revisions",
      "disposition": "c1_or_c2_read_pending",
      "command_key": "app_modelo_work_revisions",
      "write_route": "none",
      "side_effects": [
        "none"
      ],
      "has_action_catalogue_entry": true,
      "owning_authority": "tui-interface W05.P10/W05.P11",
      "reason": "read-only query, not yet migrated to a C1 or C2 destination",
      "evidence_reference": ".vault/adr/2026-08-24-tui-modelo-workspace-interface-adr.md",
      "reopening_condition": "reopens on migration to a numbered C1/C2 destination in the same commit"
    },
    {
      "action_identity": "modelo.work.run",
      "disposition": "c1_or_c2_read_pending",
      "command_key": "app_modelo_work_run",
      "write_route": "none",
      "side_effects": [
        "none"
      ],
      "has_action_catalogue_entry": false,
      "owning_authority": "tui-interface W05.P10/W05.P11",
      "reason": "read-only query, not yet migrated to a C1 or C2 destination",
      "evidence_reference": ".vault/adr/2026-08-24-tui-modelo-workspace-interface-adr.md",
      "reopening_condition": "reopens on migration to a numbered C1/C2 destination in the same commit"
    },
    {
      "action_identity": "modelo.work.run_details",
      "disposition": "c1_or_c2_read_pending",
      "command_key": "app_modelo_work_run_details",
      "write_route": "none",
      "side_effects": [
        "none"
      ],
      "has_action_catalogue_entry": false,
      "owning_authority": "tui-interface W05.P10/W05.P11",
      "reason": "read-only query, not yet migrated to a C1 or C2 destination",
      "evidence_reference": ".vault/adr/2026-08-24-tui-modelo-workspace-interface-adr.md",
      "reopening_condition": "reopens on migration to a numbered C1/C2 destination in the same commit"
    },
    {
      "action_identity": "modelo.work.runs",
      "disposition": "c1_or_c2_read_pending",
      "command_key": "app_modelo_work_runs",
      "write_route": "none",
      "side_effects": [
        "none"
      ],
      "has_action_catalogue_entry": false,
      "owning_authority": "tui-interface W05.P10/W05.P11",
      "reason": "read-only query, not yet migrated to a C1 or C2 destination",
      "evidence_reference": ".vault/adr/2026-08-24-tui-modelo-workspace-interface-adr.md",
      "reopening_condition": "reopens on migration to a numbered C1/C2 destination in the same commit"
    },
    {
      "action_identity": "modelo.work.status",
      "disposition": "c1_or_c2_read_pending",
      "command_key": "app_modelo_work_status",
      "write_route": "none",
      "side_effects": [
        "none"
      ],
      "has_action_catalogue_entry": true,
      "owning_authority": "tui-interface W05.P10/W05.P11",
      "reason": "read-only query, not yet migrated to a C1 or C2 destination",
      "evidence_reference": ".vault/adr/2026-08-24-tui-modelo-workspace-interface-adr.md",
      "reopening_condition": "reopens on migration to a numbered C1/C2 destination in the same commit"
    },
    {
      "action_identity": "modelo.work.verify",
      "disposition": "c4_mutation_pending",
      "command_key": "app_modelo_work_verify",
      "write_route": "profile-bound",
      "side_effects": [
        "local-state"
      ],
      "has_action_catalogue_entry": true,
      "owning_authority": "tui-interface W06.P12c",
      "reason": "direct-effect mutation; no lifecycle control before C3/C4 receipts are green",
      "evidence_reference": ".vault/adr/2026-08-24-tui-modelo-workspace-interface-adr.md",
      "reopening_condition": "reopens once C3/C4 receipts are green and this is enrolled as a C4 action"
    },
    {
      "action_identity": "modelo.work.wizard",
      "disposition": "flow_owned",
      "command_key": "app_modelo_work_wizard",
      "write_route": "profile-bound",
      "side_effects": [
        "local-state"
      ],
      "has_action_catalogue_entry": false,
      "owning_authority": "tui-architecture guided flows",
      "reason": "guided-wizard command; owned by a flow renderer, not a Workspace destination",
      "evidence_reference": ".vault/adr/2026-08-24-tui-modelo-workspace-interface-adr.md",
      "reopening_condition": "reopens only if C4 assigns this wizard a distinct disposition"
    }
  ]
}
