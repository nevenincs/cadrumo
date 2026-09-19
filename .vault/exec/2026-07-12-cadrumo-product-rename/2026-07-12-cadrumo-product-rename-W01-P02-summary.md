---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-12'
modified: '2026-07-12'
body_hash: 'sha256:eb8e54cc451241082521d0f29c0659ebc58a49ef1334eef4e79cbc1001abcb14'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

# `cadrumo-product-rename` `W01.P02` summary

Phase W01.P02 created the canonical Cadrumo runtime identity, exposed it through
the core facade, proved its public contract, and codified the product-versus-AEAT
boundary as a standing project rule.

- Created: `src/cadrumo/core/product_identity.py`
- Created: `src/cadrumo/core/__init__.py`
- Created: `src/cadrumo/core/tests/test_product_identity.py`
- Created: `.vaultspec/rules/cadrumo-product-authority-names.md`
- Created: S05 through S08 Step Records
- Modified: `.vault/plan/2026-07-12-cadrumo-product-rename-plan.md`
- Modified: `.vault/audit/2026-07-12-cadrumo-product-rename-audit.md`

## Description

`PRODUCT_IDENTITY` is an immutable, import-light value covering the accepted
display, package, distribution, CLI, repository, MCP, plugin, environment,
companion-distribution, and companion-namespace tuple. `IdentityReferent`
provides the closed Cadrumo-product versus AEAT-authority vocabulary, and
`AEAT_AUTHORITY_SHORT_NAME` explicitly retains the institution's legal short
name without creating a product alias.

The core facade re-exports the exact defining objects. Five direct-import tests
pass and prove the accepted external tuple, immutability, invalid-referent
refusal, facade object identity, and absence of former-product aliases in the new
API. The tests use no mocks, fakes, stubs, patches, skips, or mirrored business
logic.

The promoted rule requires Cadrumo names for application-owned surfaces and
retains AEAT only for the authority, official evidence, and external protocol.
Formal review found no HIGH or CRITICAL issues. Its one MEDIUM traceability
finding was resolved by updating the closed S08 scope through the canonical plan
CLI to the actual registered rule path.

Focused imports, five tests, Ruff, formatting, plan validation, and scoped diff
checks passed. No compatibility alias, fallback, state migration, settings read,
or outer-layer import was introduced.
