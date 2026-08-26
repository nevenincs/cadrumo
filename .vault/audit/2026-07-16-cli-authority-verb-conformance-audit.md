---
tags:
  - '#audit'
  - '#cli-authority-verb-conformance'
date: '2026-07-16'
modified: '2026-08-26'
body_hash: 'sha256:d1c1811b996cd9b0b45003c11a49eaa84d6dedbb6cfdc9899acb8a64bce3325f'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
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

## S48 formal review

### Scope

This section independently reviews commit `9dc920909d` and plan Step
`W02.P07.S48` against the accepted certificate-custody decision, the amended
plan and reference blueprint, the S48 execution record, and current HEAD
`dc7bdccaf0`.

The review covers:

- named-source password resolution and explicit absent-value transport;
- the absence of global-password fallback in the registry-wide certificate
  check;
- fail-closed behavior for missing and unreadable secure-storage secrets;
- preservation of the legacy global path, password, and friendly name when no
  named source is selected;
- duplicate resolver, backend, and mutation-writer candidates;
- real-behavior test quality and mutation sensitivity;
- application import direction and the uncached import graph;
- exact commit-path attribution despite the intervening reset commit; and
- later-HEAD contamination and active shared-worktree changes.

### Severity summary

| Severity | Count | Disposition |
|---|---:|---|
| Critical | 0 | None found |
| High | 0 | None found |
| Medium | 0 | None found |
| Low | 0 | None found |

### s48-review | low | No actionable findings

The review found no critical, high, medium, or low implementation defect. This
heading is the audit template's clean-review sentinel, not a low-severity
finding.

`check_operator_certificate_sources` now copies caller-supplied settings and
overrides only `cadrumo_certificate_password_secret`, including an explicit
`None`. Every registered named source therefore reaches the production PKCS#12
probe with either its selected-profile secure-storage secret or no password.
Neither an absent record nor a real malformed secret-store index can expose the
global single-certificate password to that named-source check.

`resolve_active_certificate_credentials` preserves the distinct legacy
contract. When no named source is selected, it returns the global certificate
path, password, and friendly name unchanged. When a named source is selected,
it resolves that source's password through the same private fail-closed read
policy used by the registry check. Storage validation and operating-system
read failures become explicit absence rather than fallback.

The tests are mutation-sensitive and use real behavior. They generate genuine
encrypted PKCS#12 bundles, bind secrets through the public application
operation into a real encrypted `SecretStore`, and invoke the production probe.
The adverse bundle is encrypted with the exact global password, so restoring
the removed fallback changes `corrupt` to `ok` and fails the test. The
storage-error proof corrupts the real non-secret index after a successful
secret write; falling back after that error also changes `corrupt` to `ok`.
The legacy proof registers but does not select a named source and compares the
exact global credential fields. No fake, mock, stub, patch, monkeypatch, skip,
xfail, or mirrored business logic appears.

Semantic and exact searches found one public raw named-secret read seam,
`resolve_certificate_source_secret`; one private read-error policy,
`_resolve_named_certificate_source_secret`; one backend implementation,
`SecureStorageCertificateSecretBackend`; and one ordinary resumable
certificate-secret set/remove authority. The direct secret removal inside
`reset_operator_auth` is a target-scoped, durable destructive composition with
different constraints and is not substitutable for ordinary secret mutation.
No second named-source global-password fallback or parallel ordinary writer
was introduced.

Commit attribution is clean. The S48 commit's actual parent is `60135859e2`,
which contains peer-owned reset work landed after the requested comparison
base `145578fead`. The S48 commit itself changes exactly five paths: its
application module, designated test module, execution record, plan checkbox,
and generated feature index. Current HEAD does not modify those five paths
after S48. Unrelated active worktree changes remain outside the review and
commit.

### Recommendations

Accept `W02.P07.S48` as delivered. Retain the missing-secret,
secure-storage-corruption, and legacy-global proofs in the integrated
certificate lane. Continue with the already separate S49 and S50 work to route
omitted-provider and adapter authentication through the typed credential;
those planned gaps are not regressions or incomplete work within the amended
S48 boundary.

### RAG and gate evidence

Directed Vaultspec-RAG code search resolved the active credential resolver,
registry-wide check, sole secure-storage backend, shared fail-closed helper,
production probe, adverse tests, and remaining S49 operator bridge. Directed
ADR search resolved the accepted rule that selected named credentials use
profile secure storage and fail closed without global fallback. Exact `rg`,
full-file reads, `git show`, ancestry inspection, and current-HEAD diffs
confirmed every semantic candidate and the non-substitutability of auth reset's
destructive cleanup.

Independent gates produced:

- Exact adverse and legacy nodes: 3 passed.
- Complete certificate-source check module: 13 passed.
- Focused Ruff: passed.
- Commit whitespace check: passed.
- Commit path inventory: exactly five paths.
- Current-HEAD contamination check: no later changes to the five S48 paths.
- Uncached import-linter: 3,433 files, 16,280 dependencies, five contracts
  kept, zero broken.
- Feature-scoped Vault check: clean.

### Verdict

**PASS.** Step `W02.P07.S48` removes the named-source global-password fallback,
fails closed on missing or unreadable secure-storage credentials, preserves the
unselected legacy global contract, and introduces no duplicate resolver,
ordinary writer, prohibited test double, import-boundary violation, or
delivery contamination.
