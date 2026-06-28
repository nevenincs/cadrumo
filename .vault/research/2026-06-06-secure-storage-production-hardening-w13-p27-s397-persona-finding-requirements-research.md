---
tags:
  - '#research'
  - '#secure-storage-production-hardening'
date: '2026-06-06'
modified: '2026-06-06'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-06-secure-storage-production-hardening-w13-p27-s396-persona-readiness-reconciliation-audit]]'
  - '[[2026-05-21-fresh-cli-persona-findings-inventory-audit]]'
  - '[[2026-05-21-fresh-cli-persona-capability-gap-design-research]]'
  - '[[2026-05-22-secure-storage-production-hardening-architecture-adr]]'
  - '[[2026-05-22-secure-object-integrity-attribution-plan]]'
---

# `secure-storage-production-hardening` research: `S397 persona finding research requirements`

This research records the evidence requirements that remain after the S396 persona readiness ownership reconciliation. It is intentionally a requirements note rather than a repair design: S398 owns final classification, S399 owns retest dispatch, and S400 owns any new secure-storage repair rows.

## Findings

### 1. FRESH-004 is a discoverability gap, not a secure-storage requirement on current evidence

The persona finding expected an `aeat app manual` route. Current evidence instead shows registry-owned manual and source surfaces under `aeat app registry`, with formula explanation already carrying legal and source identifiers. The prior capability-gap design kept manual/source drill-down conservative and did not assign profile-bound storage ownership.

Research requirement for S398:

- Confirm whether the desired outcome is a CLI alias/discovery bridge, command-help guidance, or richer formula-output hints.
- Confirm that any source-reference drill-down uses registry/manual authority surfaces rather than profile-bound storage.
- Do not assign FRESH-004 to secure-storage unless a fresh retest proves the missing route blocks storage readiness, repair, or profile-bound evidence recovery.

### 2. FRESH-007 requires capability-surface classification before repair work

The persona finding asked for an explicit "applies because" explanation after profile creation. Existing research identifies `aeat app overview explain MODELO --year YYYY` and overview calendar as the canonical applicability surfaces. The application and CLI surfaces exist and expose rationale, legal references, relevant profile facts, and applicability verdicts. The remaining question is whether profile-create or profile-edit success output should point operators to those overview surfaces.

Research requirement for S398:

- Treat the primary owner as CLI workflow or capability-plan work unless a retest shows `overview explain` cannot read the current profile through the secure-storage runtime.
- If a repair row is needed, require it to preserve the existing overview ownership of applicability reasoning and only change post-profile guidance or discovery text.
- Retest with isolated scratch roots and real profile creation so stored profile/runtime behavior is exercised rather than inferred.

### 3. FRESH-011 is secure-storage-owned but already has architectural backing

The readiness failure came from an undecryptable stored draft object in shared local state. The secure-storage architecture ADR already requires storage readiness to become an API result, default listing to fail closed for governed namespaces, and filing-grade output to block when required namespaces are degraded. The secure-object integrity plan already records unreadable-row attribution and fail-closed repair diagnostics. The current secure-storage repair privacy rows add real-custody repair roundtrips for unreadable-row reporting, quarantine preview, mutation, and redacted logs.

Research requirement for S399/S400:

- Retest unreadable stored-draft readiness in an isolated scratch root with real custody and encrypted secure-object rows.
- Require metadata-only diagnostics and redacted operator output; no payload, raw profile UUID, bucket id, taxpayer id, object key, or passphrase disclosure.
- If retest fails, S400 must add a secure-storage repair row tied to readiness degradation or repair diagnostics rather than Modelo 111 business logic.

### 4. REPAIR-PROFILE-PRIVACY-001 is verification-only for this wave

The repair-profile privacy finding was secure-storage-owned and already remediated by redacted health payloads and real CLI privacy regressions. S397 does not identify a new architectural gap.

Research requirement for S399/S401:

- Include profile-repair privacy in testimonial synthesis only as a regression check.
- Escalate to S400 only if retest output leaks raw profile, bucket, object-key, taxpayer, or passphrase material.

### 5. S398 classification rule

S398 should classify each unresolved persona finding by the surface that owns the operator outcome:

- secure-storage: unreadable stored objects, repair privacy, route binding, custody readiness, storage degradation, and filing-grade blocking.
- CLI workflow: command placement, aliasing, help discoverability, post-profile next-action text, and persona route vocabulary.
- capability plan: missing source-backed business capability, missing registry/manual corpus capability, or explanation surfaces that exist architecturally but need product exposure.
- separate plan: broad capability work that is not required to complete secure-storage runtime rollout.

No S400 implementation row should be added from S397 alone. It needs an S398 classification and, for secure-storage-owned findings, S399 retest evidence.
