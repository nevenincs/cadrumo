---
tags:
  - '#exec'
  - '#aeat-design-relayout-boundary'
date: '2026-08-18'
modified: '2026-08-18'
body_schema: 'body-v1'
body_hash: 'sha256:52474f2691a3b0e808d1944d22bc880aa5b5a53f876fb02d9f5b7d49569caeca'
step_id: 'S84'
related:
  - "[[2026-08-08-aeat-design-relayout-boundary-plan]]"
---

# `aeat-design-relayout-boundary` execution record: `W04a.P12.S84`

Author the modelo-neutral auxiliary envelope emission contract for DR23200.

## Executed

- `AuxiliaryEnvelopeHeaderDefinition` added to `_schema_exports.py` (schema_version 1, source pin, 13 prefix fields in canonical order, extent, product-identity requirement) with an `auxiliary_envelope_header` member on `ExportLayoutDefinition`; a layout declaring both a filing envelope and an auxiliary header refuses.
- `compile_auxiliary_envelope_header_definition` + `AUXILIARY_TO_PREFIX_ROLE` live in `dev/registry/_variable_envelope.py` beside the variable-envelope compiler (no new module): the parser-owned 13 roles map onto the shared prefix vocabulary, lengths come from the parser fields, extent 328 from the header.
- `render_complete_export_tree` compiles the declaration whenever the joined design carries an auxiliary header, and the layout fragment carries it.
- Coverage validator: a declared header covers its required positions over the full one-based extent; a layout without one keeps the honest "which this layout does not emit" refusal.
- Runtime: `_render_layout` prefixes the records with the declaration rendered through the ONE prefix renderer (`render_envelope_prefix_field`, now public through the filing facade); `_render_declared_prefix` is shared by the envelope and auxiliary paths; `_validate_export_options` admits the product identity for either prefix composition; `_export_parse.parse_export_payload` skips exactly `prefix_extent` bytes at the head.
- The m390 module's `_render_header_field` now delegates to the canonical prefix renderer; its own literal table and the hardcoded `"390"` value are gone. Its byte output is unchanged (existing tests prove it).
- Provenance normaliser reviewed: `auxiliary_envelope_header` admitted to `_LAYOUT_KEYS` and projected only when declared, so layouts without one attest byte-identical semantics (no version bump, no stale attestation).

## Verification

- m390 tests: 10/11 green; the one red is the standing whole-registry failure list, which carries no 232 line and no auxiliary-surface line.
- New coverage test `test_auxiliary_header_declaration_covers_the_header_and_its_absence_still_refuses` (both 232 revisions, declaration derived from the sheet's own header): declared → zero missing; absent → the header refusal line.
- New parse test `test_payload_with_auxiliary_header_prefix_skips_the_header_before_records`: the record after a 13-byte declared prefix parses; the prefix itself is skipped by extent.
- Ruff clean on every touched file; no `_render_envelope_prefix_field` references remain.
