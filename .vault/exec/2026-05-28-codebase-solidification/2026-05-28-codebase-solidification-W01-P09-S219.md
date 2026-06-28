---
step_id: S219
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
---

# codebase-solidification W01.P09.S219 — semantic-intent drift sampler enumeration

## Outcome

Enumeration pass complete. Deterministic seed-47 sampler drawn from sorted list of
all `test_*.py` files under `src/aeat/`. 20-file sample spans multiple subpackages
(adapters, application, core, domain). Heuristic: function names containing only
shape-keyword tokens (schema, field, keys, repr, type, len, count, size, contains,
instance, hasattr) without any behaviour-keyword tokens (roundtrip, validate, reject,
parse, persist, scrub, oracle, etc.) are flagged as drift candidates for Wave 2
human review.

Wave 2 follow-up targets: the sampler records candidates without failing on them.
Human review of `drift_candidates` output against the seed-47 sample is the Wave 2
action gate; no explicit Step list generated here (review cadence, not a named
follow-up set).

## Files touched

None (enumeration methodology; results registered in S220 test file).

## Verification

See S220 test file.
