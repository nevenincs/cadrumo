---
tags:
  - '#reference'
  - '#registry-header-requirements'
date: '2026-10-12'
modified: '2026-10-12'
body_schema: 'body-v2'
body_hash: 'sha256:e23ba9c3d0b38bd25dc621413451130812c365241484f832771e8bf41a2d0413'
related: []
---

# `registry-header-requirements` reference: `Where a generated export field gets its requirement`

How a generated export field came to be required or optional before this feature, read at commit `f80a12a835`, and what the Modelo 111 sources say. Sources: the generator, the semantic map, the export renderer and validator, the 111 generated tree, and the bundled 111 instructions.

## Summary

- The generator sets a field's `required` only from the design's Validación cell: `_is_required` at `dev/registry/pipeline/export_field_schema.py:153`, reading the wordings in `_UNCONDITIONAL_REQUIREMENTS` (`:107`). A qualified wording becomes `required_for` through `_qualified_requirement` (`:137`), wired at `:83`. A silent cell yields neither.
- The semantic map's only requirement field is `required_with` (`dev/registry/pipeline/semantic_map.py:341`), and the layout validator admits it only on casilla fields (`src/cadrumo/domain/calculations/registry/export_field_validation.py:204`). `required_for` is admitted only on header fields (`:190`).
- Export refuses a blank header only when the layout says so: `src/cadrumo/application/filing/record_field_renderer.py:370-371`, with `required_for` evaluated against the taxpayer's legal form by `_required_for_this_taxpayer` (`:394`). The refusal text names the producer key.
- The producer resolves `taxpayer.surnames_or_legal_name` from surnames or legal name (`src/cadrumo/application/filing/export_producer.py:1203`); those come from the profile facts `identity.surnames`, `identity.legal_name` and `identity.name` (`src/cadrumo/application/modelo/profile_export_binding.py`, the `_IDENTITY_*_KEY` constants and `_taxpayer_identity_facts`).
- Modelo 111's page sheet `dr M11101` prints no Validación, so the generated tree shipped NIF, apellidos, nombre, ejercicio and periodo as `required = false` (`src/cadrumo/_data/registry/aeat/modelos/111/revisions/2019-y-siguientes/export/0001-record-modelo-111-page-01.toml`, e.g. lines 106, 128, 150 at that commit).
- The requirement is stated by source `aeat-modelo-111-instructions` (`src/cadrumo/_data/corpus/aeat_official/instructions/modelo_111/files/modelo-111-instrucciones.html`): Apartado "IDENTIFICACIÓN" at line 235-236, "Introduzca el NIF del declarante y los apellidos y nombre o bien la razón social de la persona o entidad."; Apartado "DEVENGO" at line 237 onward, ejercicio and período. The nombre half applies only to a person.
- Precedent for carrying an optional semantic-map field through provenance without changing other maps' digests: `required_with` is digested and serialized only when declared (`dev/registry/pipeline/export_fragment_provenance_projection.py`, `_normalise_semantic_map_entry`; `dev/registry/pipeline/export_fragment_provenance.py`, `export_fragment_provenance_manifest_json_bytes`).
- Replacing a published tree whose records change goes through `republish-target` with the reviewed manifest digest and a source-pinned `record_drift` row with remedy `republish` (`dev/registry/pipeline/cli.py`, `_require_republication_record_disposition`; `dev/registry/pipeline/generated_tree_dispositions.toml`), retired once the tree reproduces.
