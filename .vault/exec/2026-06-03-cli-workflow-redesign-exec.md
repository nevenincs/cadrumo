---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-06-03'
modified: '2026-06-03'
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

## Late-session additions (commits 10 through 28)

After the initial bucket-maintenance landing (commits 1-9), the
session extended into adjacent threads driven by stop-hook
continuation prompts. Recorded here so the full session inventory
sits in one exec doc.

### Additional ADRs (5 total, including initial composition-pattern ADR)

- `2026-06-03-bucket-search-adr` — search-verb scoping to per-domain
  repository dispatch via a closed `BucketSearchScope` enum;
  recency-first ranking MVP; routes never touch `secure_objects`
  ciphertext directly.
- `2026-06-03-bucket-sealed-archive-adr` — tar.gz format with
  positional members (header.json, payload.envelope, optional
  recovery.wrap); metadata-normalisation helper for byte-stable
  archives across hosts; two/three-member layout extensible via
  archive_schema_version.
- `2026-06-03-multi-bucket-test-fixture-adr` — `isolated_two_bucket_runtime`
  contract; distinct test KEK/DEK per bucket; primary-active +
  switch_to_secondary context manager.
- `2026-06-03-iva-exemption-article-adr` — `IvaExemptionArticle`
  discriminator on `IvaClassificationResult` for Art. 20 sub-article
  routing; MVP set `ART_20_UNO_8 / ART_20_UNO_14 / ART_20_UNO_26 /
  ART_20_OTHER`; rejected on non-DOMESTIC_EXEMPT category.

### Apex / child ADR amendments

- Apex ADR `2026-05-12-cli-workflow-redesign-adr` gained a
  2026-06-03 R08-progression amendment recording 3-of-6-verbs-landed.
- Bucket child ADR `2026-05-12-cli-workflow-redesign-bucket-adr`
  gained a 2026-06-03 composition-pattern amendment per verb +
  BUCKET enum + re-export discipline note.
- Ratios-shape child ADR
  `2026-05-12-cli-workflow-redesign-app-ledger-ratios-shape-adr`
  gained a 2026-06-03 composition-pattern alignment note.

### Codified project rules (2)

- `service-imports-via-top-level-reexports` — applied across
  multiple consumer files during the session (orchestration full
  surface promoted + 8 dot-ins migrated in `_modelo.py` and
  `_overview.py` + workflow profile-bucket-scan promoted + 4 more
  consumer migrations).
- `composition-service-no-parallel-write-path` — codified for
  future composition services to delegate to existing single-writer
  primitives.

### Cross-domain landings

- S354 (R9-TOMAS-HIGH `IvaExemptionArticle` discriminator) shipped
  end-to-end: research doc + ADR + implementation (enum + field +
  validator + 8 tests). Unblocks S355 (M303 casilla 61 authoring)
  pending corpus access.
- `bind_error_code` refusal text upgraded with peer-WIP hint
  (closes cross-domain audit Finding 1).

### Infrastructure landings

- Sealed-archive writer + reader + 4-class error catalogue + 9-test
  round-trip suite (commit 22) — ready for `BucketMaintenanceService.export`
  / `.import` service composition once secure-storage envelope-wrapping
  settles.
- `isolated_two_bucket_runtime` fixture + 5-test verification —
  unblocks 3 deferred multi-bucket tests once secure-storage
  per-bucket session/KEK contract settles.
- Export/import Pydantic contracts + `compute_manifest_digest`
  helper (commit 23) with 4-test verification.

### Cross-cutting fixes

- Pre-existing `_parse_iso8601_date` private-name import in
  `aeat.adapters.outbound.fx._ecb_provider` (closes
  `test_no_private_name_cross_package_imports` gate; cleared #640
  pre-existing failure).
- 4 E501 lint errors in `_modelo.py` (consolidated
  per-row CAST-RATIONALE comments).

## Total session cadence

28 commits across 5 plans + 5 ADRs + 2 codified rules + ~100 new
tests + 1 audit doc + 0 destructive operations + 0 peer-WIP
overwrites. Discipline cited at every commit: explicit pathspec on
both `git add` and `git commit`; research-first; package-boundary
re-exports for cross-package consumption; real-behavior tests with
inline deferral notes naming the blocker rather than `xfail`/`skip`.

The next session's first move is unblocked the moment any one of:
(a) peer secure-storage W12+ settles its per-bucket session/KEK
contract, freeing the bucket-maintenance happy-path delete test
and the export/import service composition; (b) peer CLI WIP on
`cli/_config/__init__.py` settles, freeing the S2150 mount of the
three operational bucket-maintenance verbs; (c) AEAT M303 / M210
/ Orden EHA/672/2007 corpus becomes accessible, unblocking the
regulatory-data authoring Steps (S355, S393-S396, S398).
