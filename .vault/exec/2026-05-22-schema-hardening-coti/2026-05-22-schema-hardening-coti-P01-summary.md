---
tags:
  - '#exec'
  - '#schema-hardening-coti'
date: '2026-05-22'
modified: '2026-07-17'
body_hash: 'sha256:281f7f9739f74b8e693f8a5569990bcc5a36123731c793b538c6a561abc24afa'
related:
  - '[[2026-05-22-schema-hardening-coti-plan]]'
---

# `schema-hardening-coti` `P01` summary

Completed source confirmation and exact exposure listing for the quoted-fund
`coti` burn-down.

- Modified: `.vault/audit/2026-05-22-schema-hardening-coti-audit.md`
- Created: `.vault/exec/2026-05-22-schema-hardening-coti/2026-05-22-schema-hardening-coti-P01-S01.md`
- Created: `.vault/exec/2026-05-22-schema-hardening-coti/2026-05-22-schema-hardening-coti-P01-S02.md`
- Created: `.vault/exec/2026-05-22-schema-hardening-coti/2026-05-22-schema-hardening-coti-P01-summary.md`

## Description

The phase confirms that `coti` is source-visible and exposes exactly six
current warnings when removed from broad optional-token stripping.

## Tests

The committed registry warning probe produced six warnings, matching the audit
inventory.
