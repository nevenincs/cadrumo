---
tags:
  - '#audit'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:894dcd40e0291c30e95e92d909b5415474ac8be73f8b6f469f1c105f6e7e45bc'
related: []
---

# `canonical-storage-management` audit: `Dormant storage-category deletion and the unbuilt status-reader feature`

## Scope

The four declared `StorageCategory` members found to have no production
consumer, the evidence for that finding, and their deletion. Records what was
removed and the resumption point for the one member whose feature may still be
built, so a later reader can tell a deliberate deletion from an omission.

Restructured under the required audit headings without any change to its
wording, per the corpus review that found this the only campaign document whose
required sections were empty while its content sat under headings the schema
does not define.

## Findings

### dormant-category-deletion | none | Deletion record: four members with zero production consumers, confirmed by two independent methods

Four declared `StorageCategory` members had zero production consumers, confirmed independently by two methods (attribute-consumption grep, then the stronger string-constant search across all of `src/cadrumo` and `dev/` — not just `.field_name` attribute access) at two separate points in the campaign, most recently re-traced fresh at HEAD immediately before deletion per `aeat-swarm-orchestration`'s re-read-before-acting discipline:

- `storage-backup` (`cadrumo_storage_backup_dir`, subpath `backups`) — the bucket-archive and profile-bundle-export features both write to an operator-named destination, never to this directory.
- `inbox` (`cadrumo_inbox_dir`, subpath `inbox`) and `inbox-pdf` (`cadrumo_inbox_pdf_dir`, subpath `inbox/pdfs`) — only test fixtures ever set these fields; no production module reads them back.
- `status-cache` (`cadrumo_status_cache_dir`, subpath `cache/status-cache`) plus its companion `cadrumo_status_cache_ttl_s` (int, TTL seconds) — see below.

All four were deleted from `core/_storage_taxonomy.py` (the `StorageCategory` enum member and the `_location(...)` declaration) and `core/config.py` (the `Field(...)` declaration, and — for the three `Path`-typed members — their entry in the `_normalize_repo_relative_paths` field-validator list; the int-typed TTL field was never in that list). Every test asserting the *existence* of one of these four as a dormant-but-present member, or its resolved on-disk path, had its assertion removed alongside the member — pinning a deleted member's presence would be exactly the shape that let the keystore-scope defect (a test asserting the WRONG path as correct) survive undetected.

### unbuilt-status-reader-feature | none | The unbuilt status-reader feature: why `status-cache` existed, and what was deliberately left standing

`status-cache` and its TTL companion were declared for a planned AEAT status-page poll that was never implemented. The surrounding scaffolding still exists and is **not** touched by this deletion, because it names AEAT endpoints rather than local storage:

- `aeat_status_detail_url_template` (`Settings`, default from `_default_status_detail_url_template`) — URL path template for a per-expediente detail page (`{expediente_id}` placeholder), e.g. `/wlpl/TC-UTIL/Expediente/Detalle?EXP={expediente_id}`.
- `aeat_status_notificaciones_path` — URL path for the 'Mis notificaciones' listing page, joined against `AEAT_BASE_URL`.

No module in `src/cadrumo` ever read `cadrumo_status_cache_dir` or `cadrumo_status_cache_ttl_s` — the cache directory and its TTL were declared ahead of a status-reader implementation that never landed. Under `no-legacy-compatibility` (`PRE_RELEASE` regime) and the operator-honesty case for `config storage list` (a category nothing will ever write is a worse operator experience than a documented gap), the settings are deleted now rather than carried as permanent declaration-only weight — re-adding them is an ordinary operation the moment the feature is actually built, since the lifecycle/liveness gates classify by walking `Settings.model_fields` and the taxonomy rather than a hand-maintained list.

## Recommendations

**Resumption point, if the status-reader feature is built:** re-add `cadrumo_status_cache_dir` (subpath `cache/status-cache`, `StorageLifecycle.TTL`, `FingerprintParticipation.EXCLUDED`, matching the pre-deletion declaration) and `cadrumo_status_cache_ttl_s` as a taxonomy member and a `Settings` field respectively, with a real `consumer_module` naming whatever reads the AEAT status page and writes the cache. The two URL-template constants above already exist and need no changes.
