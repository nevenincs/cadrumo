---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S87'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

# Remediate the authority-lock review and reopen contradicted downstream acceptance contracts

## Scope

- `.vault/adr/2026-07-12-cadrumo-cli-executable-adr.md`
- `.vault/plan/2026-07-12-cadrumo-product-rename-plan.md`
- `.vault/audit/2026-07-13-cadrumo-product-rename-authority-lock-audit.md`
- `.vault/exec/2026-07-12-cadrumo-product-rename/2026-07-12-cadrumo-product-rename-W01-P02-S87.md`

## Description

- Amend the superseding ADR to declare both operator overrides and the complete
  exact product, command, machine-identity, companion, and agency matrix.
- Refresh the ADR modified stamp and markdown hygiene through feature-scoped
  Vaultspec checks.
- Reopen every checked implementation or acceptance Step contradicted by direct
  live-file evidence under the binding `aeat` and CADRUMO contract.
- Preserve closed Steps whose lowercase `cadrumo` values are correct machine
  identifiers rather than human commands or display copy.
- Leave the independent audit at FAIL until a reviewer verifies this remediation.

## Outcome

The accepted ADR now explicitly overrides both the parent decision's title-case
display spelling and its human executable. It records CADRUMO as the display
name, `aeat` as the only human executable, the complete lowercase `cadrumo`
machine-identity family, `cadrumo-mcp`, `CADRUMO_`, both companion distribution
names, `cadrumo_data`, and AEAT as the Spanish authority.

The plan no longer claims completed behavior that the current tree does not
provide. The following 24 Steps are open again: `S25`, `S37` through `S40`,
`S43`, `S45`, `S48` through `S55`, `S57`, `S58`, `S62` through `S67`, and
`S78`. They cover the stale runtime CLI, installed-artifact probes, product copy
and generated integration surfaces, developer automation, locale authorities,
and the aggregate real-behavior gate.

## Notes

Read-only inspection preserved closed machine-identity Steps where the accepted
lowercase `cadrumo` contract is already true: distribution and extras metadata,
MCP resource and tool identifiers, client handshake, publication distribution
choices, `cadrumo-mcp` evaluation, release parsing, and compatibility absence.

The review audit is intentionally unchanged. Its findings are remediation input,
not self-resolving task state; independent re-review must decide whether the FAIL
verdict can be replaced.
