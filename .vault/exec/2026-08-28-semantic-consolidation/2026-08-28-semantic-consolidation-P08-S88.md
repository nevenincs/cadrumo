---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-30'
modified: '2026-08-30'
body_schema: 'body-v2'
body_hash: 'sha256:7f78837f886d254e2550d566a982f2f3cea9c79462e130e2258fdf757ecbae4b'
step_id: 'S88'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# Repoint the thirty-eight gate path pins the campaign's renames left naming deleted files, which made those gates scan an empty set and pass while blind

## Scope

- `src/cadrumo/`
- `dev/`

## Changes

- `M` `src/cadrumo/core/tests/test_external_constants.py`
- `M` `src/cadrumo/core/tests/test_external_constants_centralisation_part2.py`
- `M` `src/cadrumo/core/tests/test_persisted_version_single_declaration.py`
- `M` `src/cadrumo/tests/test_parsing_enrollment_inventory.py`
- `M` `src/cadrumo/adapters/persistence/profile/tests/test_every_composing_write_is_declared.py`
- `M` `src/cadrumo/adapters/persistence/storage/tests/test_active_bucket_consumer_coverage.py`
- `M` `src/cadrumo/adapters/persistence/storage/tests/test_sensitive_persistence_policy.py`
- `M` `src/cadrumo/domain/deadlines/tests/test_iva_profile_cutover_static.py`
- `M` `dev/audit/tests/test_dead_code.py`
- `M` `dev/audit/tests/test_dev_rename_audit_tools.py`
- `M` `dev/docs/terminology/tests/test_resolution.py`
- `M` `dev/identity/tests/test_identifier_namespace_enrollment_gate.py`
- `M` `dev/quality/tests/test_rule_citation_resolves.py`
- `M` `dev/tests/test_cli_action_census.py`
- `M` `dev/tests/test_cli_action_census_dispositions.py`
- `M` `dev/tests/test_registry_facade_family_census.py`
- `M` `dev/tests/test_regulatory_drift_census.py`

## Notes

Pins naming files under `domain/modelos/` are deliberately excluded: that
retirement is complete in the working tree but uncommitted, entangled with a
peer's overlapping relocation, so its pins ride with its own commit.
