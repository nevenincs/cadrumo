---
tags:
  - '#exec'
  - '#schema-hardening-coti'
date: '2026-05-22'
modified: '2026-05-22'
step_id: 'S07'
related:
  - '[[2026-05-22-schema-hardening-coti-plan]]'
---



# `schema-hardening-coti` `P03.S07`

Updated reference, audit, and review records for the `coti` burn-down.

- Modified: `.vault/reference/2026-05-21-schema-hardening-reference.md`
- Modified: `.vault/audit/2026-05-21-schema-hardening-semantic-role-sidecar-audit.md`
- Modified: `.vault/audit/2026-05-21-schema-hardening-review.md`
- Created: `.vault/exec/2026-05-22-schema-hardening-coti/2026-05-22-schema-hardening-coti-P03-S07.md`

## Description

The shared vault records now capture that `coti` is source-visible and removed
from broad optional stripping, while remaining optional/numeric families stay
blocked for later source slices.

## Tests

Covered by final vault gate runs.
