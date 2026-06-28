---
tags:
  - '#audit'
  - '#live-iva-compensation-wallet'
date: '2026-05-26'
modified: '2026-05-26'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
  - '[[2026-05-26-live-iva-compensation-wallet-w09-p01-s01-exec]]'
  - '[[2026-05-26-live-iva-compensation-wallet-w09-p01-s03-exec]]'
  - '[[2026-05-26-securestorage-repair-policy-adr-adjudication-research]]'
  - '[[2026-05-22-secure-storage-production-hardening-architecture-adr]]'
  - '[[2026-05-22-live-iva-compensation-wallet-profile-bucket-repository-binding-reconciliation-adr]]'
  - '[[2026-05-13-cli-workflow-redesign-config-repair-shape-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-bucket-adr]]'
  - '[[2026-05-14-secure-backend-passkey-custody-adr]]'
  - '[[2026-05-06-secure-persistence-enforcement-adr]]'
---

# `live-iva-compensation-wallet` SecureStorage Repair Policy ADR Coverage Audit

SECURESTORAGE-ADR-001 | MEDIUM | Existing policy authority was real but under-linked from the wallet plan

An accepted core ADR exists for the broader policy mechanisms:
`2026-05-22-secure-storage-production-hardening-architecture-adr`. It is not
wallet-specific. It defines `StorageRuntime` as the mandatory production storage
boundary, requires namespace registry entries to include repair policy, recovery
policy, remote mirror policy, retention, schema, and partial-read policy, and
requires filing-grade outputs to block when required storage namespaces are
degraded.

The recent wallet plan already linked the wallet-specific profile/bucket/
repository/binding reconciliation ADR, but it did not directly link the broader
SecureStorage production hardening ADR, config repair shape ADR, bucket ADR,
custody ADR, or secure persistence enforcement ADR. That made the active repair
plan look more wallet-local and ad hoc than the architecture actually is.

Mitigation applied: the current wallet plan frontmatter now links the broad
SecureStorage architecture ADR/research plus the config repair, bucket, custody,
and secure persistence ADRs.

SECURESTORAGE-ADR-002 | HIGH | Cross-domain execution scope was not explicit enough in the current wallet plan

The accepted ADR chain covers the architectural direction, but the wallet plan's
repair phases focused primarily on unreadable secure-object attribution and the
IVA wallet/IVA calculation confidence path. That was not explicit enough for
operator-facing repair and recovery surfaces that touch profile buckets,
transactions, ledgers, invoices, imports, exports, Modelo work units, filing
drafts, submitted declarations, justificantes, wallet observations, auth
sessions, bucket events, custody, and remote mirror state.

Mitigation applied: the current wallet plan now includes Wave W09, `SecureStorage
repair and recovery policy governance`, with phases for ADR coverage closure,
CLI repair/recovery convergence, backend repository policy enforcement, custody
and bucket import/export/remote mirror recovery, and cross-domain persona
testimonials.

SECURESTORAGE-ADR-003 | OPEN | A focused ADR amendment may still be needed after the W09 coverage matrix

The current evidence supports this conclusion: the broad SecureStorage ADR is
the governing core decision, not an IVA-wallet-only implementation note. However,
the exact repair/recovery policy matrix for every namespace and command surface
is still work-in-progress. W09.P01.S02 now explicitly decides whether the
existing accepted ADR fully covers the mechanism or whether a focused ADR
amendment must be drafted and approved.

Until W09.P01 completes, repair/recovery work should be treated as a
cross-domain SecureStorage governance feature with wallet-specific slices, not
as an ad hoc wallet implementation.

SECURESTORAGE-W09-P01-S01 | PASS | ADR coverage matrix produced for repair and recovery surfaces

The coverage matrix below records the current governance state for the
cross-domain repair and recovery surface. It distinguishes accepted authority,
current implementation confidence, and the next tracked plan item. The matrix is
intentionally broader than IVA wallet work.

| Surface | Governing ADR coverage | Current policy confidence | Open execution hook |
| --- | --- | --- | --- |
| `aeat config repair` composite diagnostics | Covered by config repair shape ADR, SecureStorage production hardening ADR, secure persistence enforcement ADR, and profile/bucket terminology ADR | Medium. Command family exists and recent repair-plan work is preserve-first, but older quarantine/reset wording predates the full namespace policy map | W09.P02.S01, W09.P02.S02, W09.P02.S04 |
| `aeat config repair integrity attribution` | Covered by SecureStorage production hardening ADR plus profile/bucket terminology ADR | High for privacy and non-mutation. Current tests cover metadata-only unreadable-row attribution | W09.P01.S03 policy map and W09.P03.S02 degraded-read enforcement |
| `aeat config repair plan` | Covered by SecureStorage production hardening ADR and W05 preserve-first implementation records | High for non-mutation, medium for cross-domain completeness until namespace policy map is centralized | W09.P01.S03, W09.P02.S03 |
| Secure-object quarantine | Config repair shape ADR originally allowed guarded quarantine; W05/P02 narrowed it with preserve-first and protected namespace prohibitions | Medium. Critical receipt and filing-history namespaces are blocked, but global quarantine policy still needs central registry-backed coverage | W09.P01.S03, W09.P03.S03 |
| Workflow-state reset | Covered by config repair shape ADR | Medium. It is a narrow single-row recovery path, but must be reconciled with StorageRuntime/custody readiness and bucket event policy | W09.P02.S01, W09.P03.S01 |
| Profile lifecycle and profile switching | Covered by profile lifecycle, profile UUID identity, profile aggregate, state projection, and profile/bucket terminology ADRs | Medium-high. Vocabulary is accepted; adverse route/session behavior still needs enforcement tests | W06.P01, W09.P03.S04 |
| Bucket browse/search/export/import/rename/delete | Covered by bucket ADR and SecureStorage production hardening ADR | Medium-low. Policy surface is accepted, but command-level privacy, non-mutation, checksum, revision, and import/restore gates need re-audit | W09.P02.S01, W09.P02.S03, W09.P04.S02 |
| Passphrase, recovery code, keychain custody, lock/unlock | Covered by secure backend passkey custody ADR and SecureStorage production hardening ADR | Medium. ADR is strong; current CLI/runtime conformance must be verified under adverse conditions | W09.P04.S01 |
| Secure persistence boundary | Covered by secure persistence enforcement ADR and SecureStorage production hardening ADR | Medium. Encrypted SQL secure objects are accepted, but direct repository construction and root fallback routing remain explicit enforcement targets | W09.P03.S01, W09.P03.S02 |
| Ledger transactions and ledger ratios | Covered by bucket ADR, secure persistence enforcement ADR, profile/bucket terminology ADR, and calculation confidence plan | Medium-low. Storage ownership is known, but repair/recovery policy and calculation-confidence impact need centralized namespace map | W05.P03, W09.P01.S03, W09.P03.S03 |
| Invoices, payable/collectible/purchase invoice evidence | Covered by bucket ADR, secure persistence enforcement ADR, and source-kind ADR chain | Medium-low. Domain is named in plan, but import/export and repair policy must be centralized and tested | W09.P01.S03, W09.P02.S03, W09.P03.S03 |
| Import surfaces | Partially covered by bucket ADR and domain-specific CLI/source-kind ADRs | Low. Needs explicit policy for source validation, quarantine avoidance, overwrite/refusal semantics, and recovery evidence | W09.P02.S01, W09.P02.S02 |
| Export surfaces | Partially covered by bucket ADR, Modelo/export ADR chain, and SecureStorage production hardening ADR | Medium-low. User-directed export is allowed as a boundary crossing, but redaction, degraded-evidence refusal, and provenance policy need unified tests | W07.P03, W09.P02.S01, W09.P02.S03 |
| Modelo work units, calculation revisions, verification reports | Covered by secure persistence enforcement ADR, calculation source mesh ADR chain, and profile/bucket terminology ADR | Medium. Calculation state is acknowledged as bucket evidence; degraded storage must be connected to calculation confidence | W05.P03, W06.P03, W09.P03.S03 |
| Filing drafts and local filing workflow state | Covered by bucket ADR, secure persistence enforcement ADR, config repair shape ADR, and SecureStorage production hardening ADR | Medium-low. Filing state is sensitive and bucket-owned; repair policy must preserve/export before destructive action | W09.P01.S03, W09.P03.S03 |
| Submitted declarations and justificantes | Covered by secure backend custody ADR legal framing, config repair shape ADR, and W05 protected namespace policy | High for no-quarantine policy after W05.P02.S04, medium for complete recovery policy | W09.P03.S03, W09.P04.S04 |
| Filed-history observations and artefacts | Covered by wallet/profile terminology ADR and SecureStorage production hardening ADR | Medium-high for no-quarantine policy, medium for read-only redownload and recovery evidence flow | W05.P03, W09.P03.S03 |
| IVA wallet observations | Covered by live wallet ADR, profile/bucket terminology ADR, and SecureStorage production hardening ADR | High for no live submission and preserve-first repair, medium for cross-domain namespace map | W05.P03, W09.P01.S03 |
| Wallet reconciliation decisions | Covered by live wallet ADR, IVA compensation chain ADR, and profile/bucket terminology ADR | Medium-high. Authority separation is accepted; repair/recovery policy must be mapped with calculation confidence | W05.P03.S04, W09.P03.S03 |
| Auth sessions and diagnostics | Covered by config auth shape ADR chain, secure persistence enforcement ADR, and SecureStorage production hardening ADR | Medium. Recent privacy hardening exists, but recovery policy must distinguish operational rebuild from tax evidence | W09.P02.S01, W09.P03.S03 |
| Bucket event history | Covered by bucket event history ADR, bucket ADR, and SecureStorage production hardening ADR | Medium-low. Events are named, but repair/recovery policy for unreadable or partial event history needs namespace-map coverage | W09.P01.S03, W09.P03.S03 |
| Remote mirror and restore | Covered by Google snapshot/mirror ADR and SecureStorage production hardening ADR | Low-medium. Architecture exists, but partial mirror recovery, escrow absence, stale manifests, and namespace mismatch require adverse tests | W09.P04.S03 |
| Plaintext side stores and diagnostics | Covered as unresolved/backlog in secure persistence enforcement ADR and SecureStorage production hardening ADR | Low. Must be inventoried as secure-object migration, accepted exception, or retired surface | W09.P01.S03, W09.P03.S01 |

Conclusion: the feature is comprehensive in architecture intent, but not yet
complete in executable policy coverage. The current plan now tracks the gap as
W09 rather than treating it as incidental wallet hardening.

W09-P01-S01-CR-001 | PASS | Coverage matrix is broad and does not overstate implementation status

Reviewed the ADR coverage matrix against the current wallet plan and accepted
SecureStorage ADR chain. The matrix covers the requested surfaces and extends to
the adjacent recovery surfaces that can affect the same evidence boundary:
repair, bucket maintenance, profile lifecycle, custody, secure persistence,
ledger, invoices, imports, exports, Modelo state, filing history, wallet
evidence, auth diagnostics, bucket events, remote mirror recovery, and plaintext
side stores.

The matrix correctly distinguishes accepted ADR authority from implementation
confidence. Low and medium-low rows remain open and point to W09 plan hooks
instead of claiming closure. No critical/high issues found in this doc-only
step. Residual risk: W09.P01.S02 must decide whether a focused ADR amendment is
required, and W09.P01.S03 must convert the matrix into an executable
namespace-policy map.

SECURESTORAGE-W09-P01-S02 | PASS | Existing accepted ADR chain governs repair/recovery policy mechanisms

W09.P01.S02 adjudication completed. A new ADR is not required before continuing
implementation. The accepted SecureStorage production hardening ADR governs the
core mechanisms: runtime boundary, bucket-session routing, namespace registry,
repair policy, recovery policy, remote mirror policy, retention policy,
partial-read policy, fail-closed listing, revision lineage, readiness
diagnostics, and degraded-source blocking before filing-grade output.

The adjacent accepted ADRs govern the remaining surface:
profile/bucket/repository terminology, config repair command shape, bucket
maintenance, custody and recovery, and secure persistence enforcement. W09.P01.S03
should therefore implement the executable namespace-policy map under the current
ADR chain.

A focused ADR amendment remains mandatory only if later W09 work proposes a new
destructive repair class, a new live AEAT mutation, a new plaintext sensitive
side-store exception, or a remote recovery mode that bypasses custody/escrow
semantics.

W09-P01-S03-CR-001 | PASS | Namespace-policy map centralizes repair/recovery policy fields

Reviewed the W09.P01.S03 backend change. `RepairNamespacePolicy` records the
cross-domain policy fields that were missing from executable code: owner domain,
bucket scope, sensitivity class, repair policy, recovery policy, mutation
authority, export policy, import policy, retention/legal note, and
calculation-confidence impact. The policy is derived from the existing namespace
classification layer, so wallet observations, filing evidence, submission
receipts, ledger, invoices, Modelo state, profile state, auth state, unknown
namespaces, and operational support state share one repair/recovery policy
entry point.

The change does not add mutation behavior, live AEAT behavior, quarantine,
delete, import execution, or export execution. It is a policy map only. The
tests cover three high-value cases: wallet observations map to read-only remote
state recovery, unknown namespaces disable import and quarantine until an owner
contract is registered, and justificante receipt metadata preserves statutory
tax evidence and remains non-quarantineable.

No critical/high issues found. Residual risk: W09.P01.S04 still needs a gate
that fails when new repair, recovery, import, export, or bucket commands lack an
ADR-linked namespace/domain policy. W09.P03 must later enforce this map at
repository/runtime boundaries.

W09-P01-S03-CR-002 | PASS | CLI privacy tests now exercise the active-bucket route guard

The widened repair/privacy gate exposed a stale direct-test route: the CLI
privacy fixture pinned `AEAT_DATABASE_URL` to a root test database, so direct
`SecureObjectRepository()` calls were no longer attached to the active profile
bucket and correctly failed the route guard. The test harness now creates the
operator profile through the real CLI active-bucket flow, leaves database route
resolution to `AEAT_LOCAL_STORAGE_ROOT` plus the active-profile pointer, and
uses the documented synthetic tax id for the unsecured backend. Raw ciphertext
metadata snapshots are still non-decrypting, but now open the active profile
session before reading secure-object rows.

No critical/high issues found in this follow-up. The result strengthens the
test rather than relaxing production route enforcement: the privacy contract now
proves repair plan/list output remains redacted and non-mutating while the
repository is bound to the same bucket route an operator would use.

SECURESTORAGE-W09-P01-S04 | PASS | Policy coverage gate added for repair/import/export/bucket commands

W09.P01.S04 completed. `RepairPolicyCommandSurface` now records command path,
command family, owner domains, governed namespaces, mutation policy, redaction
policy, and accepted ADR links for repair, recovery, import, export, and bucket
surfaces. The current catalog covers repair diagnostics and planning, profile
import/export recovery, bucket history, ledger import/export, Modelo export,
external filing import, and Modelo audit export.

The CLI coverage test parses the real Typer source modules with Python AST and
discovers command paths under the `config`, `app ledger`, `app modelo`, and
`app live` roots. Every discovered command whose path contains `repair` or
`bucket`, or whose leaf command is `import` or `export`, must match a cataloged
policy entry. Namespace-linked entries materialise executable namespace policies
and fail when a namespace is unknown or unregistered.

No critical/high issues found. Residual risk moves to W09.P02/W09.P03: the
catalog is now enforced for coverage, but CLI wording and runtime repository
enforcement still need to consume the same command/namespace policy directly
rather than relying on tests alone.

W09-P01-S04-CR-001 | PASS | Coverage gate includes future recovery verbs

Focused code review found one medium-risk gap before closure: the first source
filter covered repair, bucket, import, and export commands but did not include
future commands named `recover`, `recovery`, or `restore`. The filter now treats
those leaf commands as policy-covered recovery surfaces, matching the plan row's
wording. Focused tests and ruff passed after the correction.

No critical/high issues found. Residual risk remains the planned W09.P02 and
W09.P03 work: command handlers still need to render and enforce these policies
directly, not only be covered by the catalog gate.
