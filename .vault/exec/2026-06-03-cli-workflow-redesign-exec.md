---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-06-03'
step_id: 'W77.P370.S2131'
related:
  - "[[2026-06-03-cli-workflow-redesign-adr]]"
  - "[[2026-06-03-cli-workflow-redesign-research]]"
  - "[[2026-05-13-cli-workflow-redesign-epic-plan]]"
---

# `cli-workflow-redesign` exec: `W77.P370 bucket-maintenance composition partial landing (rename + delete + browse)`

Records the partial landing of the BucketMaintenanceService against
the composition pattern locked by the 2026-06-03-cli-workflow-redesign-adr.
Three of the six ADR-amendment verbs are now operational; the
remaining three are explicitly scoped follow-ups.

## What landed

### Preconditions (commit `7392f07e`)

- `BucketEventObjectType.BUCKET = "bucket"` added so the four
  bucket-maintenance events (`BUCKET_EXPORTED` / `BUCKET_IMPORTED`
  / `BUCKET_RENAMED` / `BUCKET_DELETED`) can typed-reference the
  container itself.
- Application package re-exports for the bundle serialiser /
  deserialiser / `SUPPORTED_BUNDLE_SCHEMA_VERSIONS` via the existing
  lazy-`__getattr__` + `__all__` pattern.
- Domain package re-export for `UserProfilePortableExport`.
- Regression gate `src/aeat/application/user_profile/test_bundle_reexports.py`
  pins all surfaces so a future refactor cannot silently retract them.

### Rename verb (commit `7d882d5e`)

- `BucketMaintenanceService.rename` delegates to the top-level
  `rename_profile` re-export; emits `BUCKET_RENAMED` from the
  maintenance surface. Co-emission with the inner `PROFILE_RENAMED`
  is the intended audit shape: lifecycle event records the data
  change, maintenance event records the operator's verb.
- Promotes three more orchestration symbols to the application
  package top-level surface: `rename_profile`,
  `delete_profile_with_lifecycle_span`,
  `remove_profile_bucket_directory`.
- Four real-adapter service-contract tests cover result label-pair,
  manifest update, `BUCKET_RENAMED` event payload, co-emission
  contract with `PROFILE_RENAMED`.

Side note: this commit over-included 5 peer secure-storage files due
to a `git add -- <pathspec>` + `git commit -m` interaction that did
not scope the commit. Cross-attribution accepted per operator
direction; from `5ffac4a8` onward, the discipline is
`git commit -F <msgfile> -- <pathspec>` with the pathspec on the
commit verb itself.

### Delete verb (commit `5ffac4a8`)

- `BucketMaintenanceService.delete` composes
  `delete_profile_with_lifecycle_span` (soft tombstone, emits
  `PROFILE_TOMBSTONED`) and `remove_profile_bucket_directory`
  (hard erase); emits `BUCKET_DELETED` into the bucket's own
  history between the soft and hard steps.
- Two service-boundary refusals enforce the destructive-action
  protocol: `confirmed=True` required (CLI `--yes` maps through);
  active bucket cannot be deleted regardless of confirmation
  (operator must switch profiles first).
- Reuses the existing domain `BucketDeleteRefusedError`; no new
  error classes or `ErrorCode` registry entries needed.
- Negative-contract tests cover both refusals + translated-message
  context.

### Browse verb (commit `3d3a99d8a`)

- `BucketMaintenanceService.browse` composes
  `SecureObjectRepository.list_namespaces` with per-namespace
  `list_keys` to return one `BucketNamespaceInventoryRow` per
  stored namespace with its row count. Read-only verb: no bucket
  event emitted. Optional `namespace_filter` substring narrows
  the result set.
- Three real-adapter tests cover per-namespace row counts,
  substring filter restriction, empty-bucket case.

### bind_error_code hint (commit `8b361179a`)

- Closes Finding 1 of `2026-06-03-cross-domain-continuity-audit.md`.
- Extended refusal message names two response paths: declare the
  registry entry alongside the class (genuine new class case), or
  `git status` + rerun (peer-WIP collision case).
- Regression-gated by
  `test_bind_error_code_refusal_carries_diagnostic_hints`.

### S2281 closure (commit `26332fa4`)

- W83.P400.S2281 ticks structurally. Discovery pass found all 5
  required setup-events already wired in production paths from
  prior work; the 2 optional events are dormant enum members with
  no operator path today.
- Inventory test `test_s2281_event_emission_inventory.py` pins
  the four production emission-site modules + presence-checks the
  two dormant enums.
- Audit doc `.vault/audit/2026-06-03-cli-workflow-redesign-audit.md`
  records the closure rationale.

## Verification

- `pytest src/aeat/application/bucket_maintenance/` — 10 passed.
- `pytest src/aeat/application/user_profile/test_bundle_reexports.py` — 7 passed.
- `pytest src/aeat/domain/buckets/` — 32 passed.
- `pytest src/aeat/core/errors/test_registry.py` — 10 passed.
- `pytest src/aeat/application/setup/test_s2281_event_emission_inventory.py` — 5 passed.
- `ruff check` against every changed module — all green.

## Open follow-ups (NOT closed by this exec)

These remain explicit Steps in the plan; each is design-grounded
by the ADR but needs additional turn budget.

### Export verb (W77.P370.S2131 export-half)

Needs the sealed-archive format design: tar.gz with plaintext
`ExportArchiveHeader` frontmatter + encrypted bundle payload +
recovery wrap, written via the existing `serialize_profile_bundle`
output. Service composition: `serialize_profile_bundle` →
`ExportArchiveHeader` wrap → write to `output_path` → emit
`BUCKET_EXPORTED`. Pre-existing application primitives ready; the
sealed-archive write is the new work.

### Import verb (W77.P370.S2131 import-half)

Needs the sealed-archive parse pair to export + the two-tier
collision guard (live-profile-id and bucket-id; refuse unless
`force_replace=True`). Service composition: read sealed archive
→ validate `ExportArchiveHeader` → parse JSON bundle → collision
guard → provision target bucket → `deserialize_profile_bundle` →
emit `BUCKET_IMPORTED`.

### Search verb

Deferred to a dedicated ADR per the composition-pattern decision.
Query syntax, scope, ranking, decryption cost, and redaction
policy are all undecided. Step opens after the search ADR lands.

### Browse key-level surface

The current `browse` returns namespace-level inventory only.
Key-level browse requires decryption (since `list_keys` returns
HMAC digests) and a `SensitivityClass` redaction policy. Follow-up
Step under the composition-pattern ADR.

### Delete happy-path test

The two negative-contract tests cover the service-boundary
refusals; the happy-path soft-tombstone-then-hard-erase composition
test needs a two-bucket fixture (operator's active bucket distinct
from the delete target — the service's active-bucket guard refuses
self-deletion by design). Tracked as a multi-bucket fixture
follow-up under W77.P373.

### Apex ADR R08 closure (W77.P374.S2152)

Originally blocked on full `BucketMaintenanceService` landing.
Three of six verbs are now operational; the apex amendment can
land in stages or wait for the full six. Operator decision.

### Bucket child ADR amendments (W77.P374.S2153)

Update `app-ledger-ratios-shape` and the bucket child ADRs to
reflect the composition-pattern decision. Wait until S2152 lands.

### CLI mount (W77.P374.S2150)

Mount `aeat config bucket {browse / delete / rename}` under
`bucket_app`. Currently blocked by peer-WIP on
`src/aeat/entrypoints/cli/_config/__init__.py`. The pre-landing
pin `test_bucket_app_verb_roster_pins_pre_s2150_state` will fire
when the mount lands, forcing an explicit update.
