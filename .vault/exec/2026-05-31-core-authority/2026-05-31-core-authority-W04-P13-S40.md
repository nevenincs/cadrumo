---
step_id: S40
tags:
  - '#exec'
  - '#core-authority'
date: '2026-05-31'
modified: '2026-07-17'
body_hash: 'sha256:004d80c1f7d221344524620bac08edda46c5cdd355137749021ff83b7d18a2d8'
related:
  - '[[2026-05-31-core-authority-plan]]'
  - '[[2026-05-31-core-authority-adr]]'
  - '[[2026-05-31-core-authority-action-tracker-v2-reference]]'
---

# core-authority W04.P13.S40 — BucketActorLabel rename (MERGE-015)

## Files modified

- `src/aeat/domain/buckets/_event.py` — renamed `_ActorLabel` to `BucketActorLabel`; updated field `actor: BucketActorLabel` on `BucketEvent`

## Verification

```
python -c "from aeat.domain.buckets._event import BucketEvent; print('OK')"
# → OK
```

Zero external callers of `_ActorLabel` from `domain/buckets/` confirmed by ripgrep before rename.
