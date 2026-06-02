#!/bin/bash
cd Y:/code/aeat-worktrees/chore-476-restructure-execution

echo "=== P04.S10: Catalogue verification ==="
uv run pytest -xvs -k test_committed_registry_tree_has_required_model_law_coverage 2>&1 | tail -20

echo ""
echo "=== P04.S11: Formula-modelo parity ==="
uv run pytest -xvs -k test_formula_revisions_are_owned_by_constructs_with_snapshot_workflow_surfaces 2>&1 | tail -20

echo ""
echo "=== P04.S12: Modelo parity coverage ==="
uv run pytest -xvs -k test_formula_bearing_modelos_have_constructs_and_model_specific_tests 2>&1 | tail -20

echo ""
echo "=== Encryption surface tests (P03) ==="
uv run pytest -xvs -k "test_blob_and_manifest_round_trip_without_plaintext_files or test_database_payload_is_encrypted_audit_data" 2>&1 | tail -30
