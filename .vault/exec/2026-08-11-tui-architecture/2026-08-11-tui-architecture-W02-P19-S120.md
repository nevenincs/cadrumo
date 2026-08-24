---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:755027d6a6821219e04a9caf52ac199e0011a96fdc8b99af5ec467a1fc7671c8'
step_id: 'S120'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---
# Implement registered safe REVIEW resolution and typed Workspace-refresh-target resolution with exact version, definition-digest, schema, expiry, terminal-state, and output validation while preserving separate response authority and rejecting caller-supplied result references

## Scope

- `src/cadrumo/application/operations/_projection_services.py`
- `src/cadrumo/application/operations/_registry.py`
- `src/cadrumo/application/operations/_supervisor.py`
- `src/cadrumo/application/operations/__init__.py`
- `src/cadrumo/application/operations/tests/test_projection_services.py`

## Description

- Added the canonical safe REVIEW resolver over atomic observation, immutable registry registration, and encrypted secure-reference ports.
- Added exact private reviewed-operand model registration so REVIEW resolution never guesses a secure payload type or publishes it in the public manifest.
- Added the canonical typed Workspace refresh-target resolver over authoritative successful terminal receipts; the request contains no caller result reference.
- Added version-dispatched response-control, cancellation, and detach services with a narrow supervisor port and closed renderer-neutral refusals.
- Added a runtime-only bound response authority that verifies the exact bearer digest, actor, invocation, interaction, revision, proposal, expiry, and permitted REVIEW intents and zeroizes its owned token buffer on close.
- Carried the caller's expected cancellation revision into the supervisor mutation boundary and mapped a losing compare-and-swap race to `stale_operation_revision` after an authoritative re-read.
- Added exact registry lookup services and direct facade exports without frontend, domain, persistence-adapter, or Workspace imports.
- Added real filesystem journal, lease, supervisor, fresh-reader, and encrypted secure-object tests for success, version, unknown operation, pending state, expiry, contract-digest drift, schema drift, terminal state, unavailable adapter, wrong registered output, bearer loss, cancellation races, detach, and token non-retention.
- Ran semantic and exact fixed-point censuses; retained only the supervisor's canonical low-level mutation methods and executor-owned secure operand resolution as intentional internal authorities.

## Outcome

`_projection_services.py` is the sole public service home for safe REVIEW projection, typed Workspace refresh targeting, response-control availability, cancellation, and detach. REVIEW registrations now bind one strict frozen private operand model at runtime while keeping that type out of the serializable public contract. All service boundaries validate current schema identity and definition digest, collapse raw failures to endpoint-specific typed refusals, and return no tokens, secure references, adapter paths, repository DTOs, or raw exceptions.

Focused Ruff and BasedPyright checks pass. The final focused registry, observation, facade, and projection-service suite passes 59 tests. The complete operation package passes 267 unit and 70 integration tests, including all 50 real supervisor integration tests. Independent review approved the step with no open findings.

## Notes

Production registry and entrypoint composition remains intentionally outside this step and is owned by `W02.P19.S122`. No compatibility shim, re-export module, duplicate public resolver, direct frontend supervisor call, mock, fake, monkeypatch, skipped test, or xfail was introduced. The canonical facade export is a direct public boundary, not a legacy alias. The repository-wide Vaultspec check remains red on unrelated pre-existing malformed UTF-8/frontmatter and historical corpus warnings; the S120 exec and audit records were both authored and attested through the Vaultspec CLI.
