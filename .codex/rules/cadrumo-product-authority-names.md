---
name: cadrumo-product-authority-names
trigger: always_on
---

# Cadrumo product and AEAT authority names

Use `Cadrumo` in sentence prose and `CADRUMO` in identity contexts for
application-owned surfaces, and retain AEAT names when the referent is the
Spanish tax authority, its official evidence, or its external protocol. The sole
human CLI executable is the exact lowercase token `aeat` — it names the Cadrumo
command contract, not a legacy product alias.

Classifying by spelling alone creates contradictions even for apparently obvious
settings; classify by **ownership and referent** instead, which prevents both
stale branding and corrupted tax-authority semantics.

## How

- **Good:** rename an application-controlled `AEAT_WALLET_DIAGNOSTIC_DUMP_DIR`
  setting to `CADRUMO_WALLET_DIAGNOSTIC_DUMP_DIR`, while retaining AEAT names
  inside the authority payload stored there.
- **Good:** keep `adapters.outbound.aeat`, official AEAT URLs, legal provenance
  and the `registry/aeat` taxonomy under the CADRUMO package root.
- **Good:** invoke the human CLI as `aeat`, import the Python package as
  `cadrumo`, and launch the distinct MCP executable as `cadrumo-mcp`.
- **Bad:** globally replacing every `AEAT` token with `CADRUMO`, changing the
  name of the authority or of byte-exact official evidence.
- **Bad:** retaining `aeat` for a product import, environment prefix, storage
  owner, plugin or MCP namespace, or exposing `cadrumo` as a second human
  executable.

Source: ADR `2026-07-12-cadrumo-cli-executable-adr`; audit
`2026-07-12-cadrumo-product-rename-audit`.
