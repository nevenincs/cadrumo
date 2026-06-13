---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-05-22-secure-storage-production-hardening-architecture-adr]]'
  - '[[2026-05-22-secure-storage-production-hardening-architecture-research]]'
---

# `secure-storage-production-hardening` Code Review

S29-001 | HIGH | Public conflict-policy metadata can claim CAS without CAS enforcement
`secure_objects.py` exposes `conflict_policy` on `save`, `save_with_raw_key`, and `SecureObjectWrite`, then persists the caller-provided string directly. S29 is scoped to writing revision ids, previous references, hashes, timestamps, and provenance; S30 is the plan row for compare-and-swap conflict handling. Because the current code accepts arbitrary policy text while still performing unconditional last-write-wins upserts, a caller can record `compare-and-swap` or another conflict policy that was not enforced. This improperly crosses the S30 boundary and makes revision metadata untrustworthy for audit and sync consumers.

S29-002 | HIGH | Legacy overwrites lose lineage when prior metadata is absent
`secure_objects.py` reads only the existing `revision_id` and `payload_hash` before overwriting a row. The S31 bootstrap path intentionally leaves pre-existing rows with nullable revision metadata, and the S29 overwrite path does not compute a previous payload hash from the readable prior payload before replacing it. The first overwrite of an upgraded legacy row therefore records no `previous_revision_id` and no `previous_payload_hash`, erasing the only available lineage for that superseded payload. The ADR requires a previous revision id or previous payload hash when applicable, and says upserts that would lose lineage must create a revision or fail through the conflict contract.

S29-003 | MEDIUM | New metadata paths are not covered across all write APIs
The added tests cover the natural-key `save` path for initial writes and overwrites, but not `save_many` or `save_with_raw_key`. Both methods now carry the same revision metadata responsibilities, and `save_with_raw_key` is used by archive/restore paths where natural keys may be unavailable. This leaves real write-path coverage incomplete for the slice.

S29-FOLLOWUP-001 | LOW | Follow-up review found prior blockers resolved
Follow-up review on 2026-05-28 found the public `conflict_policy` input removed from the S29 API surface, S29 persistence fixed to record only the actual internal `last-write-wins` policy until S30, legacy-row overwrites fixed to derive `previous_payload_hash` from the prior plaintext before replacement when metadata is absent, and coverage added for legacy overwrite lineage, `save_many`, `save_with_raw_key`, and strict rejection of caller-supplied `conflict_policy`. Focused `ruff` and `test_secure_objects.py` checks passed with no remaining S29-scoped HIGH, CRITICAL, MEDIUM, or blocking LOW findings.
