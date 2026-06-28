---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-05-27'
modified: '2026-05-27'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# `secure-storage-production-hardening` Code Review

W15-P30-001 | MEDIUM | Resolved no-summary result payload validation trap

The review found that `_result_summary_payload()` had been changed to return tuple rows for populated summaries but still returned a list on the no-summary lane. That preserved a strict pydantic tuple validation trap for valid calculate, revisions, or revision commands whose modelo has no result summary.

Resolution: `_result_summary_payload()` now returns `()` when no summary exists and `tuple(...)` for populated rows. The targeted Modelo 303 calculate path, which exercises the structural calculation surface, passes after the fix.

W15-P30-002 | PASS | Work-create validation-boundary repair

The reviewer found no remaining issue in the `WorkCreateResult.name_applied` change. The create/reuse command now matches the nullable rename-only field semantics, and the real CLI work UX test pins both fresh create and reuse-with-same-name as `null`.

W15-P30-003 | PASS | Test quality and privacy review

The reviewed tests use real CLI invocation and isolated secure SQL/runtime helpers. No mocks, fakes, stubs, monkeypatching, `skip`, or `xfail` shortcuts were identified. No new privacy or security regression was identified in the W15.P30 repair.

W15-P31-001 | MEDIUM | Resolved unreadable-list overexposure

The review found that `aeat config repair list --unreadable` only changed the reported filter mode while still returning every row digest for the namespace. That contradicted the CLI contract and exposed extra inventory metadata when the operator explicitly requested only degraded rows.

Resolution: the secure-object SQL repository now exposes row-level decryptability metadata without returning plaintext payloads, and `build_repair_list_report(..., only_unreadable=True)` filters to rows whose payloads fail AEAD verification. A real mixed-key regression test pins readable plus unreadable rows in one namespace.

W15-P31-002 | MEDIUM | Resolved generic repair-log object-key redaction

The review found that repair-log redaction only scrubbed two known object-key prefixes. That was too narrow for a paste-safe repair diagnostic surface because future secure-object domains can carry different natural-key prefixes.

Resolution: `config repair logs` now redacts keyed `object_key` / `object-key` / `lookup_key` / `lookup-key` assignments generically before UUID and tax-id scrubbing. The privacy contract now includes a non-wallet object-key prefix.

W15-P31-003 | LOW | Resolved repair-decision content hash drift

The review found that `RepairRemediationDecisionRepository.load_decision()` documented a re-derived content-address guard but only compared the persisted payload id to the lookup key.

Resolution: repair remediation decisions now re-derive the deterministic decision id on both save and load, and load uses the explicit AUDIT classification and version contract. A real encrypted-row regression test persists a tampered decision payload and verifies the load refusal.

W15-P32-001 | HIGH | Resolved bootstrap-exempt repair session gap

The review found that `config repair list` and `config repair quarantine` could resolve active-bucket repositories without opening a bucket session on the production bootstrap-exempt repair path. In-process CLI tests had masked the issue by opening a session through the normal root callback path.

Resolution: repair list, quarantine preview, and quarantine mutation now enter the active-bucket repair session helper before resolving active-bucket repositories. Direct sessionless regression tests clear the active session context and assert the repair surfaces still inspect the namespace instead of returning a false zero or crashing.

W15-P32-002 | PASS | Runtime-owned repository guard repair

The storage hardening guards now pass with runtime-owned repository construction, central active-bucket settings derivation, and secure-bound envelope fallback through `secure_object_repository_for_active_bucket_or_default_route()`. No remaining direct production bare repository construction was found by the guard slice.
