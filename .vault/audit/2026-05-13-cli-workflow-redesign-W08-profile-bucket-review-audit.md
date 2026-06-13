---
tags:
  - '#audit'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
related:
  - '[[2026-05-13-cli-workflow-redesign-epic-plan]]'
  - '[[2026-05-12-cli-workflow-redesign-profile-read-path-retirement-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-adr]]'
  - '[[2026-05-13-cli-workflow-redesign-w08-summary-exec]]'
---

# `cli-workflow-redesign` `W08 profile bucket` Code Review


W08-PROFILE-BUCKET-001 | RESOLVED | `WorkflowState.profiles` now stores strict profile bucket pointers only.

`src/aeat/application/workflow/_models.py` defines `ProfileBucketPointer` as a strict, frozen, `extra="forbid"` Pydantic model, and `WorkflowState.profiles` is typed as `dict[str, ProfileBucketPointer]`. `active_profile_record()` dereferences the active profile through `pointer.bucket_id`, and `active_profile_bucket_id()` exposes the same backend-derived bucket id for other application services. `src/aeat/application/config_reset.py` and `src/aeat/application/setup_reset.py` delete persisted profile buckets by the pointer bucket ids rather than by profile-map keys. `src/aeat/application/profile/test_actions.py` includes negative regression coverage that rejects value-bearing workflow profile payloads.

## Verification

`uv run --no-sync pytest src/aeat/application/profile/test_actions.py src/aeat/application/archive/test_archive.py src/aeat/application/workflow/test_adapters.py src/aeat/application/wizard/test_status.py src/aeat/application/wizard/test_status_next_action.py src/aeat/application/test_config_reset.py src/aeat/application/test_setup_reset.py src/aeat/application/test_config_parity.py src/aeat/entrypoints/cli/filing/test_filing_cli.py src/aeat/entrypoints/cli/test_backend_boundary.py src/aeat/entrypoints/cli/test_workflow_surface.py::test_config_init_profile_set_deadlines_and_filing_runtime_share_profile_bucket src/aeat/tests/test_config.py -q`

Result: 98 passed in 128.38s.

## Status

RESOLVED

W08-PROFILE-BUCKET-002 | RESOLVED | `WorkflowStateRepository.save` refuses value-bearing profile payloads created through unvalidated state copies.

`WorkflowStateRepository.save` revalidates the full `WorkflowState` payload before constructing the encrypted envelope and raises `WorkflowError` before any invalid copied profile payload can be written. Regression coverage attempts to save `WorkflowState().model_copy(update={"profiles": {"kent": {"tax.id": "12345678Z"}}})`, asserts refusal, and verifies the stored state remains readable and empty.

W08-PROFILE-BUCKET-003 | RESOLVED | Pointer dereference and reset tests distinguish profile map keys from bucket ids.

Active profile reads and backend projections use `pointer.bucket_id`, and config/setup reset paths delete profile buckets by the stored bucket id. Non-identical `alias -> actual-bucket` regression coverage proves `active_profile_record()` reads the bucket id from the pointer and both reset paths delete `actual-bucket` rather than relying on the profile-map key.

W08-PROFILE-BUCKET-FINAL | PASS | Final review found no remaining profile-bucket pointer hardening findings.

Reviewed the W08 ADR, epic-plan W08 section, prior audit, execution summary, requested implementation files, and targeted tests after the W08-PROFILE-BUCKET-002/003 fixes. `WorkflowStateRepository.save` revalidates copied workflow state before envelope construction and write; active profile reads and operator projections dereference `pointer.bucket_id`; config/setup reset delete actual profile bucket ids; regression tests use real secure-object persistence and non-identical alias/bucket fixtures. Verification rerun: `uv run --no-sync pytest src/aeat/application/profile/test_actions.py src/aeat/application/archive/test_archive.py src/aeat/application/workflow/test_adapters.py src/aeat/application/wizard/test_status.py src/aeat/application/wizard/test_status_next_action.py src/aeat/application/test_config_reset.py src/aeat/application/test_setup_reset.py src/aeat/application/test_config_parity.py src/aeat/entrypoints/cli/filing/test_filing_cli.py src/aeat/entrypoints/cli/test_backend_boundary.py src/aeat/entrypoints/cli/test_workflow_surface.py::test_config_init_profile_set_deadlines_and_filing_runtime_share_profile_bucket src/aeat/tests/test_config.py -q` passed with 98 tests in 132.21s.
