---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-09'
modified: '2026-07-09'
step_id: 'S209'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace cross-domain-continuity with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S209 and 2026-05-26-cross-domain-continuity-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The migrate 20 CLI test files from monkeypatch unsecured-backend pattern to isolated_runtime_profile fixture established in test_errors_boundary.py and test_modelo_casilla_normalisation.py and ## Scope

- `full file list: test_apex_workflow_verification test_audit_remediation test_cli_surface test_cold_start_no_profile test_command_suggestions test_fast_path_no_state test_modelo_202_modality test_modelo_discovery_defects test_modelo_period_consistency test_modelo_source_mesh_calculate test_modelo_work_applicability_guard test_modelo_work_ux test_profile_create_taxpayer_type_paths test_profile_incn_new_entity_paths test_profile_lifecycle_verbs test_profile_output_language test_repair_bootstrap_exempt test_root_grammar_invariants test_root_help_shape test_session_lifecycle_roundtrip`
- `per-file triage required some may pass with simple env-var removal`
- `src/aeat/entrypoints/cli/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# migrate 20 CLI test files from monkeypatch unsecured-backend pattern to isolated_runtime_profile fixture established in test_errors_boundary.py and test_modelo_casilla_normalisation.py

## Scope

- `full file list: test_apex_workflow_verification test_audit_remediation test_cli_surface test_cold_start_no_profile test_command_suggestions test_fast_path_no_state test_modelo_202_modality test_modelo_discovery_defects test_modelo_period_consistency test_modelo_source_mesh_calculate test_modelo_work_applicability_guard test_modelo_work_ux test_profile_create_taxpayer_type_paths test_profile_incn_new_entity_paths test_profile_lifecycle_verbs test_profile_output_language test_repair_bootstrap_exempt test_root_grammar_invariants test_root_help_shape test_session_lifecycle_roundtrip`
- `per-file triage required some may pass with simple env-var removal`
- `src/aeat/entrypoints/cli/`

## Description

Verify-close. The 20-file migration this umbrella Step tracks was already landed by its batch children (S252 batch 1, S253 batch 2, S254 batch 3, S244 follow-up — all checked), so no migration work remains at HEAD.

- Grep every CLI test file for the genuine legacy pattern (`monkeypatch.setenv("AEAT_SECRET_STORE_BACKEND", "unsecured")`, `AEAT_ALLOW_UNENCRYPTED`): zero occurrences remain across `src/aeat/entrypoints/cli/tests/`.
- Confirm the local per-file `_isolated_backend` fixtures that retain the old NAME now wrap the canonical `isolated_profile_storage_root` / `isolated_runtime_profile` helper internally (e.g. `test_profile_lifecycle_verbs.py` yields `isolated_profile_storage_root(tmp_path=...)`), so the fixture name is a thin wrapper over the sanctioned helper, not the old monkeypatch.
- Confirm one named file (`test_apex_workflow_verification`) no longer exists (removed during the migration), and that the only residual `AEAT_SECRET_STORE_BACKEND` string is a legitimate output assertion in `test_root_help_shape.py` (`assert "AEAT_SECRET_STORE_BACKEND=file" in config.output`), which is correct to keep.

## Outcome

No further code change required. All 20 files are migrated off the unsecured-backend monkeypatch to the isolated-profile fixture; the genuine legacy pattern is fully absent. The residual grep hits are (a) retained `_isolated_backend` fixture names that internally use the canonical helper and (b) one legitimate CLI-output assertion. Verified against HEAD. The plan checkbox is deferred to the coordinated plan-reconciliation pass.

## Notes

This is an umbrella verify-close: the actual migration executed under the batch children S252/S253/S254 (+S244), which are already checked. The umbrella S209 checkbox lagged its children.
