---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:36928e0b5d33cf720d8ae0c7877e43203cfa2c8f4c49bd99b977179d6498f905'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---
# `tui-architecture` audit: `s123 dependency receipt review`

## Scope

Independent review of S123 at HEAD `a096a2685343e5bc38f4ec54114fcbb0724af143`, including implementation `0c0b307974` and format-only follow-up `a096a26853`, against accepted TUI Architecture ADR D8, the canonical plan, and the S123 Step Record. Vaultspec RAG semantic discovery preceded exact source, commit, and AST searches.

## Findings

### LOW â€” Full-project type-diagnostic count is not attributable to the S123 receipt module

The reported eleven type diagnostics were assessed separately from the S123 receipt surface. Focused `basedpyright src/cadrumo/application/operations/tests/test_public_operation_dependency_receipt.py` reports zero errors/warnings, as does focused Ruff. The broad type command did not complete within the terminalâ€™s 30-second result window, so this review cannot assign the eleven project-wide diagnostics to a precise source set. They are not reproduced by the S123 module and do not evidence an S123 receipt/authority defect. Resolve and inventory them at the next broad quality-gate run.

No MEDIUM, HIGH, or CRITICAL finding.

## Recommendations

- Inventory the broader type-check diagnostics at the next full quality gate; the focused S123 module is clean and no receipt-authority remediation is required for closure.

## Evidence and disposition

PASS â€” S123 may close.

- `TuiOperationObservationDependencyReceiptV1` is strict, frozen, closed (`extra='forbid'`), validates sorted/unique inventories, reproduces derived definition/schema/capability/export manifests, and is round-tripped through strict JSON in the resident-service test.
- The sole validator recomputes the live production composition contract set, source-tree digest, accepted governing and rejected staging ADR body hashes/producing commits/ancestry, required proof source digests and function names, public exports, and exact AST authority plus constructor ownership. It rejects stale commit, digest/provenance drift, missing proof evidence, duplicate/displaced authority, and non-parity production DI.
- The required proof inventory names real behavior tests for atomic interleaving, current-only deletion, digest refusal, production DI, progress/replay, restart refresh, REVIEW non-authority, sentinel non-retention, and strict anchored materialization.
- The semantic census invokes the resident Vaultspec RAG service through `uvx vaultspec-rag search ... --port 8766`, uses a fixed code-only query and operations include-path, fails on command/service failure or empty output, fingerprints tool/query/schema/result/source tree, and replays the query during validation. There is no supplied/fabricated fallback. The live query returned only allowed canonical operation paths; adversarial tests reject a missing registry path and an added competing path.
- The receipt test module does not write `_RECEIPT_PATH` or any reference artifact. S124 remains the sole clean-commit C0 artifact producer; S123â€™s in-memory materializer exists only to exercise the validator with `require_clean_tree=False` in shared-worktree tests.
- Focused default pytest selection deselects this integration/resident suite, as expected. The marked resident recipe began successfully but exceeded this terminal bridgeâ€™s 30-second response window after three passing progress markers; no failure output was observed. The Step Recordâ€™s canonical serial run records 5 passed, 1 deselected.
