{
  "receipt_schema": "ModeloWorkspaceC2DependencyReceiptV1",
  "validator": "validate_modelo_workspace_c2_dependency_receipt",
  "validator_module": "src/cadrumo/application/modelo/tests/test_workspace_dependency_receipt.py",
  "validation_result": "PASSED",
  "receipt": {
    "schema_version": 1,
    "current_head_commit": "b5ba5a54d25bc48994901d4473394de9cdc83c0b",
    "predecessors": {
      "gate_adr": {
        "stem": "2026-08-24-tui-registry-api-gate-adr",
        "status": "accepted",
        "body_hash": "sha256:932cc01ce41cdf69298ff0f2a831b52aa44429c32307e7af70f9673b05a131be"
      },
      "interface_adr": {
        "stem": "2026-08-24-tui-modelo-workspace-interface-adr",
        "status": "accepted",
        "body_hash": "sha256:0394ec857bf50e11fc9015e7d28baf0dc7adf5c5e668a817359b0e2e87cfd29c"
      },
      "c1_exit_receipt": {
        "path": ".vault\\reference\\2026-08-24-tui-modelo-workspace-interface-c1-exit-receipt-reference.md",
        "validation_result": "PASSED",
        "artifact_digest": "sha256:612d61d48b3142751c87dc2ee33e10d776efa004923117634c3a8f800d5d38fa"
      },
      "authority_grade_decision": {
        "stem": "2026-08-24-tui-registry-api-gate-adr",
        "disposition": "reconciled",
        "reconciliation_artifact_digest": "sha256:a3939c98aa473fae7924fcbe1c82ce1849f8003de89583aa19686e4f8bdc0e7a"
      },
      "native_owner_inventory": {
        "inventory_schema_version": 1,
        "artifact_digest": "e52b0985030e77f0cdc026bcca33021e40966a6a857cc4a2f5705215e24f88c7"
      }
    },
    "native_owner_surfaces": [
      "bounded_review",
      "calculation",
      "closure",
      "field_manifest",
      "locale_catalogue",
      "readiness",
      "registry",
      "work"
    ],
    "producer_stamps": [
      {
        "contributor_kind": "bounded_review",
        "owner": "application.modelo.work_review",
        "producer": "modelo_work_review",
        "contract_digest": "a5faa2fac5e767b63cd83fca02ccad0c4c988c71c0313724bec46ea39e2fc112"
      },
      {
        "contributor_kind": "calculation",
        "owner": "application.modelo.calculation",
        "producer": "calculation_materialization",
        "contract_digest": "3660090756e66d1f5b9b8f93940dcaf4b4ca7aa0dc4885d6e98b92bd6cd761e9"
      },
      {
        "contributor_kind": "closure",
        "owner": "application.registry",
        "producer": "registry_closure",
        "contract_digest": "d244a855c8a4121f9acecd72c15e50314c955ba10c01f55fcbb110075044cf64"
      },
      {
        "contributor_kind": "field_manifest",
        "owner": "application.modelo.workspace_manifest",
        "producer": "workspace_field_manifest",
        "contract_digest": "5942b2155076c065bf8eb04a398348b455208e4cbe3db9b16407d93b32246203"
      },
      {
        "contributor_kind": "locale_catalogue",
        "owner": "locales",
        "producer": "locale_catalogue",
        "contract_digest": "5b7a1224d9639fab9e82f4ce4d1d84332f0f90c08399436eab2336c334a510c2"
      },
      {
        "contributor_kind": "readiness",
        "owner": "application.state_projection",
        "producer": "modelo_readiness",
        "contract_digest": "f94d1a326b57b3f36a4a8cfd26e05891b804addfeb627439581e531525239903"
      },
      {
        "contributor_kind": "registry",
        "owner": "domain.calculations.registry",
        "producer": "validated_registry_projection",
        "contract_digest": "b99fc9f691cf5a4ec15a8eb0fb983def4f3d1041a4b5e8add654d650328304c6"
      },
      {
        "contributor_kind": "work",
        "owner": "application.modelo.work_addressing",
        "producer": "resolved_work_target",
        "contract_digest": "b28b58df29456cfc2e7e9b841b2a267622feec22ca58212331ce972bdecd5544"
      }
    ],
    "epoch_tuple": {
      "digest": "1bbb9042f178e4c67106495f0ca7bef24e5cc01194455f77ef752da308dce762",
      "covered_surfaces": [
        "locale_catalogue",
        "field_manifest",
        "readiness",
        "closure"
      ],
      "excluded_surfaces": [
        "work",
        "registry",
        "calculation",
        "bounded_review"
      ],
      "exclusion_reason": "WORK, REGISTRY, CALCULATION, and BOUNDED_REVIEW each require a work-unit/modelo/period or registry-snapshot coordinate; the C2 gate authorizes the CAPABILITY, not one target's read, so it names no coordinate for these four rather than fabricate one"
    },
    "workspace_schema_fingerprint": "418eff485552f4fc5e29430601b85199a7696d1235b581247cd6a108d1b5b909",
    "field_manifest_digest": "46fdefd980676d1656a047377bea71d174a46b79a7f84f214ffa3c5e5eadf22e",
    "read_destinations": [
      {
        "qualified_name": "cadrumo.application.modelo.workspace.resolve_static_inspection_result",
        "route_level": "function",
        "route_level_rationale": "no frontend/interface consumer exists yet (S129 census); the function IS the route"
      },
      {
        "qualified_name": "cadrumo.application.modelo.workspace.resolve_graded_snapshot_result",
        "route_level": "function",
        "route_level_rationale": "no frontend/interface consumer exists yet (S129 census); the function IS the route"
      }
    ],
    "clean_commit_proof": {
      "outcome": "passed",
      "evidence": "git status --porcelain reports zero changes across 27 dependency paths, 21 of them derived from the fingerprinted model graph at mint time"
    },
    "adr_status_proof": {
      "outcome": "passed",
      "evidence": "# `tui-registry-api-gate` adr: `read-only Modelo workspace projection and capability API` | (**status:** `accepted`)"
    },
    "interface_adr_status_proof": {
      "outcome": "passed",
      "evidence": "# `tui-modelo-workspace-interface` adr: `Modelo workspace interface and staged editor amendment` | (**status:** `accepted`)"
    },
    "c1_exit_receipt_proof": {
      "outcome": "passed",
      "evidence": "2026-08-24-tui-modelo-workspace-interface-c1-exit-receipt-reference.md reads validation_result=PASSED"
    },
    "authority_grade_decision_proof": {
      "outcome": "passed",
      "evidence": "authority-grade admission is ruled by the S287 amendment inside the accepted 2026-08-24-tui-registry-api-gate-adr.md, reconciled by 2026-08-24-tui-registry-api-gate-architecture-reconciliation-audit.md"
    },
    "owner_seam_reconciliation_proof": {
      "outcome": "passed",
      "evidence": "2026-08-25-tui-architecture-workspace-owner-seam-reconciliation-audit.md disposition: RESOLVED (S159 domain->application direction corrected)"
    },
    "native_owner_surface_inventory_proof": {
      "outcome": "passed",
      "evidence": "MODELO_WORKSPACE_PRODUCER_CONTRACT_INVENTORY_V1 classifies exactly the 8 declared ModeloWorkspaceContributorKindV1 members, no more and no fewer"
    },
    "producer_inventory_proof": {
      "outcome": "passed",
      "evidence": "inventory_version=1 digest=e52b0985030e77f0"
    },
    "field_denominator_proof": {
      "outcome": "passed",
      "evidence": "field manifest over 32 roots classifies 2199 entries"
    },
    "process_incarnation_refusal_proof": {
      "outcome": "passed",
      "evidence": "test_workspace_epoch_refuses_cross_domain_coordinates_before_generation_comparison and test_workspace_epochs_make_an_aba_value_transition_observable_without_payload_identity in test_workspace_producers.py prove cross-incarnation and ABA refusal against real epochs"
    },
    "conformance_proof": {
      "outcome": "passed",
      "evidence": "test_workspace.py, test_workspace_models.py, test_workspace_producers.py, test_workspace_manifest.py, and test_workspace_projection.py are the live V1 conformance suite"
    },
    "no_legacy_proof": {
      "outcome": "passed",
      "evidence": "no legacy/migrate/upgrade/deprecated CODE IDENTIFIER (name, class, function, import) across the Workspace module set"
    },
    "redeclaration_proof": {
      "outcome": "passed",
      "evidence": "every canonical Workspace assembly/model/producer entry point is defined in exactly one module"
    }
  }
}
