---
tags:
  - '#research'
  - '#secure-persistence-foundation'
date: '2026-04-30'
modified: '2026-04-30'
related:
  - "[[2026-04-30-secure-persistence-foundation-audit]]"
  - "[[2026-04-30-secure-persistence-foundation-adr]]"
---



# `secure-persistence-foundation` wave-5 research

## Question

Wave 4 closed the upstream HIGH-2 (live-submit log relocation) and
landed the filing-domain consumer adapters. Wave 5 must extend the
redaction discipline to the *other* on-disk consumers that today
write identity-bearing data verbatim:

- The run-trace JSONL sink (`aeat.core.observability._sink.JsonlRunSink`)
  writes `RunEvent` records that carry casilla form-fill values, AEAT
  navigation URLs, and free-form error messages. The model docstring
  is explicit that callers must trust themselves not to feed secrets
  in. Wave 5 makes that trust unnecessary.
- The submission engine persist paths (`_persist`,
  `_persist_amendment_result`) still write plaintext JSON to
  `aeat_submissions_dir`. The new `SubmissionRepository` and
  `FilingAmendmentRepository` exist as governance gates — the engine
  must now route through them.
- The legacy `aeat.adapters.outbound.aeat.export._audit.append_live_submit_audit` writer
  is preserved for backward compatibility with engine call sites; the
  governed `GovernedLiveSubmitAuditSink` exists as the relocation.
  The engine must migrate.

## Findings

### Run-trace JSONL sink emits sensitive payloads verbatim today

`JsonlRunSink.emit` calls `event.model_dump_json()` and writes the
result to disk. The `RunEvent` payload variants include:

- `FormFillPayload.value` — the casilla value, i.e. the operator's
  tax figure for a draft;
- `NavigationPayload.url` — AEAT sede URLs that may carry session
  identifiers in the path or query;
- `ErrorPayload.message` — free-form text that may include traceback
  fragments with file paths or captured user input.

The model docstring already warns that the JSONL is in scope for
sensitive data; there is no mechanism today that prevents an operator
or third-party caller from feeding a NIF straight into a form-fill
event.

### DIAGNOSTIC sensitivity class is the right tag

The default-policy comment on `SensitivityClass.DIAGNOSTIC` reads:
"scratch outputs, browser traces, screenshots, network captures.
Treatment: governed retention default (e.g. seven days); explicit
redaction; opt-in capture." Run traces fit there — they are
diagnostic artefacts, not legally-binding audit records.

### Submission engine persist paths still bypass repositories

`SubmissionEngine._persist` and `SubmissionEngine._persist_amendment_result`
write plaintext JSON via `target.write_text(filing.model_dump_json())`.
The new wave-4 `SubmissionRepository` and `FilingAmendmentRepository`
are the governance gates (envelope + classification + per-record lock).
Migrating the engine to use them is a code-only change — the on-disk
path moves from `<submissions_dir>/<id>.json` to
`<submissions_dir>/<id>.envelope.json`, and the migration helper from
wave 4 already drains the old path forward.

### Legacy audit writer is preserved for engine compatibility

`aeat.adapters.outbound.aeat.export._engine.SubmissionEngine` calls
`append_live_submit_audit(build_live_submit_audit_record(...))` at
three call sites: post-submit, post-failure, post-amendment. The
governed sink from wave-4 phase 5 has the same input contract
(`LiveSubmitAuditRecord`); migrating the engine call sites to the new
sink is a per-site change with the wave-4 migration helper handling
the legacy log drain.

## Dependencies

- Wave-4 governed sink (`GovernedLiveSubmitAuditSink`) — landed.
- Wave-4 repositories (`SubmissionRepository`, `FilingAmendmentRepository`)
  — landed.
- Substrate's `redact_structured` helper at AUDIT/DIAGNOSTIC class —
  landed in wave-3 close (commit `80ef8c3`).

No new substrate work is needed for wave 5; it is consumer-migration
work plus a redaction wrapper around `JsonlRunSink.emit`.

## Recommended scope

1. Wrap `JsonlRunSink.emit` so every event passes through
   `redact_structured(event_dict, rules=default_rules_for_class(
   SensitivityClass.DIAGNOSTIC))` before serialisation. The
   redaction discipline matches wave-4 phase 5; the only difference
   is the rule set (DIAGNOSTIC instead of AUDIT).
2. Migrate `SubmissionEngine._persist` to call
   `SubmissionRepository.save(filing)`.
3. Migrate `SubmissionEngine._persist_amendment_result` to call
   `FilingAmendmentRepository.save(result.amendment)` (storing the
   inner amendment record; the outer
   `AmendmentSubmissionResult` is a transport wrapper).
4. Migrate the three `append_live_submit_audit` call sites in
   `_engine.py` to the new `GovernedLiveSubmitAuditSink.append`.
5. Retain the legacy `_audit.py` writer functions as **deprecated**
   wrappers that delegate to the governed sink. Removing them
   outright would break any third-party caller that imports them.

## Out of scope

- Caches and corpora (Wave 6).
- Connector and export governance (Wave 7).
- Ciphertext-payload wiring for envelopes (separate ADR after wave-4
  envelopes are stable).
