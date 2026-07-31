---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-12'
modified: '2026-07-12'
body_hash: 'sha256:ad37bfa9c10b3cb941659d4c7cda73ab2a889aca3f6fab981dca7685de10548e'
step_id: 'S08'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

# Codify that Cadrumo names the product and AEAT names the authority

## Scope

- `.vaultspec/rules/cadrumo-product-authority-names.md`

## Description

- Verify that no existing project rule covers the product-versus-authority
  naming boundary.
- Promote the completed rolling audit into a rule through the canonical rule
  CLI.
- Codify the ownership-and-referent test with concrete good and bad examples.
- Read the registered rule back through `vaultspec-core spec rules show`.

## Outcome

The standing rule now requires every application-owned surface to use Cadrumo
identity and permits AEAT names only for the Spanish authority, official
evidence, or external protocol. The rule is derived from the accepted rename
audit and explicitly prevents global textual replacement and stale product
aliases.

## Notes

The plan's provisional scope named a `.codex/rules` path. The canonical
`vaultspec-core vault rule promote` workflow owns project rules under
`.vaultspec/rules`; execution followed that authority rather than hand-writing
the provisional path. No production code changed.
