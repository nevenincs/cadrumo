---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:08d3ad1f175f71fa22b7baa7ff8d1b0a8439e16893f15d54138b4e6dc7a48afc'
related: []
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace tui-architecture with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `tui-architecture` audit: `s18 review`

## Scope

Independent expanded review of `W02.P04.S18`, limited to the operation journal adapter, two-hop substrate facade, operation-journal taxonomy/path/durability additions, relevant tests and execution evidence. Concurrent profile-custody work was treated as peer-owned and excluded.

## Findings

### event-stream-port | high | The persistence implementation stores history but cannot replay it

The private file record retains complete history, but `OperationJournalRepository` implements only `OperationJournal`; it exposes neither `OperationEventStream` nor `read_after`. No other S18/S19 implementation owns that port, while S21 is explicitly required to prove cursor replay. Persisting unreachable history is insufficient: the persistence facade cannot satisfy the application replay boundary or distinguish page, caught-up, expired, compacted, and unknown-operation outcomes defined in S17.

### initial-history-origin | high | Initial creation can persist an incomplete history prefix

Create validation requires revision zero but does not require the first event sequence to be one. Both `OperationPersistedSnapshot` and `_OperationJournalRecord` accept a single initial event at sequence five with cursor five. The resulting file claims complete ordered history while silently omitting events one through four; later append checks preserve that gap forever. A planted non-one initial cursor/sequence mutation is absent.

### historical-record-binding | high | Complete history validation omits revision and terminal coherence

The one-file envelope checks history identity, contiguity, and final cursor only. It does not require event revisions to be monotonic and bounded by the current snapshot revision, does not bind the final history event/time/phase/terminal receipt to the snapshot beyond the current batch, and does not reject a terminal event followed by later history when parsing persisted bytes. Although normal writes constrain each new batch, corrupted or manually altered durable data can hydrate into a semantically false history rather than fail closed.

### lease-authority | medium | Journal commit proves operation identity but not current unexpired ownership

The adapter accepts any structurally valid lease with the matching operation ID; it does not verify token/current-owner state or expiry. S19 will implement the lease repository, so storage-backed current-owner verification may properly compose there, but the current `OperationJournal` implementation should not be described as enforcing D5's “only current lease owner may advance” invariant until an exact composition boundary exists and is tested.

### canonical-storage-reuse | low | Taxonomy, facade, locking, and byte-preserving CAS are otherwise sound

`JournalRepositoryBase` is promoted through the application and operation facades; the adapter uses that public two-hop owner. The fixed `operation-journals` category, root grammar, schema version, and durable compatibility entry are canonical and surgical. One lock encloses load, validation, and atomic replacement; repeated create, stale/non-unit revision, lease identity, cursor, and accepted reload paths are exercised with byte-preserving refusal checks and secret-payload absence. No private application import, duplicate writer, mapping fallback, or registry/secure-resolution behavior was added.

### typing-only-edits | low | Registry and test typing changes do not alter runtime behavior

The reviewed registry-related changes are annotation/narrowing accommodations for dynamically selected concrete models and test type checking. No new resolver fallback, payload coercion, or business branch was introduced in S18 scope.

## Recommendations

- Implement the public event-stream port over the stored history, including bounded exclusive-cursor pages and explicit unknown/expiry/compaction behavior, or identify and authorize its actual owning step before closing S18.
- Require initial durable history to begin at sequence one and plant a byte-preserving refusal mutation.
- Validate the complete stored history on every load/write: revision progression, terminal finality, and exact current snapshot cursor/time/phase/receipt agreement must fail closed for corrupted bytes.
- Record the S19 lease-repository composition that proves token, owner, and expiry at journal commit time; do not claim current-owner enforcement from operation-ID matching alone.
- Rerun exact adapter/application/taxonomy pytest, Ruff, and basedpyright gates after remediation.

## Final re-review

### event-stream-port-closure | low | Retained history now serves bounded exclusive replay

`OperationJournalRepository` implements both journal and event-stream ports. `read_after` validates cursor/limit before access, distinguishes absent records from corrupt ones, returns deterministic exclusive bounded pages with exact continuation cursors, and preserves the request cursor for caught-up and unknown outcomes. Repeated requests are proven idempotent; expiry and compaction are honestly not claimed under retain-all policy. The replay HIGH is closed.

### initial-history-origin-closure | low | Creation now permits only empty-zero or sequence-one history

Initial creation requires revision zero and either an empty event batch with cursor zero or a nonempty batch beginning at sequence one. The direct test plants sequence two and confirms refusal. The incomplete-prefix HIGH is closed.

### historical-record-binding-closure | low | The complete typed envelope now fails closed on global corruption

Every stored event is bound to snapshot identity; sequences begin at one and remain contiguous; timestamps are nondecreasing; revisions advance monotonically by at most one and end at the snapshot revision; terminal events are final; and the latest history suffix exactly equals the snapshot's current event batch. Raw-file mutations cover identity, starting sequence, timestamp, revision, terminal placement, and tail divergence, all refused on load. The history-coherence HIGH is closed.

### lease-authority-deferral | low | S18 explicitly retains correlation-only lease responsibility

The journal verifies that the supplied lease names the written operation. Owner/token/expiry acquisition and takeover authority remain explicitly assigned to S19 and are not claimed by S18. This is a coherent composition boundary rather than silent current-owner enforcement, closing the MEDIUM for this step while preserving the later mandatory proof.

### final-gates | low | Adapter and canonical gates are current

The full recorded surface passes 51 tests with clean Ruff and basedpyright; the remediated adapter's direct suite separately passes nine tests with clean Ruff and basedpyright. Canonical absolute imports corrected the non-package test collection without changing production behavior.

Final verdict: PASS. No CRITICAL, HIGH, or MEDIUM findings remain.
