{
  "receipt_schema": "ModeloWorkspaceC1ExitReceiptV1",
  "validator": "validate_modelo_workspace_c1_exit_receipt",
  "validator_module": "dev/quality/modelo_workspace_receipts.py",
  "validation_result": "PASSED",
  "receipt": {
    "cohort": "c1",
    "schema_version": 1,
    "current_head_commit": "e7b2b9cd858075f9bada9fdb9110c97b63ce4042",
    "governing_records": [
      {
        "stem": "2026-08-24-tui-modelo-workspace-interface-adr",
        "status": "accepted",
        "accepting_commit": "c5ba8fd6eb3756da17f40806438344a257a02599",
        "body_hash": "sha256:0394ec857bf50e11fc9015e7d28baf0dc7adf5c5e668a817359b0e2e87cfd29c"
      }
    ],
    "predecessor_digests": [],
    "compatibility": {
      "workspace": {
        "kind": "not_applicable",
        "evidence_identity": null,
        "evidence_digest": null,
        "not_applicable_code": "c1-no-workspace",
        "owning_authority": "tui-modelo-workspace-interface-adr",
        "reason": "C1 does not consume Workspace V1",
        "evidence_reference": ".vault/adr/2026-08-24-tui-modelo-workspace-interface-adr.md",
        "reopening_condition": "reopens when a later cohort consumes this axis"
      },
      "edit": {
        "kind": "not_applicable",
        "evidence_identity": null,
        "evidence_digest": null,
        "not_applicable_code": "c1-no-edit",
        "owning_authority": "tui-modelo-workspace-interface-adr",
        "reason": "C1 has no editor",
        "evidence_reference": ".vault/adr/2026-08-24-tui-modelo-workspace-interface-adr.md",
        "reopening_condition": "reopens when a later cohort consumes this axis"
      },
      "public_definition": {
        "kind": "not_applicable",
        "evidence_identity": null,
        "evidence_digest": null,
        "not_applicable_code": "c1-no-public-definition",
        "owning_authority": "tui-modelo-workspace-interface-adr",
        "reason": "C1 has no operation definition",
        "evidence_reference": ".vault/adr/2026-08-24-tui-modelo-workspace-interface-adr.md",
        "reopening_condition": "reopens when a later cohort consumes this axis"
      },
      "definition_digest": {
        "kind": "not_applicable",
        "evidence_identity": null,
        "evidence_digest": null,
        "not_applicable_code": "c1-no-definition-digest",
        "owning_authority": "tui-modelo-workspace-interface-adr",
        "reason": "C1 has no operation definition",
        "evidence_reference": ".vault/adr/2026-08-24-tui-modelo-workspace-interface-adr.md",
        "reopening_condition": "reopens when a later cohort consumes this axis"
      },
      "observation": {
        "kind": "not_applicable",
        "evidence_identity": null,
        "evidence_digest": null,
        "not_applicable_code": "c1-no-observation",
        "owning_authority": "tui-modelo-workspace-interface-adr",
        "reason": "C1 has no operation to observe",
        "evidence_reference": ".vault/adr/2026-08-24-tui-modelo-workspace-interface-adr.md",
        "reopening_condition": "reopens when a later cohort consumes this axis"
      },
      "review": {
        "kind": "passed",
        "evidence_identity": "ModeloWorkReviewScreen+ModeloWorkSelectScreen behavioural proof",
        "evidence_digest": "sha256:test_work_review.py+test_c1_bounded_review.py",
        "not_applicable_code": null,
        "owning_authority": null,
        "reason": null,
        "evidence_reference": null,
        "reopening_condition": null
      },
      "refresh_target": {
        "kind": "not_applicable",
        "evidence_identity": null,
        "evidence_digest": null,
        "not_applicable_code": "c1-no-refresh-target",
        "owning_authority": "tui-modelo-workspace-interface-adr",
        "reason": "C1 has no operation refresh target",
        "evidence_reference": ".vault/adr/2026-08-24-tui-modelo-workspace-interface-adr.md",
        "reopening_condition": "reopens when a later cohort consumes this axis"
      },
      "financial_protocol": {
        "kind": "not_applicable",
        "evidence_identity": null,
        "evidence_digest": null,
        "not_applicable_code": "c1-no-financial-protocol",
        "owning_authority": "tui-modelo-workspace-interface-adr",
        "reason": "C1 has no financial operand",
        "evidence_reference": ".vault/adr/2026-08-24-tui-modelo-workspace-interface-adr.md",
        "reopening_condition": "reopens when a later cohort consumes this axis"
      }
    },
    "checklist": {
      "modelo_work_review_relocation": {
        "kind": "passed",
        "evidence_identity": "commits 0b2151ed92295a54637ed2e328fac92c924c8357+fa72300094c268dfefc485b1ba02f3ca5ab2ba9c; legacy _modelo_work_review_screen.py deleted, no remaining reference in the tree",
        "evidence_digest": "sha256:0b2151ed92295a54637ed2e328fac92c924c8357",
        "not_applicable_code": null,
        "owning_authority": null,
        "reason": null,
        "evidence_reference": null,
        "reopening_condition": null
      },
      "locale_geometry_theme_keyboard_non_colour": {
        "kind": "passed",
        "evidence_identity": "src/cadrumo/entrypoints/tui/modelo/tests/test_c1_bounded_review.py (10 passed) + src/cadrumo/entrypoints/tui/modelo/view/tests/test_work_review.py (13 passed)",
        "evidence_digest": "sha256:test_c1_bounded_review.py",
        "not_applicable_code": null,
        "owning_authority": null,
        "reason": null,
        "evidence_reference": null,
        "reopening_condition": null
      },
      "no_legacy_production_import": {
        "kind": "passed",
        "evidence_identity": "zero references to _modelo_work_review_screen anywhere in src/cadrumo; test_modelo_view_namespace_is_inert_and_review_types_have_one_defining_module asserts one defining module",
        "evidence_digest": "sha256:test_modelo_view_namespace_is_inert_and_review_types_have_one_defining_module",
        "not_applicable_code": null,
        "owning_authority": null,
        "reason": null,
        "evidence_reference": null,
        "reopening_condition": null
      }
    }
  },
  "action_denominator_row_count": 79
}
