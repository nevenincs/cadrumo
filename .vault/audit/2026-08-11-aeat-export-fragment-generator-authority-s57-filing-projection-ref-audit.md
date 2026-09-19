---
tags:
  - '#audit'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:e009513f1b3f8489877b3dcad3f1df754291e436dde693388700b9af3d661249'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
  - "[[2026-06-13-m303-form-vs-semantic-casilla-dual-keying-adr]]"
---
# `aeat-export-fragment-generator-authority` audit: `S57 typed FilingProjectionRef integration review`

## Scope

Independent review of W04.P07.S57 against the accepted M303 dual-keying ADR. The review covered the core-owned `FilingProjectionRef` discriminated union and facade; `CasillaFieldKind.PROJECTION` and its exclusive `projection_ref` payload axis; semantic-map and generated-registry schemas, loaders, joins, generator and provenance; filing applicability and renderer dispatch; the prorrata-activity, differentiated-deduction, simplified-regime and exonerado-390 projectors; and direct real-behavior tests.

VaultSpec RAG was run before code discovery. The structural census found seven core union members, no remaining description/section/slot-offset/numeric/neighbour/string-key dispatch in the four projectors, typed exact-identity renderer keys, complete prorrata and differentiated matrices, complete exonerado population validation, and duplicate-ref refusal in every projector family. The focused real gate completed with 115 passed in 104.00 seconds across core, semantic-map, registry vocabulary, all four projector families, renderer policy and M303 applicability/evidence tests.

Verdict: NOT APPROVED. Three high-severity findings remain. During review, concurrent uncommitted changes appeared in `src/cadrumo/application/filing/_export.py`, `src/cadrumo/application/filing/_m303_export_applicability.py`, `src/cadrumo/application/filing/tests/test_export_value_policy.py`, and `src/cadrumo/domain/calculations/registry/_schema_surfaces.py`; they partially address the third finding but are shared WIP, are not a complete generator-to-renderer correction, and are not accepted by this audit.

## Findings

### projection-ref-wire-coercion | high | Both authored loaders accept noncanonical projection-reference scalar types

- [ ] `src/cadrumo/domain/calculations/registry/_loader.py` and `dev/registry/_semantic_map_loader.py` both invoke `TypeAdapter(FilingProjectionRef).validate_python(..., strict=False)`. This overrides the strict/frozen member models at the authored wire boundary: direct execution accepted slot values `"1"`, `1.0`, and `true` and coerced each to integer slot `1`, while `strict=True` refused them. The semantic-map test proves only the happy string-to-enum path and does not prove rejection of noncanonical scalar types. S57 requires a strict core-owned discriminated union, so broad Pydantic coercion is an unauthorized fallback authority.

### projection-none-preseed | high | Blanket None pre-seeding launders missing projector output into valid blank fields

- [ ] `validate_m303_export_applicability` constructs `projected_values` with every authored projection identity already present and value `None` before any projector runs. `_field_value` refuses only an absent key. Therefore an applicable projector that omits an expected endpoint is indistinguishable from an explicitly authorized non-applicable blank and silently renders whitespace. This defeats the exact typed-value arrival guard and violates the no-fallback requirement. Non-applicability blanks must be emitted explicitly by the owning family; applicable omissions must remain absent and fail.

### projection-row-occurrence | high | The generator does not declare repeated projection records, so DP30302 occurrence is lost

- [ ] `project_m303_regimen_simplificado_rows` emits values keyed by record occurrence and `validate_m303_export_applicability` carries them as row indices `0..2`, but the committed `ExportRecordDefinition.repeat` admits only `binding_rows`, `_record_render_rows` gives every non-binding record `row_index=None`, and `dev/registry/_export_tree.py::_render_records` emits no repeat semantics at all. Thus generated DP30302 projection fields cannot select their occurrence keys. Concurrent WIP adds `repeat="projection_rows"` and renderer selection from typed values, but the generator and semantic record authority still do not emit that mode, so the live generated route remains incomplete.

## Recommendations

- Replace both `strict=False` adapters with one core-owned exact wire compiler that converts only the closed discriminator/enum string tokens required by TOML and rejects bool, float, numeric-string and other scalar coercions. Add direct negative loader tests for both registry and semantic-map boundaries.
- Remove blanket projection-value pre-seeding. Make each projection family explicitly return its authorized non-applicability blanks and add an applicable-projector omission proof that reaches the real renderer and fails on the absent exact typed key.
- Carry a typed projection-row occurrence mode through the semantic record schema, semantic-map loader/join, generator, provenance and registry loader, then prove real generated DP30302 output renders the correct number and order of occurrences. Synthetic renderer-only coverage is insufficient.
- Re-run the same focused real suite plus generated-tree/provenance checks after remediation, and request append-only independent re-review before S57 is marked complete.

## Re-review resolution - 2026-08-11

Verdict: APPROVED. The current S57 worktree closes all three historical high-severity findings. This resolution is append-only: the original finding text remains above as the record of the rejected snapshot.

- `projection-ref-wire-coercion` is resolved. `compile_filing_projection_ref` is the sole public core wire compiler and the only two production authored-TOML consumers are the semantic-map and registry loaders. It requires exact string keys, exact strings for every string wire field, and `type(slot) is int` before the closed discriminated union hydrates. Independent runtime probes rejected slot string, float and bool; integer keys; non-string discriminator, field and casilla values; and an extra legacy key (8/8 rejected). Both real TOML loaders directly prove string/float/bool slot refusal.
- `projection-none-preseed` is resolved. The blanket dictionary pre-seed is gone. Exonerado, prorrata and differentiated families emit blanks only in their own typed non-applicable branches; applicable exonerado omission refuses, applicable prorrata and differentiated paths retain complete matrix validation, and applicable simplified-regime zero occurrence refuses. Simplified non-claim produces no projection occurrence rather than a fabricated blank row. Renderer dispatch still requires the exact typed identity and occurrence key.
- `projection-row-occurrence` is resolved. Strict `SemanticMapRecord.required` and `repeat="projection_rows"` flow unchanged through the real TOML loader, joined semantic record, generator, provenance exact-key normalization, generated registry record schema and renderer. Generated-tree tests cover both `required=false` and `required=true`; renderer tests prove ordered typed occurrences, required zero-occurrence refusal and optional zero-occurrence omission.

Independent verification completed with 166 focused tests passing before the final required/optional correction and 93 post-correction focused tests passing in 37.83 seconds. The real `aeat app registry verify` command returned `Verificado=True` over 73 modelos and 94 revisions. The exact compiler boundary probe rejected all eight noncanonical cases. The final S57 production-path Ruff check passed, all 11 reviewed files passed Ruff format-check, and scoped `git diff --check` passed. Structural searches found no description, section, offset, numeric, neighbouring-field, regex or string-key inference in the four projectors, and found no production FilingProjectionRef adapter outside the core compiler.

No remaining S57 findings were identified. Unrelated shared-worktree changes were preserved and were not included in this verdict.
