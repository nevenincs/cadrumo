---
tags:
  - '#exec'
  - '#secure-storage-performance-hardening'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:abaebb814f829e643da20f45bff114bec29273e117b19e439310df4879c5bc45'
step_id: 'S07'
related:
  - "[[2026-08-22-secure-storage-performance-hardening-plan]]"
---

# Capture baseline distributions and ranked outliers for every enrolled node as execution evidence

## Scope

- `dev/benchmarks/cli/`

## Description

- Freeze one content-addressed source snapshot before sampling.
- Dynamically enroll every root, group, and leaf in that snapshot.
- Resolve each path and render safe `--help` in fresh processes without executing handlers.
- Capture one warmup and three measured samples per node with periodic concurrent controls.
- Publish a reviewable index and authenticated lossless raw observations.
- Recompute distributions, rankings, failures, and compact evidence during integrity checks.
- Separate immutable source-bound integrity from current-tree freshness.

## Outcome

Captured all 361 snapshot nodes and 100 controls with zero failures or timeouts.
The evidence binds originating revision `f4f45a79b446a6a504831b8c37165ea140565ddf`,
source digest `14b80a63fd368c9bfbf5ba2854326f5cf6559395538f0e59b34806df6308ce71`,
dirty fingerprint `74c48219c586b7511d89fb0e100e492ce7a9c3372a8de1f4ed272fe4c46098f8`,
generator digest `48b69b9594aed8f80d1ff93a0830bf3d2dd3ccfb021296286588ab54e409a8e1`,
and dependency-lock digest `b2b980ef730cb836938d100584729eed8ceace14cdaef068c684dc705733b1cb`.

The deterministic gzip is 36,066,101 bytes with SHA-256
`b753a997d2c22a7abdd016e22b4ae9dd221538c97d386c1f49fb41dde84f0c70`;
its canonical 238,520,172-byte JSON expands to SHA-256
`76f9fef977390ab01487d9a2ba17983e5ae263c07de8a9fe8f0621eb0d31e390`.
The independent 149,278-byte frozen-census authority has SHA-256
`f6b34591fe72db1800c5de383ff5157006fd6d9a32e6faceda08b6b0d5a70826`.
The profile-list symptom resolves at a 10.4930-second median and renders help at
10.2363 seconds while importing 2,120/2,123 modules, constructing 1,767/1,791
models, and touching 223 instrumented storage symbols through 3,595 calls.

## Notes

The first run sampled a mutable shared tree and was stopped. Its incoherent raw
observations were deleted and its remaining note is explicitly non-evidence.

The accepted baseline is immutable pre-optimization evidence. Internal `--check`
passes. Current-source `--check-fresh` intentionally fails after two ledger
evidence nodes were added; the delta is recorded and later post-optimization
capture and gates must dynamically enroll those nodes and every other then-live
node. No claim treats this historical snapshot as current-tree complete.

Independent review initially found four issues: freshness ambiguity, missing
derived-stat recomputation, compacted-away raw memberships, and an unverifiable
rejected-run narrative. All were remediated before re-review.

Re-review found one further exact-set authority gap. The final design publishes
an independent content-addressed frozen census, validates resumed checkpoint
keys as a subset, requires exact equality before publication, and proves coherent
missing-node and invented-node republishing red in adversarial tests.
