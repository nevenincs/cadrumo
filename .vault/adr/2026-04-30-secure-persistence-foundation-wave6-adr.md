---
tags:
  - '#adr'
  - '#secure-persistence-foundation'
date: '2026-04-30'
modified: '2026-04-30'
related:
  - "[[2026-04-30-secure-persistence-foundation-wave6-research]]"
  - "[[2026-04-30-secure-persistence-foundation-wave5-audit]]"
---



# `secure-persistence-foundation` wave-6 adr | (**status:** `accepted`)

## Problem statement

Wave 5 closed the run-trace + submission-engine carry-forwards.
Wave 6 closes the next class of consumer that today writes
identity-bearing data without the substrate's redaction gate: the
LLM cache and usage log.

Both writers persist response text that may echo NIF / counterparty
context from the prompt. The substrate's `redact_structured` helper
already exists; the writers must use it.

## Considerations

Architectural drivers:

- The LLM cache is CACHE class per the substrate's default-policy
  table — public reference data that may carry identity-bearing
  caches; the policy comment notes "identity-bearing caches escalate
  to IDENTITY". The CACHE default policy has an empty rule set; wave
  6 therefore borrows the DIAGNOSTIC rule set (NIF / URL / token
  fingerprinting) rather than upgrading the whole cache to IDENTITY
  (which would pull ciphertext-at-rest into a prerequisite, blocked
  by the ciphertext-wiring ADR's deferral). The cache stays at CACHE
  class on the wire; the *redaction* discipline is borrowed from
  DIAGNOSTIC.
- The usage log is DIAGNOSTIC class — same rule set the wave-5 sink
  uses for run traces.
- Redaction at write is *idempotent*: re-reading an already-redacted
  entry returns the same redacted string the rules produce on its
  re-application, so the cache hit path stays correct.

## Constraints

- Python 3.13+, Windows-supported. No new runtime dependencies.
- Pydantic v2 strict frozen at every boundary.
- No mocks; tests use real on-disk persistence.
- Coverage floor 60% on `src/aeat` preserved.
- No new GH issues; #216 absorbs everything.
- Storage imports must remain *deferred* to preserve the CLI
  json-pipe-safety contract (per the wave-5 audit-gate finding).

## Implementation

### Phase 1 — LLM cache redaction discipline

`LLMCache.write` is wrapped so every cached entry passes through
`redact_structured(entry.model_dump(mode="json"), rules=
default_rules_for_class(SensitivityClass.DIAGNOSTIC))` before
serialisation. The redacted dict is then re-encoded via
`json.dumps(..., indent=2)` and written to the same content-addressed
path. The DIAGNOSTIC rule set is used (rather than CACHE) because the
CACHE default policy has an empty rule set — see the Considerations
section above for the rationale. The storage import is deferred
inside the write method body to preserve the CLI json-pipe-safety
contract.

Tests confirm:

- A NIF canary in the synthetic LLM response text never lands in the
  on-disk JSON.
- A bearer-shape token in the response is fingerprinted.
- The cache `read` returns the redacted text (idempotent re-read).

### Phase 2 — LLM usage log redaction discipline

`UsageRecorder.record` is wrapped so every usage record passes
through `redact_structured(record.model_dump(mode="json"), rules=
default_rules_for_class(SensitivityClass.DIAGNOSTIC))` before append.
The encoded line is written to the same daily JSONL path.

Tests confirm:

- A NIF canary in the synthetic record's `text` field never lands in
  the on-disk JSONL.
- The append-only contract is preserved (one line per record;
  parseable JSON per line).

### Phase 3 — Wave-6 audit gate

Identical contract to waves 1-5.

## Rationale

The phase ordering takes the LLM cache first because cache hits are
the cheapest re-read path; locking down the on-disk content at write
prevents leakage across re-imports and across operator workstations
(an operator who archives `var/llm-cache/` for backup will not be
exporting plaintext NIFs).

## Consequences

Positive:

- LLM cache + usage log inherit the substrate's redaction discipline
  end-to-end. The trust-the-caller posture in the LLM contract
  becomes a defence-in-depth posture: the substrate redacts even if
  a caller forgets to.
- Future ciphertext-payload wiring lands in the same place
  (`LLMCache.write` / `UsageRecorder.record`); wave 6 prepares the
  ground.

Negative:

- Cache-key prompt hashing is unchanged — the *prompt* is still
  hashed verbatim before persistence (it is the cache's primary key,
  not stored content). Operators inspecting the on-disk file
  structure can still infer prompt frequency by counting hash files
  but cannot recover the prompt text. This matches the wave-1
  substrate posture for content-addressed blobs.

Neutral:

- No new runtime dependencies.
- No Alembic migration.
- The deferred-import pattern from wave 3 carries forward.

## Out of scope

- Status cache redaction (Wave 7).
- Corpus integrity tracking (separate ADR after wave 7).
- Connector + export governance (Wave 7).
- Ciphertext-payload wiring for envelopes (separate ADR).
- IDENTITY-class records in the secret store widening (separate ADR).
