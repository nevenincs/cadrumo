---
tags:
  - '#exec'
  - '#cli-machine-secret-channel-unification'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:8f7e1c0b5f3f15969f101314391acdc8b177686f433391697ba3f750da71716a'
step_id: 'S11'
related:
  - "[[2026-08-23-cli-machine-secret-channel-unification-plan]]"
---




# Run vaultspec-rag semantic code and ADR discovery, confirm exact symbols with rg, then re-read current HEAD, status, and scoped diff, and regenerate all four locales through python -m dev.locales with channel-neutral diagnostics that reserve only fd1/fd2 and remove stale environment and legacy-field strings

## Scope

- `src/cadrumo/locales/ and dev/locales/`

## Description

- Ground the locale diagnostics and accepted transport decision through semantic code and ADR discovery, then confirm live keys and consumers with exact search.
- Replace stdin- and descriptor-specific malformed-payload copy with channel-neutral machine-secret diagnostics in all four catalogues through `python -m dev.locales set`.
- Correct the descriptor refusal copy to reserve only descriptors 1 and 2 and explicitly preserve descriptor 0 as valid.
- Remove the obsolete CLI passphrase-environment route from absent-channel and isolated-execution copy in all four catalogues.
- Extend the focused secure-input locale contract to cover conflict and descriptor refusal keys.
- Run locale integrity, inter-locale parity, translation honesty, focused CLI locale tests, lint, and obsolete-copy searches.

## Outcome

All four runtime catalogues now describe one channel-neutral strict JSON payload contract. Their descriptor refusal tells operators that only stdout and stderr are reserved, while descriptor 0 or another readable descriptor is accepted. Login, profile creation, and configuration overview copy no longer advertise `CADRUMO_SECRET_PASSPHRASE` as a CLI secret source. Focused locale and CLI checks passed with 8 tests and clean lint.

## Notes

The required full scaffold check remains red from unrelated concurrent catalogue/codebase drift: every locale reports 19 missing and 5 extra code keys, with 11 additional pre-existing Hungarian Modelo 390 gaps. The broad parity test likewise reports the shared unrelated source/catalogue mismatch. The scaffold mutation rewrote unrelated shards; those exact rewrites were restored immediately while preserving pre-existing peer-owned Modelo 220 edits. The focused integrity, inter-locale parity, honesty, and diagnostic tests all pass.
