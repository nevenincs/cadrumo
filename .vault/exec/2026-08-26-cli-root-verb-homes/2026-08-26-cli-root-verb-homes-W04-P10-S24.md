---
tags:
  - '#exec'
  - '#cli-root-verb-homes'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:02fea2cd12798f3d5eaae244c44463e568ada047da94b9f6d534078926d7bb12'
step_id: 'S24'
related:
  - "[[2026-08-26-cli-root-verb-homes-plan]]"
---

# Keep config repair integrity registry: the S23 proof shows it exercises the snapshot-build gate that app registry verify does not

## Scope

- `src/cadrumo/entrypoints/cli/_config/`

## Changes

- `M` `.vault/adr/2026-08-26-cli-root-verb-homes-adr.md`
- `M` `.vault/audit/2026-08-25-cli-root-verb-homes-audit.md`

## Notes

No code change. The Step is a ruling, not a deletion: `config repair integrity
registry` is kept on the S23 evidence, and the ADR and audit are amended. The
audit finding is downgraded from duplication to discoverability.
