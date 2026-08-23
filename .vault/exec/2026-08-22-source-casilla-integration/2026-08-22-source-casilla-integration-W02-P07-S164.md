---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:cc5aa0ee704c3ea4bfc347175026152de1c2c700fbe27806a4d6172ab14a832c'
step_id: 'S164'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---




# propagate complete acquisition-cost facts through inventory application and operator ingress

## Scope

- `src/cadrumo/application/inventory`
- `src/cadrumo/entrypoints/cli`

## Description

- Propagate the complete acquisition envelope through the application command and a domain-owned purchase-movement factory.
- Replace rival purchase amount and IVA ingress with an explicit stdin-only structured channel.
- Redact evidence identities and content digests from ordinary inventory output while retaining audited cost totals and completeness counts.
- Enroll the stdin flag in the command registry and author all four locale strings through the locale authority.
- Hard-cut application, CLI, and payload fixtures to schema version 2 and the complete purchase contract.

## Outcome

Purchase movements now require one typed complete acquisition envelope, refuse the legacy unit-cost, taxable-base, and IVA-rate authorities, and preserve every domain-validated component and completeness fact into encrypted persistence. Operator output carries no evidence reference or content digest. Focused domain, application, CLI, command-schema, locale, Ruff, and ty gates passed. Independent formal review reported no remaining high or medium findings.

## Notes

The initial inline-JSON design was rejected during review because process arguments and ordinary output exposed evidence metadata. It was replaced before commit with stdin-only ingress and a safe output projection. Generated documentation was intentionally left to its CLI-owned later step. Unrelated shared-worktree changes were preserved.
