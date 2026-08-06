---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
body_hash: 'sha256:6de0a88ad1fc2fed1b40a2e97e370d10916911eb13a008fb10a70c49026438e1'
step_id: 'S83'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Prove create-time and attach-time evidence validation enforce the same missing and cross-bucket policy

## Scope

- `src/cadrumo/application/ledger/tests/test_actions_create_evidence_validation.py`

## Description

This Step is already satisfied at HEAD; the record documents the landed state verified against HEAD. The predecessor ledger-evidence-atomicity campaign landed the gate in commit `0ea2800b8c`.

- Prove the create door rejects a purchase evidence id absent from the invoice catalogue, and rejects an attachment id absent from the attachment manifest, persisting neither transaction nor event.
- Prove the create door rejects a purchase evidence record owned by another bucket, and rejects an attachment manifest owned by another bucket.
- Mirror all four refusals on the attach door with the same fixtures and the same assertions, so the two doors are proven to enforce one policy rather than two.
- Assert each attach refusal leaves the seeded evidence-free transaction with a null purchase evidence id and an empty attachment tuple, so a rejected attach cannot have half-written.

## Outcome

The create-time and attach-time evidence validators are proven to enforce byte-for-byte the same missing and cross-bucket policy, so neither door is a weaker route into the evidence catalogue. Evidence bytes in these fixtures are written through the content-addressed attachment store over the real encrypted secure-object repository, never a temp file or a path pointer, and cross-bucket refusals are asserted on the bucket-mismatch field rather than on rendered prose.

Gate: `uv run --no-sync pytest -m "" src/cadrumo/application/ledger/tests/test_actions_create_evidence_validation.py` reports 8 passed.

## Notes

Both doors converge on one shared reference validator, so the parity is structural rather than coincidental; the mirrored tests exist to prove the attach door actually reaches that validator instead of relying on the call graph staying wired.
