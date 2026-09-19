---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:92c8620c2e37250ffbcc7cea1373d7b17f2eeb9296a120032cadd45ee2aad803'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---
# `tui-architecture` audit: `s124 receipt self-reference feasibility`

## Scope

Architecture feasibility review of S124 against accepted TUI Architecture ADR D8/D13, the S123 live-tree validator, the canonical plan, and existing receipt conventions. Vaultspec RAG was attempted first but correctly refused because the local client (`0.4.2`) and resident service (`0.4.1`) differ; exact source and vault searches supplied the evidence instead. No implementation was changed.

## Findings

### HIGH - S124 is mathematically infeasible under the current self-referential `producing_commit` rule

S123 builds a receipt with `producing_commit = git rev-parse HEAD` and its validator requires both a clean worktree and `receipt.producing_commit == current HEAD`. Let A be the clean implementation commit. Writing the receipt and committing it creates B, so the durable artifact at B still names A and is rejected at B. Regenerating it with B changes the commit content and therefore produces a different commit hash, not B. No finite amend/recommit sequence can satisfy this fixed point.

The source-tree digest intentionally covers tracked Cadrumo source, not `.vault/reference`, so the artifact can be committed without source drift. The blocker is solely the conflation of implementation provenance and artifact-attestation commit identity.

## Recommendations

Amend the accepted TUI ADR before implementation; this is a decision-level refinement. Keep exact current-HEAD and source-digest authority, but split the facts without a shim, alias, or re-export bridge:

1. Replace receipt field `producing_commit` with current-only `implementation_commit`. It is the clean commit A from which all C0 source evidence was captured.
2. S124 writes the reference artifact from clean A, then commits it as B without changing the covered source set.
3. The sole validator accepts the loaded artifact only at clean current HEAD B. It must require:
   - `implementation_commit` is an ancestor of B;
   - the source-tree digest recomputed at B equals the receipt digest (therefore the covered source tree did not change from the evidence); and
   - the artifact bytes being parsed equal `git show B:.vault/reference/2026-08-24-tui-operation-observation-dependency-receipt.md`, proving the receipt is committed at B rather than merely staged or copied.
4. Keep all existing live checks at B: production DI parity, public exports/contracts, proof digests, exact AST census, Vaultspec RAG replay, and ADR accepted/rejected provenance. These continue to fail any relevant drift.
5. Derive the artifact attestation commit from the validator target B; do not store `artifact_commit` inside the artifact, which recreates the same hash fixed point. The consumer/CI invocation is the attestation that B is current HEAD and clean.

Do not exclude staged files from source authority. The covered-source digest already intentionally excludes the vault artifact; explicit committed-byte verification is the narrower proof. Do not preserve `producing_commit` as an alias or accept either field: pre-release current-only policy requires deleting the old field and updating every in-tree producer, parser, test, plan/record statement, and reference schema together.

### Required changes after decision approval

- Amend ADR D13's clean-commit receipt language to distinguish implementation evidence A from artifact attestation target B.
- Update `TuiOperationObservationDependencyReceiptV1`, its builder, and sole validator in `test_public_operation_dependency_receipt.py`; add adversarial tests for non-ancestor implementation commit, source drift between A/B, uncommitted/staged artifact, and artifact-byte mismatch.
- Update S123 record wording and S124 plan/record procedure to the two-commit sequence. S124 remains the only durable artifact producer; S123 may only materialize in-memory test evidence.
- Update every downstream receipt consumer to validate the predecessor artifact at its committed target, then bind the predecessor's `implementation_commit`, source digest, and committed-artifact digest as separate facts.

## Disposition

Do not attempt S124 under the current contract. This is an architectural blocker, not an implementation defect that can be patched locally. An ADR amendment requires explicit approval before it is persisted; this audit supplies the recommendation.
