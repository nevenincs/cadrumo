---
tags:
  - '#exec'
  - '#registry-temporal-coverage'
date: '2026-08-14'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:e505d76718b048cdc88c4286c461a271778d3522b5f3d9e9a19281d7c10fd2ea'
step_id: 'S36'
related:
  - "[[2026-08-14-registry-temporal-coverage-plan]]"
---

# Reduce the per-load cost the sanctioned authority path charges every caller, by bounding the source-evidence fingerprint collection the way the registry tree fingerprint is already bounded rather than leaving it an uncached recursive walk over the evidence corpus, and by keying the authority cache on a digest of the fingerprint tuples rather than on the tuples themselves so the key hash stops scaling with corpus size, measured before and after against a warm real bundled tree and proven not to weaken invalidation by rerunning the staleness gates that prove a tree edit is seen

## Scope

- `src/cadrumo/domain/calculations/registry/_source_evidence_fingerprint.py`
- `src/cadrumo/domain/calculations/registry/_authority.py`
- `src/cadrumo/domain/calculations/registry/tests/`

## Description

Both S36 production mechanisms landed in commit `a16b0b8ffd`. `_source_evidence_fingerprint.py` bounds bundled evidence-corpus walks by the shared bundled fingerprint window while mutable/specimen roots continue to walk on every call. `authority.py` frames complete fingerprint tuples in `_FingerprintKey`, whose equality and hashing use a canonical fixed-width digest while retaining the tuples for construction and invalidation.

Commit `fad4d426a6` repairs the proof after the authority-root identity API changed and adds a direct walker spy showing one bundled corpus walk followed by hot reuse. No second cache or compatibility path was introduced.

## Outcome

Focused verification passed 18/18 across `test_source_evidence_fingerprint_bound.py` and `test_authority_cache_key_digest.py` in 3.16 seconds. The suite covers mutable immediate invalidation, bundled reuse and explicit clearing, fixed-width canonical digest framing, mutation misses, delimiter safety, immutability, and the resolved authority-root comparison domain. Ruff format/check and `git diff --check` passed.

A one-process component measurement over the real bundled evidence corpus counted 2,458 files. The cleared cold walk took 78.491 ms and the immediate hot lookup took 0.670 ms while returning the same tuple. Across 20,000 repeated hashes, hashing the raw tuple corpus took 624.646 ms and hashing `_FingerprintKey` took 5.912 ms. These measurements isolate S36 without loading the actively changing bundled Modelo 200 authority.

## Notes

The earlier execution snapshot described only the first half as uncommitted and explicitly said digest keying and measurement were missing. That statement is historical and has been superseded: commit `a16b0b8ffd` contains both production halves, and `fad4d426a6` supplies current proof and measurement.

This row consumes no deletion-inventory entry. S29 separately removed the dead mutable-TTL forwarding surface. No Modelo 200 path was touched.
