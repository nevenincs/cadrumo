---
name: cadrumo-product-authority-names
derived_from:
  - "audit:2026-07-12-cadrumo-product-rename-audit"
---

# Cadrumo product and AEAT authority names

## Rule

Always use Cadrumo identity for application-owned surfaces and retain AEAT names
only when the referent is the Spanish tax authority, its official evidence, or
its external protocol.

## Why

The accepted `2026-07-12-cadrumo-product-rename-adr` establishes Cadrumo as the
single product identity without aliases, while AEAT remains the external
authority. The `2026-07-12-cadrumo-product-rename-audit` showed that classifying
by spelling alone creates contradictions even for apparently obvious settings;
classifying by ownership and referent prevents both stale branding and corrupted
tax-authority semantics.

## How

- Good: rename the application-controlled
  `AEAT_WALLET_DIAGNOSTIC_DUMP_DIR` setting to
  `CADRUMO_WALLET_DIAGNOSTIC_DUMP_DIR` while retaining AEAT names inside the
  authority payload stored there.
- Good: keep `adapters.outbound.aeat`, official AEAT URLs, legal provenance,
  and the `registry/aeat` taxonomy under the Cadrumo package root.
- Bad: globally replace every `AEAT` token with `Cadrumo`, changing the name
  of the authority or byte-exact official evidence.
- Bad: retain `aeat` for a product import, executable, environment prefix,
  storage owner, plugin, or MCP namespace.
