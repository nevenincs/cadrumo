---
tags:
  - '#research'
  - '#live-iva-compensation-wallet'
date: '2026-05-26'
modified: '2026-05-26'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
  - '[[2026-05-26-securestorage-repair-policy-adr-coverage-audit]]'
  - '[[2026-05-22-secure-storage-production-hardening-architecture-adr]]'
  - '[[2026-05-22-live-iva-compensation-wallet-profile-bucket-repository-binding-reconciliation-adr]]'
  - '[[2026-05-13-cli-workflow-redesign-config-repair-shape-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-bucket-adr]]'
  - '[[2026-05-14-secure-backend-passkey-custody-adr]]'
  - '[[2026-05-06-secure-persistence-enforcement-adr]]'
---

# `live-iva-compensation-wallet` research: `SecureStorage repair policy ADR adjudication`

This research adjudicates W09.P01.S02: whether current accepted ADRs govern the
SecureStorage repair/recovery policy mechanisms, or whether a focused ADR
amendment is required before continuing implementation.

## Findings

The accepted SecureStorage production hardening ADR is broad enough to govern
the policy mechanisms. It requires a mandatory production storage boundary,
bucket-session routing, namespace registry entries, repair policy, recovery
policy, remote mirror policy, retention policy, partial-read policy, fail-closed
listing, revision lineage, readiness diagnostics, and degraded-source blocking
before filing-grade output. Those are the mechanisms the current repair plan
needs.

The accepted profile/bucket/repository/binding reconciliation ADR resolves the
terminology problem for this work. It distinguishes operator profile, private
profile UUID, bucket, bucket manifest, active pointer, `BucketSession`, domain
repository, physical `SecureObjectRepository`, calculation binding, source
observation, and reconciliation decision. That ADR is sufficient authority for
keeping repair output redacted while still allowing internal UUID-aware routing
and confidence classification.

The accepted config repair shape ADR governs the CLI home and command family.
It places diagnostics and storage maintenance under `aeat config repair`,
requires thin CLI handlers, requires `_emit` text/JSON output, requires
actionable warn/fail diagnostics, and originally defines quarantine and
workflow-state reset. Later W05 execution narrowed quarantine with
preserve-first decision records, verified evidence requirements, and protected
namespace prohibitions; those changes are compatible with the ADR because they
make the maintenance surface safer, not broader.

The accepted bucket ADR governs profile-scoped bucket storage and bucket
maintenance commands. It is enough authority for W09 to audit bucket
browse/search/export/import/rename/delete policy and to ensure those operations
stay storage maintenance rather than normal app workflow.

The accepted custody ADR governs passphrase, recovery code, lock/unlock,
rekey, recovery, and no silent key minting. It is sufficient authority for W09
custody and recovery adverse-condition tests.

The accepted secure persistence enforcement ADR governs sensitive persistence
through encrypted SQL secure objects and treats direct plaintext writes as
exceptions requiring classification. It is sufficient authority for W09 side
store inventory and repository-boundary enforcement.

Decision: a new ADR is not required before continuing W09 implementation. The
existing accepted ADR chain governs the mechanisms. W09.P01.S03 should implement
an executable namespace-policy map under those ADRs.

Focused ADR amendment trigger: if W09.P01.S03 discovers a policy class that
cannot fit the accepted architecture, such as a new destructive repair mode, a
new live AEAT mutation, a new plaintext sensitive side store exception, or a
remote recovery mode that bypasses custody/escrow semantics, then a focused ADR
amendment is required before implementation of that policy class.
