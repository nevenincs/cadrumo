---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-14'
modified: '2026-05-14'
step_id: 'W13..W19'
related:
  - "[[2026-05-13-cli-workflow-redesign-epic-plan]]"
  - "[[2026-05-12-cli-workflow-redesign-bucket-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-bucket-event-history-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-config-init-shape-adr]]"
  - "[[2026-04-21-auth-cli-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-config-auth-shape-adr]]"
  - "[[2026-05-13-cli-workflow-redesign-config-repair-shape-adr]]"
  - "[[2026-05-13-cli-workflow-redesign-config-profile-use-and-status-adr]]"
---

# `cli-workflow-redesign` W13..W19 closeout

Closed plan rows: every row of Waves `W13..W19`, 210 plan rows
total (S0361..S0570).

## Wave-by-wave verification (head)

### W13 — bucket storage boundary (bucket ADR)
- `domain/buckets/` carries the canonical `BucketEvent`,
  `BucketEventHistoryCatalogue`, `BucketEventType`,
  `BucketEventObjectType`, `derive_bucket_event_id`,
  `append_bucket_event`, `BucketEventHistoryRepository`, plus
  per-bucket secure-DB persistence.
- Every persisted mutation (profile, ledger, modelo) emits a
  bucket-scoped event through the canonical service. The
  `ProfileBucketPointer` model in `application/workflow/_models`
  threads the active bucket id through workflow state.

### W14 — bucket event history (bucket-event-history ADR)
- `BucketEventHistoryRepository` provides load/save over the
  append-only catalogue.
- `aeat config bucket history` is mounted at
  `entrypoints/cli/_config/__init__.py:712` with filters for
  bucket id, event type, object id, actor, since/until.

### W15 — config init shape (config-init-shape ADR)
- `aeat config init --tax-id ... --activity ... [--profile NAME]
  [--output-language] [--non-interactive] [--dry-run]` is
  registered as a top-level `@app.command("init", ...)` and
  delegates through the wizard runner + canonical
  `application.setup.initialize_workspace` service.

### W16 — auth cli + W17 — config auth shape
- `aeat config auth` is mounted with verbs `providers`,
  `configure`, `status`, `test`, `clear`. The provider catalogue
  routes through `application/auth/_catalogue.known_auth_provider_ids`
  and `application/auth/_actions` (configure/clear/status).

### W18 — config repair shape (config-repair-shape ADR)
- `aeat config repair` is mounted with `logs`, `quarantine`,
  `reset-state`, `connectivity`. Each handler is a thin adapter
  over `application/diagnostics` and `application/workflow/_persistence`.

### W19 — config profile use and status
- `aeat config profile use NAME` shipped in W10 closeout (commit
  `a9e0321f`) wrapping the canonical `select_profile`
  orchestration.
- `aeat config profile status` continues to expose the readiness
  projection through `build_wizard_status`.

## Per-phase rationale

Every Wave follows the 5-phase template (backend → shadow
removal → de-shim → verification → thin CLI). All 30 rows per
Wave are closed because:

- The backend service / domain primitive exists and is canonical
  (no parallel surface).
- No shadow duplicates remain — the legacy operator surfaces
  (`aeat setup`, `aeat browser`, `aeat financial`, `aeat
  filing`) are absent from the command tree per
  `test_rejected_aliases_do_not_reach_apex_workflow_services`.
- No shims / placeholder stubs.
- Targeted tests exercise each surface through real services
  (the user_profile, wizard, workflow, diagnostics, and auth
  test packages cover the slice).
- The CLI handlers are thin Typer adapters that delegate to the
  canonical service and render through `_emit`.

## Guards held

- No metastate codification (absence tests for retired roots,
  "removed" sentinels, deferred-code markers).
- No compatibility surface re-introduced.
- The remaining apex/W74A verb-tree completions (`config
  profile add/edit/validate/preflight/export/import`,
  `config profile list --with-status`) are not codified as
  NotImplementedError stubs; their absence is the current
  architectural state and they will land with W74A.
