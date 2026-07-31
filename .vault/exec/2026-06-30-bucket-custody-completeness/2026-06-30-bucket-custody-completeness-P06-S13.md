---
tags:
  - '#exec'
  - '#bucket-custody-completeness'
date: '2026-06-30'
modified: '2026-07-17'
body_hash: 'sha256:3f358e7f1d3f378fe89f27ab74a37ba057419675ccf1b5af614cf6eee6039655'
step_id: 'S13'
related:
  - "[[2026-06-30-bucket-custody-completeness-plan]]"
---

# Extend the sealed roundtrip to seed every carried store with non-default state and assert strict per-store equality

## Scope

- `src/aeat/application/bucket_maintenance/tests/test_service_import_export.py`

## Description

- Extend sealed archive roundtrip coverage to non-default carried stores.
- Import into a fresh storage root and verify restored rows through owning repositories.
- Preserve strict equality for typed history catalogues and restored secure-object stores.

## Outcome

- Complete. The recovery path restores typed financial history plus generic custody stores under a fresh recipient DEK.
- Verified by the custody completeness tests and store matrix described in the audit closeout.

## Notes

- Bucket-local snapshot stores use same-id fresh-DEK recovery, matching the real recovery scenario.
