---
tags:
  - '#audit'
  - '#secure-persistence-foundation'
date: '2026-04-30'
modified: '2026-04-30'
related:
  - "[[2026-04-30-secure-persistence-foundation-wave6-adr]]"
  - "[[2026-04-30-secure-persistence-foundation-wave6-research]]"
  - "[[2026-04-30-secure-persistence-foundation-wave5-audit]]"
---



# `secure-persistence-foundation` wave-6 audit gate | (**status:** `passed`)

## Summary

Wave 6 closes the LLM cache + usage log redaction gap:

- Phase 1 — `LLMCache.write` routes every cached entry through
  `redact_structured` at DIAGNOSTIC class before serialisation.
- Phase 2 — `UsageRecorder.record` routes every usage record through
  the same DIAGNOSTIC rule set before append.
- Phase 3 — This audit gate.

Test footprint: 7 new redaction-discipline tests. Existing LLM suite
(22 tests) and full unit-suite regression (3782 tests) green.

## Findings

### Carry-forwards from wave 5 — IN PROGRESS

The legacy `aeat.adapters.outbound.aeat.export._audit.append_live_submit_audit`
deprecation wrapper remains in place. No urgency to excise — the
governed sink is the engine's path; third-party callers are warned;
operators have a migration window.

The transport-level `AmendmentSubmissionResult` wrapper fields
remain dropped from on-disk persistence. No production reader has
emerged that would need them.

### Cross-cutting design checks — PASS

- DIAGNOSTIC-class rule reuse — explicit decision recorded in the
  ADR's Considerations section: the CACHE class default policy has
  an empty rule set, so the LLM cache borrows the DIAGNOSTIC rule
  set for *write-time redaction* while staying at CACHE class on
  the wire.
- Deferred imports preserved — both writers' storage imports are
  inside method bodies so the LLM package's import chain does not
  pull Alembic plugin discovery into CLI commands that never touch
  the cache or usage log. The wave-5 audit-gate's regression
  prevention discipline holds.
- Idempotent redaction — re-writing an already-redacted response
  through the cache does not double-encode the redaction. Confirmed
  by `test_idempotent_re_read`.
- The cache `read` path is unchanged — re-reads of an already-
  redacted entry return the redacted text. The cache hit semantics
  remain correct because the prompt hash key is computed from the
  ORIGINAL prompt (not the cached response), so a cache hit
  matches on prompt identity even though the response has been
  redacted.

### No new HIGH/MEDIUM findings

Wave-6 surfaced no new HIGH or MEDIUM findings. The redaction
discipline is verified end-to-end against NIF and bearer-token
canaries; the storage import is deferred so json-pipe-safety
holds; the cache round-trip via `model_validate_json` is exercised
in `test_cache_entry_remains_parseable`.

## Wave-7 inputs

The following are *carried forward* into wave 7 (connector + export
governance):

- Status cache redaction — `aeat.status` writes per-expediente
  status snapshots that may carry justificante CSV references and
  filing-history shape; same redaction wrapper pattern applies.
- Corpus integrity tracking — public reference material under
  `aeat_casillas_root` and `aeat_manuals_root` is plaintext at rest
  but the substrate's policy comment mandates SHA-256 tracking.
  Wave 7 will land a manifest format and a verification helper.
- Connector + export governance — when an operator exports
  `var/llm-cache/` for backup or audit transfer, the redacted
  on-disk content already meets the discipline. A future wave will
  formalise an export-bundle checksum manifest.

## Decision

Wave 6 audit gate: **PASSED**. Wave 7 may proceed.

The rolling-wave loop continues. Wave 7 picks up status cache +
corpus integrity + connector/export governance; the deferred
ciphertext-payload-wiring ADR remains on the roadmap as an
independent track.
