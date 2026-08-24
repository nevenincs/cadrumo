---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:0daad133115e83ee9cea4e011d1bd78e62a70cbf912a7a19def4cd191e3aa1c1'
step_id: 'S128'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---
# Classify operator-reachable outbound-storage validation carriers

## Scope

- `src/cadrumo/adapters/outbound/storage/_key_validation.py`
- `src/cadrumo/adapters/outbound/storage/_factory.py`
- `src/cadrumo/adapters/outbound/storage/_local.py`
- `src/cadrumo/adapters/outbound/storage/_google_drive.py`
- `src/cadrumo/adapters/outbound/storage/tests`

## Description

- Census every validation-error construction in the declared storage modules.
- Attach canonical fact-only operator-decision verdicts to operator-reachable provider, key, namespace, content-hash, path, and configuration refusals.
- Use runtime-observation provenance for call/provider observations and application-state provenance for loaded factory configuration.
- Exclude only the enum-exhaustion branch proven unreachable by complete ProviderKind coverage.
- Add an exact AST totality gate and co-located machine-contract tests with redacted facts.

## Outcome

Seventeen of eighteen validation sites are operator-reachable and now carry canonical `OPERATOR_DECISION` no-action verdicts. Evidence contains only backend, field, configured/valid state, and provenance; supplied keys, paths, configuration values, and secrets are not exposed. The remaining factory branch is mechanically proven unreachable because the preceding parser returns the closed `ProviderKind` enum and every enum member is handled.

The totality gate matches the production census exactly and rejects direct verdict/evidence construction. Focused validation and storage partitions pass 105, 71, 71, and 41 tests. Scoped Ruff and diff checks pass. Independent review confirmed no S126 network/HTTP/integrity encroachment.

## Notes

- VaultSpec RAG grounded the shared public no-action helper as the only verdict-construction authority in this scope.
