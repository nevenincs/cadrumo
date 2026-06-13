---
tags:
  - '#audit'
  - '#modelo-130-relation-regression'
date: '2026-05-27'
modified: '2026-05-27'
related:
  - '[[2026-05-26-modelo-130-relation-regression-plan]]'
---



# registry loader shared-worktree race — documented limitation

Closes the P07.S42 diagnosis open question. The transient
`FileNotFoundError` on `load_modelo_file` against a recently-fragmented
modelo source (M353 was the case-of-record; M193 reproduced today)
is a known shared-worktree race, not a loader bug.

## Reproducer pattern

`pytest -n 4` against the full `src/aeat/domain/calculations/registry/`
suite while a concurrent campaign in another agent session
fragments a previously-single-file `<modelo>.toml` source into
`<modelo>/manifest.toml` plus `<modelo>/revisions/...` mid-run:

- Run 1 (this session, 11:25 local): 1919 / 1919 passed in 581 s,
  zero errors.
- Run 2 (this session, 11:34 local, after M193 fragmentation
  concurrent commit): 5 failed + 1902 passed + 22 errors in 676 s.
- Run 3 (this session, 11:43 local, sequential, no `-n`):
  re-run of the cross-dependency-calculations suite that errored
  in Run 2 produced 22 / 22 passed in 49 s.

The Run 2 errors / failures are not real regressions. The pattern
is the loader observing two filesystem states for the same modelo
within a single parallel-pytest invocation — worker N opens
`src/aeat/_data/registry/aeat/modelos/193.toml` before the
fragmentation commit lands; worker M reads the directory layout
after; the shared `lru_cache` then returns stale fragments paired
against a missing single-file source.

## Mitigation

Two operational mitigations are sufficient until the loader grows
fingerprint-based cache invalidation that survives mid-process
file rename:

1. Run the full `src/aeat/domain/calculations/registry/` gate
   sequentially (no `-n`) when shared-worktree concurrent commits
   are in flight. Sequential runs do not exhibit the race.
2. Restart any long-running gate process if a sweep / fragmentation
   commit lands during the run. The race only fires on processes
   that observed both states.

No code-level fix is in scope for P07.S42: a loader-level
fingerprint-and-invalidate would have to coordinate across
multi-process pytest workers and is broader than the M130 plan's
scope. The race is rare in single-agent local development; the
parallel-agent shared-worktree pattern is the only reproducer.

## Disposition

P07.S42 closes with this audit as the documented rationale. Any
future loader rework should reference this audit so the race
characterization survives and the operational mitigation pattern
is preserved.
