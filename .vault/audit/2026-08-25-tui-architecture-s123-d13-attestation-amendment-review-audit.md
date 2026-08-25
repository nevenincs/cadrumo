---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:f43a2d4e36cad42e1d646814a9949f83c7ce2e7bef4a1bc93b79204cb752f80b'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---
# `tui-architecture` audit: `s123 d13 attestation amendment review`

## Scope

Independent review of the D13/S123 attestation implementation at exact commit `87e87a3eea` against the amended accepted TUI Architecture ADR. Vaultspec RAG semantic discovery preceded exact commit-scoped searches. The review covered receipt schema current-only behavior, A/B capture and validation, Git-object source digests, committed-artifact bytes, S123 in-memory isolation, live DI/proof/RAG/exact censuses, and static quality.

## Findings

### LOW - Reported eleven type diagnostics are not reproduced by the S123 attestation surface

Focused basedpyright on `test_public_operation_dependency_receipt.py` reports `0 errors, 0 warnings`; focused Ruff also passes. The reported eleven diagnostics therefore are not attributable to this implementation surface. They should be inventoried by the next full-project type gate, but do not constitute an S123 D13 attestation defect.

No MEDIUM, HIGH, or CRITICAL finding.

## Recommendations

Retain the exact A/B adversarial tests as the required durable-attestation gate. Run a full-project type inventory before a broader release/closure gate to classify the eleven diagnostics by owner.

## Disposition

PASS - S123's D13 amendment implementation is conformant and may proceed. `producing_commit` remains only on ADR-document provenance, plus the negative legacy-model witness; the receipt schema has only `implementation_commit` and rejects the legacy field.

Evidence:

- Clean capture records A and calculates the covered source digest from `git show A:<path>` bytes.
- Durable validation requires a clean current worktree B, reads the on-disk artifact, requires byte equality with `git show B:<receipt path>`, parses those committed bytes, and never stores B in the receipt.
- It rejects non-ancestor A, source drift at B, byte mismatch, uncommitted artifact, and staged artifact. Six non-resident durable-attestation tests passed.
- The in-memory helper is private, requires its receipt name the current implementation commit, and cannot call the durable artifact validator or open C0.
- Live production DI, required proof fingerprints, exact AST authority/constructor census, and resident Vaultspec RAG replay remain in `_validate_receipt_evidence`. Three resident fixed-point/semantic-mutation/closed-model tests passed.
