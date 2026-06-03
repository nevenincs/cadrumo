---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-03'
step_id: 'S320'
related:
  - "[[2026-05-22-secure-storage-production-hardening-refactor-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace secure-storage-production-hardening with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.
     step_id is the originating Step's canonical identifier, e.g. S01.

     Related: use wiki-links as '[[YYYY-MM-DD-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add frontmatter fields
     outside the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path. -->

# W12.P26.S320 bucket event catalogue

## Scope

- `src/aeat/domain/buckets/_event.py`

## Description

- Audited `domain.buckets._event` against the target `remote-mirror` (owner `W12.P24.S98`).
- Confirmed `BucketEventType` carries the censo-mirror event-kind values (`profile.censo.refreshed`, `profile.censo.applied`, `modelo.censo.dependent_stamped_stale`, plus the `modelo.036.declaration.{alta,modificacion,baja}` declarative-recording events landed by the M036 commit 3 verb mount).
- Confirmed the `manifest-bucket` signal is appropriate: every emitted event carries a `bucket_id` field bound to the active manifest bucket, and the deterministic `derive_bucket_event_id` SHA-256 incorporates `bucket_id` into the content-address so cross-bucket replay cannot silently coalesce events.
- Confirmed the `remote-provider` signal is appropriate: the censo refresh/apply events explicitly mirror state read from the AEAT sede remote provider into the bucket-scoped event log, with no remote-write surface. The `MODELO_RECONCILED` and `MODELO_FILING_IMPORTED` events similarly mirror sede-side or operator-imported state into the local catalogue.
- The mirror events are content-addressed and frozen at strict-pydantic boundaries; no parallel write path bypasses the catalogue per the `composition-service-no-parallel-write-path` rule.

## Outcome

- AFR-218 closed: the remote-provider mirror events are appropriately scoped to the bucket-local catalogue; no source change required.
- No new tests authored — the existing bucket-event roundtrip + content-address tests cover the contract.

## Notes

- Audit-only Step; the source file is unchanged.
