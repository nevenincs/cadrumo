---
tags:
  - '#audit'
  - '#aeat-export-fragment-generator-authority'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:551f49aaf0655f8ce83d837cc02a453d658cc8c1a7dedb7216fd0c088694db83'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---
# `aeat-export-fragment-generator-authority` audit: `s133 provenance only republication review`

## Scope

Reviewed the S133 implementation against the accepted narrow-mechanism widening, completeness-closure, and temporal-authority decisions. The review covered the digest-bound CLI contract, exact staged-candidate comparison, transaction-state binding, strict disposition schema, dynamic generated-tree enrollment, source-bound pending pins, the fourteen republished export trees, strict typechecking, and shared-worktree isolation.

## Findings

No HIGH or MEDIUM findings remain.

The new `republish` action requires an existing target and the exact lowercase SHA-256 digest of its current provenance manifest. It renders one explicitly selected revision, compares that exact staged export root with the selected target, admits only semantically reproduced record sets with no member drift, validates the candidate at the existing calculation-grade publication floor, and then delegates replacement to the existing transactional publisher with the previously observed target-state receipt. A stale digest, missing tree, semantic record change, or member change is refused before publication.

Fourteen publication-eligible stale trees were republished through that command. Their generated record spelling and provenance manifests now match the canonical serializer and current authorities. A stable canonical census now classifies the 32 published roots as 19 exact reproductions, 11 provenance-only pending states, and 2 record drifts; the additional renderable Modelo 308 revision is explicitly `never_committed`. The command was not used for either Modelo 347 revision because both retain semantic record drift, or for the eleven trees whose current validation state refuses publication.

Every retained exclusion now names its exact modelo/revision subject, source reference, source digest, reason, and reconsideration condition. The two Modelo 347 rows are loaded from a strict pipeline-owned schema and fail when their source is reissued or their record drift disappears. The eleven reproduction-pending rows are asserted against dynamic enrollment, current source authority, current semantic reproduction, and the exact current check-mode refusal. For Modelo 303, check mode first exposes stale committed output-file digests; an attempted republication independently reaches the deeper undeclared-casilla refusal, and the pins record both layers.

The implementation adds no casts, `Any`, new type ignores, or pyright suppressions. Ruff and basedpyright pass with zero diagnostics. The final combined generated-tree, render-check, CLI, and state suite passes all 104 tests under identical HEAD and measured-diff hashes before and after. Review cleanup removed stale historical comments from the derived pending map and strengthened disposition validation so both the reason and reconsideration condition must contain text.

## Recommendations

Keep the digest argument mandatory for all provenance-only republication; do not add an overwrite or relaxed comparison path. Resolve the remaining subjects only at their named authorities: calculation-grade review for Modelos 185 and 222, cross-revision validation preservation for Modelo 202, casilla export-reference ownership for Modelo 303, and semantic-map repeat and row identity for Modelo 347. Remove each pin when its reconsideration condition becomes true rather than changing the matcher.
