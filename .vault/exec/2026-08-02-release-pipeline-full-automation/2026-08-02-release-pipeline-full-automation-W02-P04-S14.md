---
tags:
  - '#exec'
  - '#release-pipeline-full-automation'
date: '2026-08-02'
modified: '2026-08-02'
body_schema: 'body-v1'
body_hash: 'sha256:5b92d4b2cd3aff47440aacef6068964f3852cef0d0b9fe30a86db20f6a9bf836'
step_id: 'S14'
related:
  - "[[2026-08-02-release-pipeline-full-automation-plan]]"
---
# Declare the release-candidate record as a strict typed model carrying the cohort id, the version, the source commit, the smoke run id, every acquisition run id, the claimed channel set, the dry_run flag, the soak opened_at, and the computed soak deadline, with the window read from the release checklist soak hours rather than a new literal so one authority still owns the duration, gate: uv run --no-sync pytest dev/release/tests/test_release_candidate.py -q passes with a strict save-load-equality roundtrip populating every defaultable field non-default plus an anti-tautology proof deleting the deadline from the serialized payload and asserting the load refuses

## Scope

- `dev/release/release_candidate.py`
- `dev/release/tests/test_release_candidate.py`

## Description

- Declare `ReleaseCandidate` as a strict, frozen, extra-forbidding model carrying the cohort id, version, source commit, packaging run id, all three acquisition sources, the claimed channel set, the dry-run flag, and both soak instants.
- Add `SoakWindow` and `load_soak_window`, reading the minimum and maximum hours from the shipped release checklist and refusing rather than defaulting when the section is absent.
- Compute and STORE the deadline at seal time through `seal_candidate`, refusing a timezone-naive instant.
- Reserve the `release-candidate-<run_id>` tag namespace with its grammar helpers, deliberately disjoint from the evidence namespace.
- Add `candidate_tags_in` as a pure selector over an already-fetched releases payload.
- Add twelve tests including the strict roundtrip, the anti-tautology proof, the boundary case, and the GC-exemption proof.

## Outcome

`uv run --no-sync pytest dev/release/tests/test_release_candidate.py -q` reports 12 passed. `ruff check dev/release/` and `ty check` are clean.

The record is durable, complete, and refuses to load in a partially-reconstructed state, which is the property the whole machine-held wait rests on.

## Notes

The significant finding is a hazard the Step text did not anticipate, discovered by reading the evidence GC rather than by reasoning about it.

The plan says to publish the candidate through the existing evidence-release draft transport. Reused naively, that means minting the candidate inside the `evidence-<lane>-<run_id>` tag namespace - and `plan_evidence_gc` collects exactly that namespace, keeping only the newest K drafts per lane. A candidate sits sealed for 48 to 72 hours, which is ample time for K later campaigns to push it out of the retention window and delete it. The failure mode is the worse of the two the ADR names: a garbage-collected candidate does not publish late, it never publishes at all, and nothing reports why, because from the promoter's side an absent candidate is indistinguishable from no release having been started.

The candidate namespace is therefore `release-candidate-<run_id>`, which `EVIDENCE_TAG_RE` does not match. That makes the exemption structural rather than configurational - it does not depend on anyone setting a retention count correctly or remembering to pass a protected tag. This also matches the Step text's own wording, which asked for "a release-candidate tag", so the mechanism is reused while the namespace is not.

Measured, not assumed: `plan_evidence_gc` was run against a payload holding two evidence drafts and one candidate at `keep_per_lane=1`. It deleted the older evidence draft and did not return the candidate in EITHER bucket. The test pins that with a control asserting the GC really was deleting in that scenario, so the candidate's absence reads as exemption rather than an inert planner. If anyone later enrolls candidates as an `EvidenceLane`, that test reds instead of in-flight soak state quietly becoming collectable.

Two smaller decisions worth recording. The deadline is STORED rather than recomputed at read time: a promoter that recomputed it would silently re-date every in-flight candidate the moment the checklist was edited, so a documentation change could publish a candidate early or extend one already served. And `load_soak_window` refuses when the soak section is missing rather than falling back to a literal, because a fallback would be a second authority over the duration - the exact thing the "read it from the checklist" requirement exists to prevent.
