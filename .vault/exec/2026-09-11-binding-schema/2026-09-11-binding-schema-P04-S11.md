---
tags:
  - '#exec'
  - '#binding-schema'
date: '2026-09-12'
modified: '2026-09-12'
body_schema: 'body-v2'
body_hash: 'sha256:1ab8ddb1bd9c3c9c25dda69dcbfdb7dbe226cf015bbb0916f654f9c62a302d61'
step_id: 'S11'
related:
  - "[[2026-09-11-binding-schema-plan]]"
---

# Write the CLI-owned converter that rewrites bindings/*.toml and relations/*.toml to the provider shape, with dry-run and report modes

## Scope

- `dev/registry/convert_binding_provider_shape.py`
- `justfile`

## Changes

- A `dev/registry/convert_binding_provider_shape.py`
- A `dev/registry/tests/test_convert_binding_provider_shape.py`
- M `justfile`

## Notes

Relations fragments are untouched: the Step row names them, but the relation absorption is
sequenced behind this rewrite and no relation row was read or written.
