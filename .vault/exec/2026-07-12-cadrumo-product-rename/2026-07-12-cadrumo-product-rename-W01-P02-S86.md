---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-13'
modified: '2026-07-13'
body_hash: 'sha256:101f11f3dcbe8a2e1513e5b80c9628042851fc597e787ab1622ba1bba6132d76'
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

The active authority chain now states one referent-aware contract: `Cadrumo` is
used in sentence prose and `CADRUMO` in identity contexts; `aeat` is its only
human CLI executable; `cadrumo` remains the Python and machine-identity root;
`cadrumo-mcp` remains the distinct MCP executable; and AEAT remains the Spanish
tax authority.

The plan links the accepted executable ADR, restores its ratified prose/identity
casing note, and records this reconciliation as `W01.P02.S86`. The promoted
source rule, its four generated provider copies, and the immutable runtime identity
contract project the same tuple. No downstream CLI implementation, locale,
packaging, documentation, MCP, persistence, or generic Python error surface was
changed in this Step.

## Notes

The committed identity source and its focused test already matched the complete
binding tuple when this Step began, including `display_name="CADRUMO"`,
`cli_executable="aeat"`, and `mcp_executable="cadrumo-mcp"`. They therefore
required verification rather than modification.

Historical quoted commit text remains byte-faithful where it records the former
title-case spelling. Downstream surfaces remain intentionally open for separate
path-owned Steps and review.

## Evidence correction from S87

The earlier claim that the runtime authority proved the complete contextual
casing tuple was too broad: `display_name="CADRUMO"` proved the identity-context
value only. S87 adds the distinct consumable `prose_name="Cadrumo"` contract and
a direct test of both values without changing the display identity.
