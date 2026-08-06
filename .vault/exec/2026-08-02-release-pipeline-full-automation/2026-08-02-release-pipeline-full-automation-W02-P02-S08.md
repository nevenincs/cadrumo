---
tags:
  - '#exec'
  - '#release-pipeline-full-automation'
date: '2026-08-02'
modified: '2026-08-02'
body_schema: 'body-v1'
body_hash: 'sha256:e111ca730aeddcf091f11a295356d277127efc4c3a02451461bda023477c8fe2'
step_id: 'S08'
related:
  - "[[2026-08-02-release-pipeline-full-automation-plan]]"
---

# Add the fail-closed precondition refusing an orchestration when a claimed host-extension channel has no operator-minted claude evidence release, naming the emit_real_client_evidence capture command in the refusal, and never attempting to produce those four rows because the emit honesty guard refuses SDK-driven runs by design and defeating it would make the evidence a lie about what was installed, gate: uv run --no-sync pytest dev/packaging/tests -q -k precondition passes covering the unclaimed-channel pass, the claimed-and-supplied pass, and the claimed-and-absent refusal carrying the capture command in its message

## Scope

- `dev/packaging/publication_inputs.py`
- `dev/packaging/tests/test_publication_inputs.py`

## Description

Added `host_extension_precondition_refusal(descriptor, *, claude_evidence_release)` to `dev/packaging/publication_inputs.py`: refuses when a claimed host-extension channel (`claude-plugin`, `mcpb`) has no operator-minted claude evidence release, naming the exact `EMIT_REAL_CLIENT_EVIDENCE_COMMAND` (`uv run --no-sync python -m dev.packaging.emit_real_client_evidence`) capture verb in the refusal text. This is a standalone orchestration-ENTRY precondition, kept separate from the publish-dispatch `refusals()` demand machinery: it is meant to run before the bump or any other stage so the whole chain stops before a version is burned. Never attempts to produce the four claude-* rows itself — the honesty guard in `distribution_evidence_emit.py` refuses SDK-driven runs by design, and defeating it would make the evidence a lie about what was installed.

## Outcome

Gate green: `uv run --no-sync pytest dev/packaging/tests -q -k precondition` — 6 passed. Coverage: unclaimed host-extension channel passes regardless of the evidence-release value (including whitespace-only); claimed-and-supplied passes; claimed-and-absent refuses naming both the capture command and the claimed channel id; whitespace-only release treated as absent; both host-extension channels claimed together are both named in one refusal; a non-host-extension claim (scoop) never trips this precondition. Full-file selector `-k publication_inputs` also green: 23 passed.

## Notes

No incidents.
