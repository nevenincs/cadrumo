---
tags:
  - '#audit'
  - '#object-name-declustering'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:1c478d6df046f8e4faa4a1e17ca05830192ffd1a44a092d450c197515b8fc0c0'
related:
  - "[[2026-09-02-object-name-declustering-plan]]"
  - "[[2026-09-02-object-name-declustering-adr]]"
---

# `object-name-declustering` audit: `S32 retained transaction disposition blocker classification`

## Scope

Classified whether the two retained transaction roots named by `W04.P11.S32` can become disposable merely by waiting for adjacent work to settle. The check joined each retained backup to the receipt baseline, the live worktree bytes, and the committed `HEAD` blob without modifying any root or live source file.

The disposition implementation and its accepted invariant require an empty `.absent-paths` marker and every backup to be byte-identical to both the receipt baseline and the live tree immediately before strict removal.

## Findings

### s32-committed-live-divergence | high | both retained roots are permanently non-inert at the current revision

Both roots contain a backup of `src/cadrumo/application/workflow/run_models.py` with Git blob `6f7a7239d107ef7400c8f8b06647c7217718d188`. The live file is clean and equals committed `HEAD` blob `1d93181653ed256f73dc277b1f8f5b989ef2cfcc`. Therefore the required backup/live equality cannot become true when adjacent dirty work settles: the divergence is already committed history. The receipt-bound `dispose` command correctly refuses both roots.

The newer root also currently differs from live `test_file_flow_verify.py` and `test_cross_boundary_roundtrip.py`. Those two paths are dirty and their retained backups still equal `HEAD`, so those mismatches may disappear when their owning session resolves its work. That does not make the root disposable because the committed `run_models.py` mismatch remains.

No retry, quiet period, or exclusive worktree closes this condition. Restoring the old `run_models.py` bytes would reverse committed application work and is not authorised by the disposition invariant.

## Recommendations

Keep both roots intact. Closing `W04.P11.S32` now requires an operator-authorised decision that is not present in the accepted record: either provide a new evidence-preserving disposition for a transaction whose baseline has been superseded by committed work, or explicitly accept restoring the old live bytes before using the existing strict disposer. Do not treat waiting for adjacent sessions as a remedy and do not weaken the implemented equality checks implicitly.
