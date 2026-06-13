---
tags:
  - '#audit'
  - '#secure-persistence-foundation'
date: '2026-04-30'
modified: '2026-04-30'
related:
  - "[[2026-04-30-secure-persistence-foundation-adr]]"
  - "[[2026-04-30-secure-persistence-foundation-research]]"
  - "[[2026-04-27-security-storage-audit-audit]]"
---



# `secure-persistence-foundation` wave-4 audit gate | (**status:** `passed`)

## Summary

Wave 4 lands eight phases under the rolling-wave loop:

- Phase 1 — `FilingDraftRepository` at FINANCIAL class.
- Phase 2 — `SubmissionRepository` at AUDIT class.
- Phase 3 — `FilingAmendmentRepository` at AUDIT class.
- Phase 4 — `JustificanteRepository` at AUDIT class (parsed metadata only).
- Phase 5 — `GovernedLiveSubmitAuditSink` + legacy-log migrator (closes
  the upstream 2026-04-27 audit's HIGH-2 finding).
- Phase 6 — `FilingHistoryRepository` at AUDIT class.
- Phase 7 — End-to-end integration test walking every wave-4 repository
  together against real on-disk persistence.
- Phase 8 — This audit gate.

Test footprint: 135 tests across 7 test modules, all passing. Full
unit-suite regression: 3747 passed / 18 skipped / 21 deselected.

## Findings

### HIGH-2 from upstream audit — CLOSED

Upstream finding (2026-04-27): live-submit JSONL audit log persisted to
`.aeat/live-submit-audit.log` outside any operator-configured root,
captured NIF + draft checksum + justificante CSV + submission URL +
process arguments verbatim.

Closed by the new `GovernedLiveSubmitAuditSink`:

- Sink target relocated to `aeat_audit_dir / live-submit-audit.envelope.jsonl`.
  The path is composed from the operator-configured audit root, so the
  log lives inside the substrate's classification gate rather than the
  project tree.
- Every event passes through `redact_structured(event, rules=
  default_rules_for_class(SensitivityClass.AUDIT))` before write —
  NIF SHA-256-prefixed, URL host-only (path/query stripped),
  bearer-shaped tokens fingerprinted, opaque bearers fingerprinted.
- Migration helper `migrate_legacy_live_submit_audit` drains existing
  legacy logs through the redaction contract into the new location.
- Tests confirm no plaintext NIF / URL path / token-shape value lands
  in the JSONL, even across multiple modelos.

### Cross-cutting design checks — PASS

- Pydantic v2 strict frozen at every boundary (every public model
  carries `ConfigDict(strict=True, frozen=True, extra="forbid")`).
- Per-record exclusive_file_lock on every save and migration step.
  Concurrent writers serialise per-record; cross-record contention
  is avoided by the per-id lock-target convention.
- Path-safety validators on every id input (draft_id, submission_id,
  amendment_id, csv, modelo) reject empty / dot-prefix / path-separator
  tokens before composition into the envelope filename. Defence in
  depth alongside the substrate's path-containment helpers.
- Classification gate at `load_envelope` refuses payloads whose
  recorded class drifted from the repository's expected class. Tests
  exercise the FINANCIAL/AUDIT gate at every repository.
- Zero-touch migration: every legacy plaintext consumer can be
  drained into the governed repository through a `migrate_legacy_*`
  helper. Re-runs are idempotent; partial migrations complete with
  unparseable rows counted under `errors`.

### Carried-forward (deferred per ADR) — DEFERRED

Per the wave-4 ADR's "Rationale" section (and per the wave-3 audit
gate's HIGH-1), envelopes carry plaintext payloads inside the
classification gate. Ciphertext-payload-at-rest layering is deferred
to a future ADR after the wave-4 plaintext envelopes are stable.
This is not a wave-4 regression; it is the explicit posture
inherited from wave 3, documented in both ADRs, and will be closed
by a dedicated ciphertext-wiring wave.

### No new HIGH/MEDIUM findings

This pass surfaced no new HIGH or MEDIUM findings. The redaction
discipline tests, classification-gate tests, path-safety tests, and
per-record lock tests all pass. The end-to-end integration test
walks every repository together and confirms the cross-repository
chain holds.

## Wave-5 inputs

The following are *carried forward* into wave 5 (observability +
run-trace redaction) rather than blocking wave 4:

- The substrate's `redact_structured` helper is now load-bearing for
  the live-submit audit sink; wave 5 will wire the same rule-set
  through every `aeat.core.observability` writer so run traces and
  diagnostic dumps inherit the same discipline.
- The legacy `aeat.adapters.outbound.aeat.export._audit.append_live_submit_audit` writer
  is preserved alongside the new governed sink so existing engine
  code paths continue to work; wave 5 will migrate the engine call
  sites to the governed sink and remove the legacy writer in the
  same change.
- The `_engine.py` submission writer (`_persist`,
  `_persist_amendment_result`) still writes plaintext JSON to
  `aeat_submissions_dir`; wave 5 / 6 will route those writes through
  the new `SubmissionRepository` and `FilingAmendmentRepository` so
  the engine's persist path is governed end-to-end.

## Decision

Wave 4 audit gate: **PASSED**. Wave 5 may proceed.

Closing reference: the rolling-wave loop continues. Open items above
are scoped explicitly so a future wave can pick them up; they are
not Wave-4 blockers.
