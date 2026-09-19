---
tags:
  - '#reference'
  - '#filed-capture-import-targets'
date: '2026-09-13'
modified: '2026-09-13'
body_schema: 'body-v2'
body_hash: 'sha256:2da7bdbb2e8ffb2f790983f27bab2a36e45070451691b57afb3e3fda2ec52b66'
related: []
---

# `filed-capture-import-targets` reference: `Filed-capture import resolution`

The relocated filed-capture baseline integration test is adapter-owned because
it constructs the real profile repositories and validates the persisted
baseline/amendment seam. Its three modelo action imports must target the
application.modelo defining modules directly; `application.live.modelo` is not
a package in the current tree.

## Summary

The canonical mappings are `ExternalModeloImportError` from
`cadrumo.application.modelo.action_errors`, `amend_modelo_revision` from
`cadrumo.application.modelo.amendment_actions`, and `get_calculation_revision`
from `cadrumo.application.modelo.calculation_actions`. The moved test otherwise
uses canonical absolute imports and has no relative-import relocation hazards.
No alias or forwarding module is appropriate.
