---
tags:
  - '#audit'
  - '#cli-authority-verb-conformance'
date: '2026-07-16'
modified: '2026-07-16'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
  - "[[2026-07-15-cli-authority-verb-conformance-W02-P06-S43]]"
---
# `cli-authority-verb-conformance` audit: `S43 auth logout preservation review`

## Scope

This audit independently reviews commit `bee34cf878` and plan Step `W02.P06.S43`. It checks them against the accepted architecture decision record (ADR), research, authentication reference, S37 records, S43 record, and current HEAD `2ee3ae2625`.

The review covers:

- the exact four committed paths;
- the public authentication facade;
- certificate-source registration and selection;
- secure-storage secret custody;
- encrypted persisted-session storage;
- target-scoped logout and test mutation sensitivity;
- import direction and duplicate test authority;
- plan closure, execution attribution, and index enrollment; and
- later-HEAD contamination.

## Findings

### s43-review | low | No actionable findings

The review found no critical, blocker, high, medium, or low implementation defect. This heading is a clean-review sentinel required by the audit format, not a low-severity defect.

The new test invokes public application behavior for certificate registration, selection, secret mutation, secret resolution, session loading, and logout. It uses the production encrypted profile repository, secure-object browser-session store, and sole secure-storage certificate-secret backend. The private session adapter seeds and inspects the production record because S43 tests logout rather than login acquisition.

The saved session is deletion-sensitive and genuinely loadable. Before logout, the production loader decrypts and validates the record into `PersistedAuthSession`. It also confirms the provider and tax identification number (NIF). After logout, the same logical key must be absent and `removed_sessions` must equal one. A missing save, malformed metadata, wrong provider stem, wrong bucket route, or skipped deletion makes those assertions fail.

The preservation assertions are mutation-sensitive. Exact equality covers provider plus `configured_at`, selected certificate path, active source name, and the complete immutable `CertificateSourceRecord`. A separate assertion covers the decrypted secure-storage secret. Clearing, replacing, or routing logout through reset behavior changes at least one asserted value. Deleting the secret also fails the post-logout resolver and value checks.

The commit adds no business-logic mirror, fake, mock, stub, patch, monkeypatch, skip, or xfail. Its new application imports use the public `application.auth` facade. Existing same-package private imports remain test setup or inspection seams and add no production dependencies. Exact and semantic searches found no second test that owns the complete S43 preservation contract.

The delivery records match the commit and execution evidence. Commit `bee34cf878` changes exactly the S43 test, S43 execution record, S43 plan checkbox, and generated feature index. The execution record matches the observed gates and states that production code was unchanged. The index enrolls the record once. Later commits do not modify those four paths, so current HEAD has neither superseded nor contaminated the conclusion.

## Recommendations

Accept `W02.P06.S43` as delivered. Retain this test in the final integrated authentication and feature conformance lanes. No production, test, plan, execution-record, or index revision is required from this review.

## RAG and gate evidence

Vaultspec retrieval-augmented generation (RAG) code searches resolved `logout_operator_auth`, the S43 test, the canonical session loader, and certificate-source operator services. They also resolved the sole secure-storage secret backend and public auth facade. Directed ADR search resolved the accepted rule that logout removes sessions while preserving provider and certificate-source configuration. Vault search resolved the S43 plan row, reference verification map, S43 execution record, S37 remediation record, and intentional logout/reset non-consolidation.

Exact `rg`, current-file reads, `git show`, `git log`, and `git diff bee34cf878..HEAD` confirmed every semantic result. The focused checks produced:

- Exact S43 node: 1 passed.
- Complete designated module: 13 passed.
- Focused Ruff: passed.
- Uncached import-linter: 3,431 files, 16,260 dependencies, five contracts kept, zero broken.
- Commit whitespace check: passed.
- Commit path inventory: exactly four paths.
- Current-HEAD contamination check: no changes to the four S43 paths after `bee34cf878`.

## Verdict

**PASS.** Step `W02.P06.S43` directly proves that certificate logout removes a real persisted session while preserving provider configuration and certificate custody. No blocker or high finding remains, and no review-driven code or record correction is needed.
