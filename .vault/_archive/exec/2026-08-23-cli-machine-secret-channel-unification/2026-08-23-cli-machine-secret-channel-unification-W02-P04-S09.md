---
tags:
  - '#exec'
  - '#cli-machine-secret-channel-unification'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:365c0057074546fd5ede40eb01fff74b41cbb2f5bcc10c1199b64fe426d87b4f'
step_id: 'S09'
related:
  - "[[2026-08-23-cli-machine-secret-channel-unification-plan]]"
---

# Run vaultspec-rag semantic code and ADR discovery, confirm exact symbols with rg, then re-read current HEAD, status, and scoped diff, and migrate restore to two conditional canonical payload variants and hard-cut the legacy password field in favor of passphrase

## Scope

- `src/cadrumo/entrypoints/cli/_config/_restore_cli.py`

## Description

- Ground restore behavior and governing decisions through semantic discovery,
  exact symbol search, and current-tree inspection.
- Register strict canonical `passphrase` and `recovery_secret` payload models.
- Select the machine channel once before capsule reads, proof, or publication.
- Route both restore doors through the canonical bounded payload reader and
  verified no-echo prompt fallback.
- Delete the restore-local readers, compatibility selector, duplicated strict
  model configuration, and retired `password` field.
- Update real restore fixtures and add focused hard-cut and variant-isolation
  tests.
- Audit the scoped change for secret safety, ordering, and contract fidelity.

## Outcome

Profile restore now consumes the same paired machine-secret capability as the
other migrated custody verbs. The passphrase door accepts exactly `passphrase`;
the artifact door accepts exactly `recovery_secret`; legacy `password` input is
rejected as an unexpected field. Conflict refusal precedes all reads and the
application restore authorities still perform proof before publication.

## Notes

Focused lint, unit contract, metadata, and real password/recovery restore tests
passed. Import Linter analyzed 5,117 files: nine contracts were kept and the
repository-wide application-to-adapters contract remained broken on existing
application custody and export edges; S09 adds no import edge in that contract.
The campaign-wide real inherited-descriptor subprocess matrix remains in S13
and S14 by plan design. Unrelated shared-worktree changes were preserved.
