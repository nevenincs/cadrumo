---
tags:
  - '#exec'
  - '#canonical-release-pipeline'
date: '2026-07-27'
modified: '2026-07-27'
body_hash: 'sha256:61dcd0851c9d50c63edd1b7f14c6e91676a1dcbce7c3944e1d22b9d0e85262dd'
step_id: 'S11'
related:
  - "[[2026-07-27-canonical-release-pipeline-plan]]"
---

# Extend the doc-privacy gate with the cross-project identifier class, shape rules for 32-hex infrastructure ids, cloud role-identifier shapes, and owner-slash-repo slugs outside the declared reference set, plus fragment tokens for known private names, preserving the legal-attribution exemption untouched, gate: uv run --no-sync pytest dev/quality/tests/test_doc_privacy.py -q passes including a planted-violation self-test per new shape class that reds when its refusal is removed

## Scope

- `dev/quality/tests/test_doc_privacy.py`

## Description

- Measure the false-positive rate of candidate identifier shapes against the tree.
- Add the cross-project identifier class, split between shapes and fixed tokens.
- State in the module what the detector cannot catch.

## Outcome

Landed under the commit subject `test(privacy): ban cross-project identifiers,
and scan the untracked files too`.

The measurement changed the design. A bare thirty-two-character hexadecimal
identifier was the obvious shape for a zone or account id, and it matches
eighty-two legitimate occurrences in this tree: index job ids, document internal
ids, library digests. Banning it would have produced noise, and noise gets
silenced rather than corrected.

So the class is split honestly. Shapes are used where a shape is genuinely
distinctive, which for a cloud role identifier means zero false positives. Known
values whose shape cannot be told apart from ordinary data are banned as fixed
tokens instead, assembled from fragments exactly as the existing tokens are.

What no detector here can catch is stated in the module rather than implied: an
identifier belonging to a sibling product whose value nobody recorded. The
detector narrows the window; only the discipline of naming account dependencies
abstractly closes it.

Gate: the privacy suite passes at nine tests, including an emptied-set guard, so
disarming the class cannot leave the gate green.

## Notes

The gate flagged this change's own test on the first run, which is the
self-coverage property working rather than a defect. A literal identifier
planted in a tracked test file is a real leak, so the planted value is now
fragment-assembled like every other.
