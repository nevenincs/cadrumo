---
tags:
  - '#audit'
  - '#profile-registration-password-policy'
date: '2026-08-22'
modified: '2026-08-22'
body_schema: 'body-v1'
body_hash: 'sha256:9851bafbf3d7c8d9b743777d810f5db9ae565e0e208859ec926e32a7f09dd3b9'
related:
  - "[[2026-08-22-profile-registration-password-policy-canonical-credential-capability-adr]]"
  - "[[2026-08-22-profile-registration-password-policy-plan]]"
---

# `profile-registration-password-policy` audit: `fresh-context honesty`

## Scope

Fresh-context close audit of the accepted canonical-credential ADR, research,
incident reference, live L3 plan, every S02-S14 execution record, formal review,
current HEAD and overlapping worktree changes. Each section began with semantic CODE
and ADR discovery through `vaultspec-rag`, then exact `rg` confirmation. No prior
completion statement was accepted as evidence.

The audit derived every concrete acceptance criterion and checked it against current
production code, real runtime boundaries, complete storage-tree snapshots, focused
tests, locale/error artefacts, obsolete-symbol searches, generated documentation
reports, and the honest S13 repository-gate transcript. No production file was edited.

## Evidence matrix

| Requirement | Current evidence | Result |
| --- | --- | --- |
| One core password authority: 15-256 Unicode scalars, at most 1,024 strict UTF-8 bytes, surrogates refused, exact sequence, typed safe facts, advisory-only strength | `src/cadrumo/core/_credentials.py`; fresh unit lane; boundary, result-shape, immutability and composed/decomposed tests in `src/cadrumo/core/tests/test_credentials.py` | Proven |
| Custody repeats the canonical assessment without owning policy limits or operator prose | `src/cadrumo/adapters/persistence/storage/custody/_records.py`; focused record error-bite and exact-unlock tests; obsolete custody symbols absent except negative assertions | Proven |
| Registration and rotation refuse before KDF, locks, identity randomness, staging, journaling, re-heading or publication and leave all storage state unchanged | `src/cadrumo/application/user_profile/_registration.py`, `_passphrase_rotation.py`; collaborator bite tests and exact path/kind/byte snapshots in their integration suites | Proven |
| Malformed and incorrect existing proofs are publicly indistinguishable while integrity, corruption, transaction, resource, supervision and keyring failures remain distinct | `ProfileAuthenticationRefusedError`; the five-operation mapping matrix; real login, password restore, recovery export/restore and rotation tests | Proven |
| Recovery secrets use a separate exact parent/worker codec, preserve mnemonic/envelope semantics and never call profile-password assessment | `_recovery_secret_codec.py`, supervised worker paths, recovery roundtrips and negative source scan; wrong and surrogate recovery proofs have the same localized refusal and identical before/after storage snapshots | Proven |
| Direct application, live Textual feedback/submission and scripted CLI agree at 14/15/256/257 scalars, 1,024/1,025 bytes and surrogate boundaries | Fresh 67-test unit lane and 103-test real integration lane; live Pilot matrix includes the original Spanish fourteen-scalar crash and the upper/byte/surrogate cases | Proven |
| Accepted composed/decomposed credentials remain byte-exact and unlock only with the submitted sequence | Core, custody, registration and rotation exact-Unicode tests; real persisted-envelope unlock assertions | Proven |
| TUI/CLI output is one-language, localized and secret-safe, with no custody prose, translation key, traceback, INTERNAL guidance or submitted secret | Four-locale real CLI envelope matrix, locale-parity test, live TUI pinned-status assertions, malformed/mismatch/oversized stdin no-echo tests | Proven |
| Rotation preserves DEK epoch, committed records, password generation lineage, recovery enrolment and intended session revocation | Real rotation application tests and seven capsule-envelope rotation tests in the fresh 57-test storage/proof slice | Proven |
| Superseded policy, duplicate validators, aliases, shims, compatibility paths, stale credential locale leaves and recovery/password coupling are absent | Exact repository searches; production recovery glob returns no canonical-password dependency; locale scaffold/audit contains zero credential hits | Proven |
| Scope and gate claims are honest | Feature Ruff passes; feature Vault behavioral checks pass; current diff after S14 contains no credential file; S13 full-tree reds are reproduced/classified below and are not presented as green | Proven with baseline caveats |

## Findings

No open LOW, MEDIUM, HIGH, or CRITICAL feature finding was found.

The tree-wide caveats remain real and are not narrowed away. Current import-linter
keeps nine contracts and breaks the longstanding layered-architecture contract. The
locale scaffold and audit are red with 2,236 lines of unrelated aggregation and Modelo
036/220/390 drift, but contain zero credential-key hits. API reference checks remain red
with four missing, two orphan and four stale stubs, all the same unrelated calculation,
operator-surface, registry and source-connectivity set recorded by S13. The prior
full-corpus and documentation failures and interrupted `just docs-check 4` remain
unproven green.

These repository baseline reds do not block this feature's objective under the
path-scoped feature-surface rule: fresh feature production lint, both complete selected
credential lanes, focused real custody/proof tests and feature-tagged Vault behavioral
checks pass, and none of the current global diagnostics names a credential locale,
feature-owned generated stub, or post-S14 credential change. This conclusion does not
claim the repository as a whole is releasable.

## Recommendations

Close W04.P11.S15 with its execution record and evidence commit. Keep W04.P11.S16
separate for final lifecycle/index reconciliation. Preserve the S13 full-tree caveats
in final campaign reporting until the independently owned locale, API, documentation,
import and harness baselines are green.

Do not broaden this campaign into recovery-based password reset, compromised-password
screening or Unicode normalization. The accepted ADR explicitly defers those decisions.
