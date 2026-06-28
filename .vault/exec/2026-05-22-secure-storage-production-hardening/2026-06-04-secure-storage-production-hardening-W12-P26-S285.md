---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S285'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# W12.P26.S285 - Close AFR-183 for active profile health

Scope: close `AFR-183` for `src/aeat/application/workflow/_profile_health.py` with
signals `active-profile, manifest-bucket, master-key, plain-file`, target
`manifest-discovery`, and owner `W12.P22.S90`.

## Description

- Audited active-profile health assessment and repair as an application projection over
  pointer, manifest, workflow-state, and user-profile lifecycle data.
- Confirmed root, pointer, manifest, and encrypted profile reads use centralized
  settings and shared storage helpers.
- Confirmed manifest-status repair is confirmation-gated and writes through the shared
  bucket manifest helper after loading the encrypted active profile record.
- Verified degraded storage states become explicit health statuses or compact error
  fields rather than silent failures.
- Ran vaultspec RAG semantic search and focused profile-health/CLI tests.

## Outcome

`AFR-183` is closed as manifest discovery and repair projection. No production code
change was required for this step.

Validation passed:

- `uv run --no-sync ruff check src/aeat/application/workflow/_profile_health.py src/aeat/application/workflow/test_profile_health.py src/aeat/entrypoints/cli/_config/__init__.py src/aeat/entrypoints/cli/test_profile_lifecycle_verbs.py`
- `uv run --no-sync pytest -q src/aeat/application/workflow/test_profile_health.py src/aeat/entrypoints/cli/test_profile_lifecycle_verbs.py::test_config_profile_show_does_not_suggest_switch_for_missing_record`
- `uv run --no-sync -q python -m aeat.locales audit`
- `uv run --no-sync vaultspec-rag search "active profile health projection manifest status repair next_action settings master key no active bucket session" --type code --port 8766 --max-results 10`

## Notes

The health model's `next_action` values are command pointers for CLI status output,
not localized refusal messages. The CLI layer still owns user-facing rendering around
those health snapshots.
