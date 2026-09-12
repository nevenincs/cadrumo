---
tags:
  - '#exec'
  - '#binding-schema'
date: '2026-09-12'
modified: '2026-09-12'
body_schema: 'body-v2'
body_hash: 'sha256:c6322c682b66ff207ca8d3ce1c8c44c3dcf26317210ba1903557240d8857530c'
step_id: 'S12'
related:
  - "[[2026-09-11-binding-schema-plan]]"
---

# Run the converter across the corpus, delete relations fragments, replace the inventory absolute year, and republish the authority

## Scope

- `src/cadrumo/_data/registry/aeat/modelos/**/bindings/*.toml`
- `src/cadrumo/_data/registry/aeat/modelos/**/relations/`

## Changes

- M `src/cadrumo/_data/registry/aeat/modelos/{100,131,151,180,182,184,190,193,200,202,232,296,303,309,322,347,353,360,369,390,714,720}/revisions/*/bindings/*.toml`

## Notes

Seven modelos still hold legacy rows whose value contract is not derivable from any declared
source: 130, 202, 210, 303, 347, 349 and 390. Those rows were refused rather than guessed, so
their fragments were left byte-identical and those seven modelo directories do not load. Every
other modelo directory loads. Relations fragments were not deleted; that is a later Step.
