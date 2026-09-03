---
tags:
  - '#research'
  - '#observability-replay-retirement'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:c02b3fd8bdb7198dd2d2e3308059bcec28ca588b5b922605226c062247bfa352'
related: []
---

# `observability-replay-retirement` research: `generic captured-argv replay`

The live tree has retired generic `replay_run`; what remains is a redacted run-trace/audit facility plus a hermetic deterministic-output substrate. The evidence separates historical-argv re-entry from deterministic-output assurance: the former reconstructed an unbounded command against current ambient state, while the latter uses explicit synthetic inputs, frozen time, narrow masking, typed full-envelope comparison, and scenario-specific state assertions. The ADR must decide whether retirement becomes permanent and reconcile the two accepted records that still require the former runner.

## Findings

### Generic argv re-entry was not hermetic

The retired runner reconstructed positional and flag records, but recovered `ENV`, `CONFIG`, and `DEFAULT` values from the current environment. Its only pre-invocation refusals were corpus-hash drift and a two-name obsolete-write-flag denylist; it neither resolved the entrypoint through current command authority nor confined execution to synthetic/read-only scenarios. `commit ac0e7fff6c^:src/cadrumo/core/observability/replay.py:55-117`, `commit ac0e7fff6c^:src/cadrumo/core/observability/replay.py:174-192`.

The runner constructed current `Settings()` and re-entered CLI dispatch, whose preflight resumes or authenticates the currently selected profile. A historical trace was not a sealed input or credential capsule. `commit ac0e7fff6c^:src/cadrumo/core/observability/replay.py:183-225`, `src/cadrumo/entrypoints/cli/_profile_authentication_gate.py:157-251`, `src/cadrumo/entrypoints/cli/_command_runtime.py:205-224`.

The trace is a redacted diagnostic artifact, not executable secret storage. Producers must redact secret-named arguments; persistence applies DIAGNOSTIC redaction and retains a certificate fingerprint rather than credentials. `src/cadrumo/core/observability/models.py:16-79`, `src/cadrumo/core/observability/models.py:369-400`, `src/cadrumo/core/observability/store.py:180-185`. The optional `db_sha256` check ran after invocation and only for hermetic roots, so it supplied no current-state precondition. `commit ac0e7fff6c^:src/cadrumo/core/observability/replay.py:149-158`, `commit ac0e7fff6c^:src/cadrumo/core/observability/replay.py:233-256`.

### Output assurance needs capture fidelity, not execution fidelity

The accepted substrate stores the verbatim emitted, CLI-redacted `SchemaEnvelope`, applies canonicalisation and a narrow mask at comparison time, and compares the full envelope. Golden inputs remain synthetic; state fingerprints are limited to hermetic write scenarios. `.vault/adr/2026-06-30-deterministic-output-replay-substrate-adr.md:20-41`.

The residual ADR makes load-bearing identifiers deterministic rather than masked and runs enrolled cases under frozen time and injected identity; the axis owns neither arbitrary trajectory execution nor live AEAT calls. `.vault/adr/2026-07-01-determinism-replay-residual-adr.md:62-138`. The live comparison primitive and anti-tautology tests enforce the residual mask. `src/cadrumo/tests/golden_comparison.py:60-240`, `src/cadrumo/core/observability/tests/test_golden.py:206-243`.

### Bounded synthetic consumers provide the intended assurance

The determinism axis explicitly enrols `ledger.add` and `ledger.evidence.add` against real repositories inside isolated profiles and a frozen clock. It compares full envelopes; the retried add also checks committed-state identity. Unenrolled JSON commands remain visible coverage gaps. `src/cadrumo/entrypoints/cli/tests/test_determinism_conformance.py:1-18`, `src/cadrumo/entrypoints/cli/tests/test_determinism_conformance.py:60-71`, `src/cadrumo/entrypoints/cli/tests/test_determinism_conformance.py:173-306`.

Observability does not require replay authority: `run_context` records a trace and persists the last emitted envelope while trace/event persistence applies diagnostic redaction. `src/cadrumo/core/observability/context.py:229-307`, `src/cadrumo/core/observability/store.py:245-278`, `src/cadrumo/core/observability/store.py:338-366`. Focused current gates reported 14 passed.

### The options carry different authority costs

- Restore generic captured-argv replay: preserves historical re-entry provenance, but requires a closed command allowlist, sealed synthetic inputs, explicit credential posture, and pre- plus post-state gates.
- Retain hermetic capture/canonicalise/mask/compare: matches the current implementation and the assurance core of both determinism ADRs, at the cost of deliberate scenario authorship and incomplete but visible coverage.
- Add future capability-specific replay: store typed inputs and outcomes rather than execute diagnostic traces. Current CLI authority rejects duplicate `modelo audit replay` and requires explicit safety classification for every live leaf. `src/cadrumo/entrypoints/cli/tests/test_audit_verbs.py:144-156`, `.vault/adr/2026-07-28-cli-authority-verb-conformance-adr.md:66-124`.

## Sources

- `.vault/adr/2026-06-30-deterministic-output-replay-substrate-adr.md:20-41`
- `.vault/adr/2026-07-01-determinism-replay-residual-adr.md:62-138`
- `.vault/adr/2026-07-28-cli-authority-verb-conformance-adr.md:66-124`
- `commit ac0e7fff6c`
- `commit ac0e7fff6c^:src/cadrumo/core/observability/replay.py:55-256`
- `src/cadrumo/core/observability/models.py:16-400`
- `src/cadrumo/core/observability/context.py:229-307`
- `src/cadrumo/core/observability/store.py:180-366`
- `src/cadrumo/tests/golden_comparison.py:60-240`
- `src/cadrumo/core/observability/tests/test_golden.py:206-243`
- `src/cadrumo/entrypoints/cli/tests/test_determinism_conformance.py:1-306`
- `src/cadrumo/entrypoints/cli/_profile_authentication_gate.py:157-251`
- `src/cadrumo/entrypoints/cli/_command_runtime.py:205-224`
- `src/cadrumo/entrypoints/cli/tests/test_audit_verbs.py:144-156`
