---
tags:
  - '#exec'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:49038e54ebcec69baf79768e23950aad28ca5948ea15618f6df47ec1086f940a'
step_id: 'S09'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---

# Emit source, map, schema, semantic, and file digests in the provenance manifest

## Scope

- `dev/registry/`

## Description

- Move field derivation evidence into the strict provenance contract and require an exact parser anchor, semantic-map entry, emitted field, record identity, normalization schema, and closed derivation code for every field.
- Require a joined design, reviewed semantic map, explicit target, materialized layout, and complete field derivations for emission and verification; delete the prior intermediate-only builder surface.
- Emit canonical JSON as a non-loader sibling only after TOML rendering, with no timestamp, generic default, legacy input, fallback, or manifest self-digest.
- Reject authority, loader-semantic, file, derivation, path, schema, and complete-layout drift; keep the later target publication and atomic tree swap out of scope.
- Exercise direct emission and verification against a real generated revision loaded by `load_modelo_directory`.

## Outcome

The renderer now emits a canonical adjacent manifest that records source and map identity, parser and generator schema versions, target revision, loader-semantic and output-file digests, and complete per-field wire-normalization evidence. Verification rebuilds and compares current authorities rather than trusting persisted identity fields.

Focused provenance and renderer tests passed 16/16. The full `dev/registry/tests` suite passed 66/66. Owned Ruff passed, and BasedPyright reported zero errors, warnings, and notes. Independent re-review passed with no unresolved critical, high, or medium finding.

## Notes

The bounded RAG service warned that all five matches resolved to the same current provenance module; the warning was recorded and no manual reindex was performed. Vault CLI scaffolding completed despite an unrelated historical ADR UTF-8 metadata warning. No target publication or atomic tree swap was introduced; that remains W02.P04.
