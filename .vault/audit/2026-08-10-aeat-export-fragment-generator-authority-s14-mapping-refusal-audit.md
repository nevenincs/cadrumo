---
tags:
  - '#audit'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:0b70cc9723ff58251514f07eadbc5700a7e84efc73cfe2ea036154fddbc26927'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---

# `aeat-export-fragment-generator-authority` audit: `s14 mapping refusal`

## Scope

Independently reviewed `W03.P05.S14` against the accepted generator-authority ADR: the changed adversarial cases in `dev/registry/tests/test_semantic_map_join.py`, plus the complete `dev/registry/_semantic_map_validation.py` and `dev/registry/_semantic_map_join.py` authority boundaries. The audit checked missing, duplicate, ambiguous, near-match, and anomaly-exception cases for whole-design refusal; exact-anchor-only joining; prohibited legacy, single-file, direct-revision, and fuzzy admission surfaces; and the project prohibition on test doubles and mirrored business logic.

## Findings

No findings. The join validates the complete semantic-map and parser bijections before building lookup dictionaries or any joined design. The changed tests exercise absent coverage, duplicate map anchors, duplicate parser anchors, a cell-only near match, and an otherwise valid anomaly exception that cannot waive missing coverage. The module-level structural red guard rejects the identified legacy, loader-compatibility, and fuzzy-matching terms. Focused execution passed: `uv run --no-sync pytest dev/registry/tests/test_semantic_map_join.py -q` reported 9 passed.

## Recommendations

No remediation is required for `W03.P05.S14`. Retain the structural red guard as later generator work lands; the plan's dedicated hard-cutover steps remain responsible for deletion of repository-wide compatibility paths.
