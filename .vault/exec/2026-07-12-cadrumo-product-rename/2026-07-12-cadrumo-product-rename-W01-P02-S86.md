---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S86'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

# Reconcile the binding CADRUMO product, aeat human CLI, and AEAT authority naming contract

## Scope

- `.vault/adr/2026-07-12-cadrumo-cli-executable-adr.md`
- `.vault/plan/2026-07-12-cadrumo-product-rename-plan.md`
- `.vaultspec/rules/cadrumo-product-authority-names.md`
- `generated provider naming rules`
- `src/cadrumo/core/product_identity.py`
- `src/cadrumo/core/tests/test_product_identity.py`

## Description

- Restore the accepted executable decision as an active plan authority.
- Correct the canonical identity tuple to display `CADRUMO` and execute through
  the sole human command `aeat`.
- Preserve lowercase `cadrumo` for package, distribution, repository, plugin,
  MCP, and companion identifiers and preserve AEAT for the Spanish authority.
- Promote and sync the referent-aware naming contract without authorising blind
  token replacement.
- Verify the immutable identity contract and the plan, rule, and vault structures.

## Outcome

The active authority chain now states one unambiguous contract: CADRUMO is the
product display name, `aeat` is its only human CLI executable, `cadrumo` remains
the Python and machine-identity root, `cadrumo-mcp` remains the distinct MCP
executable, and AEAT remains the Spanish tax authority.

The plan links the accepted executable ADR, corrects its command and casing
claims, and records this reconciliation as `W01.P02.S86`. The promoted source
rule, its four generated provider copies, and the immutable runtime identity
contract project the same tuple. No downstream CLI implementation, locale,
packaging, documentation, MCP, persistence, or generic Python error surface was
changed in this Step.

## Notes

The identity source and its focused test already contained uncommitted
`cli_executable="aeat"` overlap when this Step began. That overlap matched the
accepted executable decision and was preserved; this Step added the binding
CADRUMO display casing and reconciled the governing records around it.

Historical quoted commit text remains byte-faithful where it records the former
title-case spelling. Downstream surfaces remain intentionally open for separate
path-owned Steps and review.
