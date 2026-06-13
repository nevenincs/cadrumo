---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
related:
  - '[[2026-05-13-cli-workflow-redesign-epic-plan]]'
  - '[[2026-05-12-cli-workflow-redesign-profile-read-path-retirement-adr]]'
---

# `cli-workflow-redesign` `W08` summary

Completed W08 profile read path retirement with profile-associated secure
buckets as the only profile value store.

- Created: `src/aeat/application/profile/_repository.py`
- Deleted: `src/aeat/adapters/persistence/profile/tax_residence.py`
- Deleted: `src/aeat/adapters/persistence/profile/test_tax_residence.py`
- Deleted: `src/aeat/application/profile/_storage_namespaces.py`
- Modified: `src/aeat/application/profile/_actions.py`
- Modified: `src/aeat/application/workflow/_models.py`
- Modified: `src/aeat/application/wizard/_persistence.py`
- Modified: `src/aeat/application/archive/_registry.py`
- Modified: `src/aeat/application/archive/test_archive.py`
- Modified: `src/aeat/entrypoints/cli/filing/__init__.py`
- Modified: `src/aeat/entrypoints/cli/test_workflow_surface.py`

## Description

Profile values now live only in `PROFILE_BUCKET_NAMESPACE` as
`Envelope[ProfileBucket]` with `SensitivityClass.IDENTITY`. `WorkflowState`
stores profile pointers only. Wizard persistence, config profile commands,
filing runtime projection, reset behavior, archive export/restore, and overview
deadline readiness now converge on the active profile bucket.

The removed surfaces are not replaced by shims: profile path settings, the
tax-residence profile-path adapter, JSON draft input providers, and filing
`build --inputs` are absent from the retained operator path.

## Tests

`uv run --no-sync pytest src/aeat/application/profile/test_actions.py src/aeat/application/archive/test_archive.py src/aeat/application/workflow/test_adapters.py src/aeat/application/wizard/test_status.py src/aeat/application/wizard/test_status_next_action.py src/aeat/application/test_config_reset.py src/aeat/application/test_setup_reset.py src/aeat/application/test_config_parity.py src/aeat/entrypoints/cli/filing/test_filing_cli.py src/aeat/entrypoints/cli/test_backend_boundary.py src/aeat/entrypoints/cli/test_workflow_surface.py::test_config_init_profile_set_deadlines_and_filing_runtime_share_profile_bucket src/aeat/tests/test_config.py -q`

Result: 98 passed in 128.38s.
