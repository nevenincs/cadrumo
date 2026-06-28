---
tags:
  - '#adr'
  - '#secure-persistence-foundation'
date: '2026-04-30'
modified: '2026-04-30'
related:
  - "[[2026-04-30-secure-persistence-foundation-wave5-research]]"
  - "[[2026-04-30-secure-persistence-foundation-audit]]"
  - "[[2026-04-30-secure-persistence-foundation-adr]]"
---



# `secure-persistence-foundation` wave-5 adr | (**status:** `accepted`)

## Problem statement

Wave 4 landed the filing-domain consumer adapters and relocated the
live-submit audit sink so the upstream HIGH-2 finding closed.
Wave 5 closes three carry-forwards from the wave-4 audit gate:

1. The run-trace JSONL sink writes identity-bearing payloads
   (form-fill casilla values, AEAT navigation URLs, free-form error
   messages) verbatim. The substrate's `redact_structured` helper
   exists; the sink must use it.
2. The submission engine still calls `target.write_text(...)` to
   persist `SubmittedFiling` and `AmendmentSubmissionResult`
   records. The wave-4 repositories are the governance gates — the
   engine must route through them.
3. The legacy `append_live_submit_audit` writer at
   `.aeat/live-submit-audit.log` is preserved for backward
   compatibility. Three engine call sites still target the legacy
   path; they must migrate to the wave-4 governed sink.

## Considerations

Architectural drivers:

- Run traces are DIAGNOSTIC class per the substrate's default policy
  table. The redaction rule set for DIAGNOSTIC mirrors AUDIT — NIF
  hashing, URL host-only, bearer-shape fingerprinting, opaque-bearer
  fingerprinting. The wave-4 audit-sink work demonstrated that wrapping
  the emit path in `redact_structured(event_dict, rules=...)` is a
  one-line change at the writer.
- The wave-4 repositories were designed with this migration in mind.
  Both `SubmissionRepository.save` and `FilingAmendmentRepository.save`
  accept the same payload shape the engine already builds; the engine
  change is a substitution of the writer, not a refactor.
- Removing the legacy `_audit.py` writer outright would break any
  third-party caller that imports it. Wave 5 keeps the symbols but
  delegates to the governed sink so the migration is safe.

## Constraints

- Python 3.13+, Windows-supported. No new runtime dependencies.
- Pydantic v2 strict frozen at every boundary.
- Trilingual error envelope contract preserved.
- No mocks; tests use real on-disk persistence + CliRunner.
- Coverage floor 60% on `src/aeat` preserved.
- Live AEAT submission permanently forbidden — wave 5 does not touch
  the gate logic.
- No new GH issues; #216 absorbs everything.

## Implementation

### Phase 1 — Run-trace redaction discipline

Wrap `aeat.core.observability._sink.JsonlRunSink.emit` so every event passes
through `redact_structured(event.model_dump(mode="json"), rules=
default_rules_for_class(SensitivityClass.DIAGNOSTIC))` before write.
The rule set is the DIAGNOSTIC default — same shape as the AUDIT
default but registered separately so per-class policy edits do not
cross-contaminate.

The sink continues to receive a typed `RunEvent` from the logging
filter; redaction operates on the dumped dict, not the model. The
serialised JSONL line is the redacted dict re-encoded via `json.dumps`
(same as the wave-4 governed sink — gives sorted keys for
determinism).

Tests confirm:

- A form-fill event with a NIF-shaped value redacts to a SHA256-prefix.
- A navigation event with a session-bearing URL host-only-redacts.
- An error event with a bearer-shaped token fingerprints the token.

### Phase 2 — Submission engine persist migration

`SubmissionEngine._persist` is rewritten to:

```
repository = SubmissionRepository(store_dir=self.settings.aeat_submissions_dir)
repository.save(filing)
```

`SubmissionEngine._persist_amendment_result` is rewritten to use
`FilingAmendmentRepository(store_dir=self.settings.aeat_submissions_dir / "amendments")`
and call `.save(result.amendment)`.

The legacy plaintext path (`<submissions_dir>/<id>.json`) is no longer
written. The wave-4 migration helper already drains operator data
forward.

### Phase 3 — Engine audit-sink migration

The three `append_live_submit_audit(build_live_submit_audit_record(...))`
calls in `_engine.py` are replaced with:

```
sink = GovernedLiveSubmitAuditSink(audit_dir=self.settings.aeat_audit_dir)
sink.append(build_live_submit_audit_record(...))
```

The legacy `_audit.py` symbols (`append_live_submit_audit`,
`build_live_submit_audit_record`, `LiveSubmitAuditRecord`) are kept as
public exports. `append_live_submit_audit` becomes a deprecated
wrapper that emits a `DeprecationWarning` and delegates to the
governed sink so any third-party caller continues to work.

### Phase 4 — Wave-5 audit gate

Identical contract to waves 1-4. Test footprint check, regression
sweep, write the audit-gate report, capture any HIGH/MEDIUM as wave-6
inputs.

## Rationale

The phase ordering puts the run-trace redaction first because it is
the highest-risk surface (form-fill values land daily; the audit log
fires only on live-submit). Phases 2 and 3 are mechanical engine
migrations whose correctness is already pinned by the wave-4
repository tests and the governed-sink redaction tests.

The deprecation wrapper for `append_live_submit_audit` preserves the
public surface so a downstream caller never gets a breaking import.
Operators still get the relocation benefit because the wrapper
delegates to the governed sink — there is no path through which a
caller writes outside the configured audit dir.

## Consequences

Positive:

- Run traces inherit the wave-4 redaction discipline end-to-end. The
  trust-the-caller posture in the model docstring becomes a
  defence-in-depth posture: the substrate redacts even if a caller
  forgets to.
- The submission engine persist path is governance-gated end-to-end.
  Future ciphertext-payload wiring lands in one place
  (`SubmissionRepository.save`) instead of two.
- The legacy audit log path is no longer reachable from inside the
  project — the deprecation wrapper guarantees every write passes
  through the governed sink.

Negative:

- The deprecation wrapper is a temporary maintenance load until a
  future wave excises it cleanly. Wave 5 records the wrapper in the
  ADR so the future wave can find it.

Neutral:

- No new runtime dependencies.
- No Alembic migration.
- The deferred-import pattern from wave 3 carries forward.

## Out of scope

- Caches and corpora (Wave 6).
- Connector + export governance (Wave 7).
- Ciphertext-payload wiring for envelopes (separate ADR).
- IDENTITY-class records in the secret store widening (separate ADR).
