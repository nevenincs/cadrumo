---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
body_hash: 'sha256:59371841b8d715de8f22a3e21539692ffb2b5d153da5f4a62b35a41dac0d30d3'
step_id: 'S237'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Route both config profile export and subject-access-request through the sole portable-export application service and remove direct serialization, target writes, completion events, and static SAR category ownership from the CLI

## Scope

- `src/cadrumo/entrypoints/cli/_config/_profile_bundle.py`
- `src/cadrumo/entrypoints/cli/tests/test_profile_export_roundtrip.py`
- `src/cadrumo/entrypoints/cli/tests/test_profile_subject_access_request.py`

## Description

Route both `config profile export` and `config profile subject-access-request`
through the single portable-export application service, and remove direct
serialization, target writes, completion-event emission, and static
subject-access-request category ownership from the CLI.

## Outcome

Both verbs in `src/cadrumo/entrypoints/cli/_config/_profile_bundle.py` call the one
application service `export_profile_bundle`, differing only by declared purpose:
the subject-access-request handler at `:155` passes
`ProfileBundleExportPurpose.SUBJECT_ACCESS`, and the export handler at `:385` passes
`ProfileBundleExportPurpose.PORTABLE_TRANSFER`. There is no second orchestration
path and no parallel writer, satisfying the composition-service rule.

The CLI performs no serialization and no target write of its own: it hands the
destination to the service inside `ProfileBundleExportRequest` and reads back
`export.destination` (`:420`) and `export.bundle_schema_version` (`:421`) for
reporting. Both handlers only build a typed result and emit an envelope —
`config.profile.subject_access_request` (`:195`) and `config.profile.export`
(`:425`) — so no completion event is raised from the entrypoint tier.

Static category ownership is gone. `rg` for `DATA_CATEGORIES`, `CATEGORIES =`, and
tuple/list category literals in the module returns no match; the categories are read
from the service result at `:180` and `:181` and rendered from those same values by
`_build_sar_catalogue_notice` (`:210`). The notice explicitly distinguishes the
categories carried in the archive from those deliberately excluded, so the
right-of-access response does not overclaim.

Diagnostics ride the typed `Notice` channel — the catalogue, sensitivity, and
reconcile-failure notices are passed as `notices=` on the envelope, not as bespoke
`advisory`/`next`/`suggestion` fields on the registered result schema.

`test_profile_export_roundtrip.py` and `test_profile_subject_access_request.py` both
passed in the coordinator's W04 gate run
(`uv run --no-sync pytest <14 W04 files> -m "integration and not os_keychain"` →
`1 failed, 154 passed`), the single failure being the unrelated S112 control.

## Notes

This step is the prerequisite the profile-bundle TUI handover was waiting on: the
portable-export routing it needs is in place and the CLI no longer owns a second
serialization path.

`vaultspec-rag` is degraded (truncated code index reporting `degraded_reasons: []`);
all findings were confirmed with `rg` and direct file reads.
