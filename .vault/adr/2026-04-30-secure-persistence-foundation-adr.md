---
tags:
  - '#adr'
  - '#secure-persistence-foundation'
date: '2026-04-30'
modified: '2026-04-30'
related:
  - "[[2026-04-30-secure-persistence-foundation-research]]"
  - "[[2026-04-29-secure-persistence-foundation-adr]]"
  - "[[2026-04-27-security-storage-audit-audit]]"
---



# `secure-persistence-foundation` wave-4 adr | (**status:** `accepted`)

## Problem statement

Wave 3 closed Kent's bank-import moment. Wave 4 lands the
**filing-domain consumer adapters** plus the **audit-sink
relocation** the upstream 2026-04-27 security audit graded HIGH-2
(`.aeat/live-submit-audit.log` outside any configured root,
captures NIF / draft checksum / justificante CSV / submission URL /
process arguments). The two scopes co-deliver because the filing /
submission writers and the live-submit audit emit overlapping
identity-bearing record shapes; co-locating their migrations
exercises the substrate's redaction-rule contract end-to-end on
real AUDIT-class events.

## Considerations

Architectural drivers:

- The `aeat.application.filing` and `aeat.adapters.outbound.aeat.export` modules already use the
  pydantic-v2-frozen + atomic-tempfile-write pattern. Migration
  is structurally a thin envelope wrapper (the existing
  `Wave-3` repository pattern carries forward verbatim).
- The live-submit audit log emission is the load-bearing change.
  Today `aeat.adapters.outbound.aeat.export._audit` writes JSONL to
  `.aeat/live-submit-audit.log` (project-relative, outside
  `aeat_audit_dir`). The relocation replaces the writer with
  one that routes every event through
  `aeat.adapters.persistence.storage.redact_structured(event, rules=default_rules_for_class(SensitivityClass.AUDIT))`
  before writing JSONL to
  `aeat_audit_dir / live-submit-audit.envelope.jsonl`. The
  legacy log is migrated forward with an explicit redaction pass
  by a one-shot helper.
- `redact_structured` (added in commit `80ef8c3`) is the
  primitive: it walks dict / list / tuple containers and
  redacts string leaves while preserving the container shape.
- Filing draft records are FINANCIAL classification (per-line
  casilla values are tax-relevant arithmetic).
- Submission, amendment, justificante, filing-history records
  are AUDIT classification (capture the exact bytes Kent uploaded
  + the AEAT response — auditable evidence with identity-bearing
  context).
- The Wave-3 audit-gate HIGH-1 (ADR drift on encryption-at-rest)
  applies to Wave 4 as well: envelopes today persist plaintext
  payloads inside the classification gate. The Wave-4 ADR is
  honest about this — payloads are CLASSIFIED at rest;
  CIPHERTEXT-at-rest layering arrives in a follow-up wave that
  wires `encrypt_record` + `EncryptionMetadata` into the
  per-domain repositories' save paths and adds leak-canary
  regression tests.

## Constraints

- Python 3.13+, Windows-supported. No new runtime dependencies.
- Pydantic v2 strict frozen at every boundary.
- Trilingual error envelope contract.
- No mocks; tests use real on-disk persistence + CliRunner.
- Read-through adapter pattern is non-negotiable.
- Live AEAT submission permanently forbidden — Wave 4 only
  touches the live-submit AUDIT log writer, never the gate
  logic itself.
- Coverage floor 60% on `src/aeat` preserved.
- No new GH issues; #216 absorbs everything.

## Implementation

### Phase 0 — Wave-3 audit-gate finding cleanup

Already actioned in Wave-3 close commit `80ef8c3` (HIGH-1 ADR
honesty + HIGH-2 TOCTOU + MEDIUM-1 zero-amount). Wave-4 inherits
the remaining MEDIUM/LOW Wave-3 reviewer findings as input
backlog (recommended docstring tweaks; ImportSummary errors-
field validation; cross-module error re-export discipline).

### Phase 1 — Filing draft repository

New module `aeat.application.filing._repository` mirroring the Wave-3
`TransactionCatalogueRepository` pattern:

- `FilingDraftRepository(*, store_dir)` wraps
  `Envelope[FilingDraft]` at FINANCIAL class with
  `exclusive_file_lock(<store_dir>/<draft_id>.lock)` per draft.
- `load(draft_id)` / `save(draft)` / `delete(draft_id)` /
  `list_draft_ids()`.
- One envelope per draft (`<draft_id>.envelope.json`) so
  per-draft locking does not contend across the whole
  drafts directory.
- `migrate_legacy_drafts_to_repository(legacy_dir, repository,
  *, overwrite=False)` reads every `<draft_id>.json` in the
  legacy dir and persists each through the repository.

### Phase 2 — Submission repository

`aeat.adapters.outbound.aeat.export._repository` — submission records at AUDIT
class. Same per-record envelope shape; same per-record lock.

### Phase 3 — Amendment repository

`aeat.application.filing._complementaria_repository` — amendments at AUDIT
class. Co-located with the submission repository because the
existing complementaria flow consumes both.

### Phase 4 — Justificante records repository

`aeat.domain.justificante._repository` — parsed justificante metadata
at AUDIT class. The PDF blobs themselves remain in
`aeat_justificantes_dir` (operator-class legal proof; the
substrate already handles them via `EncryptedBlobStore`).

### Phase 5 — Live-submit audit relocation

The big one. New `aeat.adapters.outbound.aeat.export._governed_audit` writer:

- Replaces the existing `aeat.adapters.outbound.aeat.export._audit` writer.
- Sink target: `aeat_audit_dir / live-submit-audit.envelope.jsonl`.
- Every event passes through
  `redact_structured(event, rules=default_rules_for_class(SensitivityClass.AUDIT))`
  before write — NIF SHA-256-prefixed, URL host-only, bearer
  fingerprinted, opaque-bearer fingerprinted (Wave-2 rule).
- Migration helper `migrate_legacy_live_submit_audit(legacy_path,
  audit_dir)` drains any existing `.aeat/live-submit-audit.log`
  through the redaction contract into the new location and
  archives the legacy file.
- Tests confirm no NIF / URL path / token shape lands in the
  output.

### Phase 6 — Filing-history repository

`aeat.application.filing._history_repository` — historical filing-state
records at AUDIT class. The HTML detail-page archive stays in
the existing `aeat_filing_history_dir` (large blobs; operator-
visible legal record).

### Phase 7 — Wave-4 integration test

End-to-end: build one filing draft → approve → emit submission
record → fetch justificante → reconcile → archive in
filing-history. Assert at every step that:

- The on-disk envelope is FINANCIAL (drafts) or AUDIT
  (submissions / justificantes / history).
- The live-submit audit log emission has no NIF, URL path, or
  bearer-token-shaped value in the JSONL.
- Re-running the same step against the same store is
  idempotent.

### Phase 8 — Wave-4 audit gate

Identical contract to Waves 1-3.

## Rationale

The phase ordering prioritises the load-bearing audit-sink
relocation (Phase 5) only after the per-domain repository
adapters (Phases 1-4) are in place, because the audit-sink
emission references the same record shapes the repositories
host. Phase 6 (filing-history) is structurally simpler and
co-delivers with the audit-sink to verify the AUDIT-class
end-to-end flow.

The classification choice is FINANCIAL for drafts (per-line
arithmetic = financial state) and AUDIT for everything that
captures Kent's filing history. The redaction contract from
Wave 2 is the single point of truth for what does not land in
audit logs in plaintext; the new `redact_structured` helper
ensures nested dict events are walked recursively.

The ADR is explicit (per Wave-3 audit gate's HIGH-1) that
ciphertext-payload at rest is **deferred** until the
ciphertext-wiring wave. Wave 4 ships the same envelope-classified-
plaintext shape as Wave 3, with the same gate-at-load semantics.
The leak-canary regression test pattern (grep envelope file for
the plaintext, assert absent) lands together with the
ciphertext-payload wiring in a future ADR.

## Consequences

Positive:

- The HIGH-2 finding from the upstream audit (live-submit log
  outside configured root) is structurally closed.
- Filing-domain consumers gain envelope-classified persistence
  with classification gates at load.
- The redaction contract is end-to-end tested on real AUDIT-class
  event shapes — a regression that breaks the redaction would
  trip on first push.
- The `redact_structured` helper from commit `80ef8c3` becomes
  load-bearing; Waves 5-7 can consume it directly.

Negative (carried from Wave 3):

- Envelopes still persist plaintext payloads. Confidentiality-
  at-rest for the payload bytes lands in a follow-up wave.
- Operators with existing `var/drafts/`, `var/submissions/`,
  `.aeat/live-submit-audit.log` files must run the migration
  helpers; until they do, the read-through adapter consults
  the legacy paths transparently.

Neutral:

- No new runtime dependencies.
- No Alembic migration.
- The deferred-import pattern from Wave 3 carries forward to
  the new CLI surfaces (`aeat filing reconcile`,
  `aeat submission preflight`, etc.) so they don't pull
  Alembic into every CLI invocation.

## Out of scope

- Observability + run-trace redaction discipline (Wave 5).
- Caches and corpora (Wave 6).
- Connector + export governance (Wave 7).
- Ciphertext-payload wiring for envelopes (separate ADR after
  the Wave-4 plaintext envelopes are stable).
- IDENTITY-class records in the secret store widening
  (separate ADR).
- Argon2id / SQLCipher / master-key rotation / per-profile
  keyring identifiers (deferred from Wave 1).
