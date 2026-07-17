---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-12'
modified: '2026-07-17'
step_id: 'S22'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

# Rename product bundle suffixes and reject former bundle formats

## Scope

- `src/cadrumo sealed bucket archive writer/reader/header/service and focused storage/application/CLI tests`

## Description

- Publish `.cadrumo-bucket.tar.gz` as the sole sealed profile-bundle suffix.
- Advance the sealed archive to schema v3 with a required canonical product marker.
- Bind encrypted payload associated data to the Cadrumo v3 archive identity.
- Refuse former suffixes before opening files and renamed former headers before payload reads.
- Update storage, application, custody, and CLI roundtrip examples and assertions.

## Outcome

The writer accepts only the Cadrumo suffix and emits a required `product: cadrumo` header at archive schema version 3. The reader rejects `.aeat-bucket.tar.gz` before opening it. A former archive renamed to the canonical suffix is rejected after reading only the first header member; payload members are not read or adopted. No refusal path migrates, auto-renames, unpacks, copies, or deletes the source.

Forty-five focused tests passed across header validation, roundtrip, crash windows, real service import/export, schema lineage, custody recovery, and CLI workflows. Sentinel tests prove former-suffix bytes and renamed former archive bytes remain unchanged and no canonical output is created. Ruff, formatting, compilation, and scoped diff checks passed.

## Notes

One broader custody-completeness run exposed an unrelated S21 natural-key resolver finding for `cadrumo.application.modelo.m145_communication_record`; the bundle-specific custody recovery test passed in the final focused run. Official AEAT filing/export formats and authority payload terminology were not changed.
