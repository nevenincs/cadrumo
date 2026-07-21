---
name: cadrumo-product-authority-names
derived_from:
  - "audit:2026-07-12-cadrumo-product-rename-audit"
---

# Cadrumo product and AEAT authority names

## Rule

Use `Cadrumo` in sentence prose and `CADRUMO` in identity contexts for
application-owned surfaces, and retain AEAT names
when the referent is the Spanish tax authority, its official evidence, or its
external protocol. The sole human CLI executable is the exact lowercase token
`aeat`; it names the Cadrumo command contract, not a legacy product alias.

## Why

The accepted `2026-07-12-cadrumo-cli-executable-adr` establishes `Cadrumo`
prose and `CADRUMO` identity contexts as the single product identity, `aeat` as
its one human CLI executable, and AEAT as the external authority. The
`2026-07-12-cadrumo-product-rename-audit` showed that
classifying by spelling alone creates contradictions even for apparently
obvious settings; classifying by ownership and referent prevents both stale
branding and corrupted tax-authority semantics.

## How

- Good: rename the application-controlled
  `AEAT_WALLET_DIAGNOSTIC_DUMP_DIR` setting to
  `CADRUMO_WALLET_DIAGNOSTIC_DUMP_DIR` while retaining AEAT names inside the
  authority payload stored there.
- Good: keep `adapters.outbound.aeat`, official AEAT URLs, legal provenance,
  and the `registry/aeat` taxonomy under the CADRUMO package root.
- Good: invoke the human CLI as `aeat`, import the Python package as `cadrumo`,
  and launch the distinct MCP executable as `cadrumo-mcp`.
- Bad: globally replace every `AEAT` token with `CADRUMO`, changing the name
  of the authority or byte-exact official evidence.
- Bad: retain `aeat` for a product import, environment prefix, storage owner,
  plugin, or MCP namespace, or expose `cadrumo` as a second human executable.
