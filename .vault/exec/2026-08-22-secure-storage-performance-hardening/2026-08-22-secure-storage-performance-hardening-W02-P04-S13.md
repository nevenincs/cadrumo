---
tags:
  - '#exec'
  - '#secure-storage-performance-hardening'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:730f9aeba91c01a0a7b3393e834384c3d609cf95dd856e5d98106828923145cb'
step_id: 'S13'
related:
  - "[[2026-08-22-secure-storage-performance-hardening-plan]]"
---

# Convert the complete config subtree from eager registrar imports to nested loader references

## Scope

- `src/cadrumo/entrypoints/cli/_config/`

## Description

- Replace eager config registrars with nested path-bound lazy targets.
- Split metadata-light root, profile-list, profile-status, and Google folder
  ownership without changing command paths, callbacks, options, or locales.
- Bind every current descendant to one distinct immutable target and inspect
  the real live registry by identity.
- Prove sibling isolation, repeated materialization, generated metadata parity,
  family help, and empty profile-list dispatch.
- Profile three fresh cold processes before and after the conversion.
- Resolve all independent-review findings and rerun scoped quality gates.

## Outcome

All 105 current config descendants are registered through distinct immutable
targets, discovered dynamically rather than against a frozen count. Resolution
and help for `config profile list` import 302/305 modules with 190/214 model
constructions and import none of registry, crypto, custody, keyring, or storage;
they perform zero storage operations. Final three-sample medians are 0.899 s
resolution and 0.968 s help invocation, close to the quiet control.

Actual empty-list invocation improved from the 13.588 s baseline median to
8.975 s in the final noisy shared-worktree measurement, while preserving the
empty output contract. Its remaining 1,568 imports, 1,637 model constructions,
and 3,569 storage calls happen after selected handler dispatch and are
explicitly deferred to W03 rather than claimed fixed by registration work.

The complete config test directory passed 283 parallel tests and all 16 held
serial tests. The focused ownership plus authoritative localized metadata lane
passed 19 tests. Scoped Ruff and `ty` passed. Independent review's HIGH and
MEDIUM findings were remediated and re-reviewed.

## Notes

The initial implementation was included by a concurrent shared-worktree writer
in commit `544332300f`; follow-up fixes preserve that history and stage only
S13-owned paths. The generated command-registration cache is CLI-owned and
ignored by repository policy, so it was regenerated and checked locally but
not force-added after the repository deliberately stopped tracking it.

The immediate pre-S13 snapshot reproduced the current preflight authentication
refusal, and both snapshots passed the documented manager-routing behavior.
Those pre-existing security-contract contradictions remain explicit follow-up
work outside S13. No S14 or W03 implementation was absorbed.
