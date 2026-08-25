---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:7726c8be4cf0f2ba67350b78bbf0ce6024ede51e1f3019b5c0ba6cfa4e9cc169'
related:
  - "[[2026-08-24-tui-registry-api-gate-adr]]"
  - "[[2026-08-11-tui-architecture-plan]]"
  - "[[2026-08-25-tui-architecture-s160-approved-amendment-architecture-review-audit]]"
  - "[[2026-08-25-tui-architecture-s160-plan-amendment-review-audit]]"
  - "[[2026-08-11-tui-architecture-W03-P20-S168]]"
---

# `tui-architecture` audit: `S168 pointer transition code review`

## Scope

Independent code review of `W03.P20.S168` against the accepted registry API-gate amendment, the governing architecture and plan audits, the checked plan row, and the S168 execution record. The review baseline was the combined current source at `69b2e9b000d`; the implementation lineage was traced through `d64845fbf1`, the five S168 corrections included in `03d2b3caef1`, and the close commit `2897ee552d5`, but every conclusion below comes from current source behaviour and an exact census rather than those commit claims.

Discovery started with semantic Vaultspec RAG over code and decisions, then narrowed to whole-file inspection of the pointer record/IO, transaction, configuration, reset, custody, login, lifecycle, workflow-health, storage-write-policy, and profile-deletion epicentres. The final exact source census found 87 production Python files referencing `resolve_active_bucket_id`, `require_active_bucket_id`, or `resolve_repository_bucket_id`, with 128 call-or-definition matches. It found six production `read_pointer` definition/call sites and exactly one production `write_pointer` caller outside the writer definition.

The focused existing suite passed: 59 tests covering the strict pointer model and IO, concurrent reader/writer atomicity, transition authority, reset, custody transactions, and login handover. Those tests confirm strict current-only schema version 2 parsing and version-1 refusal, a durable absent tombstone, idempotent same-state selection/clear, exactly one revision advance for each real select/clear/restore, real spawned-process A-B-A detection, typed custody/login coordinates, the sole low-level writer, and the exercised no-follow/atomic-replacement paths. Exact census also found no second pointer schema, path literal, custody-root lock identity, compatibility reader, old raw-byte handover, legacy mutation owner, or retired `_custody_pointer` implementation.

## Findings

### canonical-defining-module-cutover | high | Pointer authority remains private behind prohibited package re-exports

The accepted amendment requires exact public defining modules and inert package namespaces, with the former private definitions and every shim, alias, fallback, bridge, and re-export removed in the same change. Current source instead defines the record in `core._bucket_pointer`, its IO in `core._bucket_pointer_io`, and the application authority in `application.user_profile._profile_pointer_transaction`. Both `core.__init__` and `application.user_profile.__init__` expose those definitions through PEP 562 lazy re-exports. `BucketPointer` even imports `STRICT_FROZEN_CONFIG` through the `core` package facade. The S168 authority test positively locks in the prohibited shape by asserting that public package attributes have a private `_profile_pointer_transaction` defining module. This is not a naming preference: it leaves two package facades as alternate API homes, preserves private-module coupling, and directly contradicts the accepted canonical-home gate that was in force before `d64845fbf1` landed.

### reader-cutover-and-config-coordinate | high | Raw readers bypass the transaction and settings construction splits one coordinate across two reads

The implementation did achieve one low-level writer, but it did not atomically migrate every production reader. `core._bucket_pointer_io.resolve_active_bucket_id` reads the pointer without the custody-root transaction, and the exact census shows that resolver family still supplies 87 production files. `workflow._profile_health`, storage repositories, adapters, application services, and entrypoints continue to consume that unlocked raw-reader path. `core.config` contains two additional direct `read_pointer` calls outside the application observation authority.

The configuration exception is observably racy. `_active_profile_pointer_fingerprint` reads a pointer revision to form the cache key, `_constructed_settings` ignores the corresponding record, and `Settings._resolve_database_url_for_active_profile` independently reads the pointer again to choose the bucket route. A reviewer-only deterministic interleaving changed A/revision 1 to B/revision 2 between those reads. One `load_settings` call then cached a B database route under the A/revision-1 key. Atomic file replacement prevents torn bytes but does not make those two observations one coordinate, so the returned settings instance can be mislabeled and a subsequent lookup of the old key can reuse a route derived from another state. This falsifies both the all-reader cutover and the required atomic cache coordinate.

### config-reset-stale-absence | high | Reset recovery treats every later absent coordinate as its own clear

`ConfigResetOperation` correctly journals a typed `BucketPointer`, but `_reconcile_pointer_snapshot_for_resume` stops comparing that coordinate once any target reaches `POINTER_RECONCILING`: every current record whose `bucket_id` is absent is accepted, regardless of `transition_revision`. The reset first persists `POINTER_RECONCILING`, then clears the pointer, so a crash in that window followed by A-B-absent transitions can produce a later tombstone that recovery silently treats as the reset's expected successor. `_reconcile_pointer` then observes an idempotent absence, marks the pointer phase reconciled, and continues the destructive workflow without proving which transition produced the tombstone. Typed storage alone does not provide stale refusal; exact before/after coordinate comparison is required to distinguish crash replay from ABA lineage.

### implementation-traceability | low | S168 changes are mixed with unrelated feature work in both implementation commits

`d64845fbf1` includes unrelated `content_hash_hex` refactors in the filing review and flow-definition surfaces plus four associated test files. Conversely, the five reported S168 corrections are embedded in the 113-file operations relocation commit `03d2b3caef1`. These changes are not evidence of a pointer production defect and are not part of the FAIL disposition, but the mixed ownership prevents commit-level gates and review history from cleanly demonstrating what S168 itself changed.

## Recommendations

1. Reopen S168 and keep its dependent pointer work blocked until all three HIGH findings are remediated and independently re-reviewed.
2. For `canonical-defining-module-cutover`, hard-move the record/IO and transaction/observation symbols into the accepted public defining modules, rewrite every consumer to those modules, make both package `__init__` files inert, and delete the private originals and re-export maps atomically. Replace the current positive facade test with negative import/census gates for package attributes, private modules, aliases, and re-exports.
3. For `reader-cutover-and-config-coordinate`, replace the resolver-family census with one canonical lock-scoped observation at each operation boundary and pass explicit bucket coordinates into inner adapters rather than letting them reread process-global state. Configuration must capture one exact pointer record, use that same record as both cache key input and route-construction input, and never reread the pointer inside `Settings` construction. A lock-scoped capture or an exact post-construction compare/retry may implement the cutover, but a split fingerprint/validator read may not. Add the deterministic A/revision-1 to B/revision-2 interleaving as a regression test and require zero production raw-reader callers outside the named IO/transaction implementation.
4. For `config-reset-stale-absence`, journal or derive the exact expected successor coordinate and accept only the exact before record or exact after record during recovery. Every other selected or absent coordinate must pause/refuse as stale. Add a real crash-recovery test for A/revision N, crash after `POINTER_RECONCILING`, external B/revision N+1, absent/revision N+2, and resume refusal.
5. For `implementation-traceability`, review and attribute the unrelated `d64845fbf1` changes separately and keep future remediation commits path-pure so feature-surface evidence maps to one plan step.

## Disposition

FAIL. There are no CRITICAL findings, but the three HIGH findings require S168 to reopen. The passing transition, durability, cross-process, typed-journal, sole-writer, and no-follow evidence remains useful and should be preserved while the canonical-home, reader/cache, and stale-reset defects are corrected.
