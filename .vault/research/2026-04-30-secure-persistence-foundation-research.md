---
tags:
  - '#research'
  - '#secure-persistence-foundation'
date: '2026-04-30'
modified: '2026-04-30'
related:
  - "[[2026-04-29-secure-persistence-foundation-adr]]"
  - "[[2026-04-28-secure-persistence-foundation-exec]]"
  - "[[2026-04-27-security-storage-audit-audit]]"
---



# `secure-persistence-foundation` wave-4 research

## Origin

Wave 1 shipped the substrate. Wave 2 added the operator-facing
primitives + the read-through canary-adapter pattern. Wave 3
landed the financial-domain consumer — Kent's bank-import
moment closed in commit `1741517`. The TDP T1 row in
`docs/coverage/pipeline.md` flipped from `🚧 (no persist)` to
`✅ persisted via aeat financial ingest --persist`.

Wave 4 is the **filing-domain consumer wave** plus the
**audit-sink relocation** the upstream 2026-04-27 security audit
graded HIGH. The two scopes co-deliver because the filing /
submission / amendment / justificante writers and the
live-submit audit log share an identity-bearing, taxpayer-NIF-
bearing record shape; co-locating their migrations means one
audit pass covers both surfaces and the redaction rule contract
gets exercised end-to-end on real domain shapes.

## Wave-4 candidate consumer surface

The audit identified the following plaintext-on-disk filing
state. Each is a Wave-4 migration candidate:

- `var/drafts/<draft_id>.json` — filing-draft records under
  `aeat.entrypoints.cli.filing` and `aeat.entrypoints.cli.review`. Contains taxpayer
  NIF, line-by-line casilla values, approval state. Migration
  target: FINANCIAL-class envelope per draft, content-addressed
  by the existing draft id (already a UUID).
- `var/submissions/<submission_id>.json` and amendments under
  `aeat.adapters.outbound.aeat.export._engine` / `aeat.application.filing._complementaria`.
  AUDIT-class for the submission record (it captures the
  exact bytes Kent uploaded to AEAT); identity-bearing.
- `var/justificantes/<csv>.pdf` — AEAT-issued PDF receipts
  + downstream extracted records. AUDIT-class for the parsed
  records; the PDFs themselves are operator-class (Kent's
  legal proof of filing).
- `var/filing-history/<entry>.json` — historical filing state
  + optional archived detail-page HTML. AUDIT-class.
- `.aeat/live-submit-audit.log` — the hard-coded JSONL log
  outside any configured root, graded HIGH-2 by the upstream
  audit. Captures NIF, draft checksum, justificante CSV,
  submission URL, environment state, process arguments. The
  upstream audit's HIGH recommendation is to relocate this
  under `aeat_audit_dir` and route every emission through the
  substrate's redaction rule contract before write.

## Wave-4 success criteria

1. Every Wave-4-targeted file lives under an
   `Envelope[<DomainPayload>]` at the appropriate sensitivity
   classification (FINANCIAL / AUDIT / IDENTITY) — no plaintext
   identity-bearing material on disk outside the substrate's
   governed roots.
2. `.aeat/live-submit-audit.log` is relocated to
   `aeat_audit_dir / live-submit-audit.envelope.jsonl` (or
   per-event envelope files). Every emission passes through
   `redact()` with the AUDIT-class default rules
   (NIF → SHA-256 prefix; URL → host-only; bearer →
   fingerprint; new opaque-bearer rule from Wave 2 covers
   non-JWT shapes).
3. The read-through adapter pattern from Wave 2 is reused: the
   existing draft / submission / justificante readers consult
   the envelope first, fall back to legacy plaintext with a
   one-shot deprecation log; one-shot migration helpers move
   data on operator demand.
4. Wave-4 tests demonstrate the redaction works on a real
   live-submit-audit event shape — no NIF, URL path, or
   bearer-token-shaped value lands in the audit log unredacted.

## Wave-4 plan shape (preview)

- Phase 0: action any Wave-3 audit-gate findings that emerge.
- Phase 1: filing-draft repository + read-through service helpers.
  FINANCIAL classification.
- Phase 2: submission record repository. AUDIT classification.
- Phase 3: amendment record repository. AUDIT classification.
- Phase 4: justificante records (parsed PDF metadata)
  repository. AUDIT classification. The PDFs themselves remain
  in `aeat_justificantes_dir` because they are operator-class
  legal proof; the substrate already wraps them via the
  `EncryptedBlobStore` content-addressable layout.
- Phase 5: live-submit audit relocation. New
  `aeat.adapters.outbound.aeat.export._audit` writer routes every event through
  `redact(value, rules=default_rules_for_class(AUDIT))` then
  writes JSONL to `aeat_audit_dir`. Migration helper drains
  any existing `.aeat/live-submit-audit.log` into the new
  location with an explicit redaction pass. Legacy file is
  archived with a deprecation log.
- Phase 6: filing-history repository. AUDIT classification.
- Phase 7: end-to-end Wave-4 integration test exercising one
  filing draft → approval → submission record → justificante
  → reconcile → archived in filing-history, with the
  live-submit-audit log redacted at every event.
- Phase 8: Wave-4 audit gate.

## Standing constraints inherited from Waves 1-3

- The substrate's public API is `aeat.adapters.persistence.storage` only.
- Pydantic v2 strict frozen at every boundary.
- No mocks; tests use real cryptography, real on-disk
  persistence, real CliRunner, real multiprocessing.
- Read-through adapter pattern is non-negotiable.
- Trilingual error envelope contract continues to apply.
- Live AEAT submission permanently forbidden — Wave 4 touches
  the live-submit AUDIT log writer but does NOT change the
  live-submit gate logic.
- No new GH issues are filed for findings; #216 absorbs
  everything.

## Inherited audit-finding backlog

Carried forward from the Wave-2 audit gate (still un-actioned
because Wave 3 prioritised the Kent moment):

- vs-L-1, vs-L-2 — docstring notes (cosmetic)
- vs-L-3 — `functools.lru_cache` on regex compile in
  `_redaction._apply_one`
- vs-L-4 — recursive `redact()` for structured payloads
  (will be load-bearing for Wave 4's audit-sink relocation —
  audit events are structured dicts, not flat strings)
- sec-L-3 — NIF check-letter validator landed in Wave-2 Phase 3;
  the substrate's `nif-hash` redaction rule's regex remains
  permissive on purpose. Optional Wave-4 hardening would tighten
  it to consume `aeat.adapters.inbound.identity.validate_identity` for false-
  positive elimination
- vs-L-5 — already actioned in Wave-2 Phase 0
- vs-L-6 — secret-store delete blob-cleanup logging (already
  actioned in Wave-2 Phase 1's sec-M-3)
- The substrate's `SecretStore._check_class` widening to accept
  IDENTITY (Wave-2 reviewer's L-1) — required for the operator-
  profile re-classification noted in Wave-2's exec summary; can
  land alongside Wave-4 if convenient

Will append Wave-3 audit-gate findings here as the running
reviewer reports.

## Out of scope for Wave 4

- Observability + run-trace redaction discipline (Wave 5).
- Cache and corpus migrations (Wave 6).
- Connector + export governance (Wave 7).
- Substrate-widening for IDENTITY-class records in the secret
  store (separate ADR; co-deliver if Wave-4 hits the operator-
  profile case).
- Argon2id / SQLCipher / master-key rotation / per-profile
  keyring service identifiers (separate ADRs; deferred from
  Wave 1).

## Open audit-finding inventory at Wave-4 entry

Identical to the Wave-3 audit-gate-deferred backlog above. The
Wave-4 ADR will commit to a phase ordering once the Wave-3
audit gate completes.
