---
tags:
  - '#reference'
  - '#registry-edition-authoring'
date: '2026-09-14'
modified: '2026-09-14'
body_schema: 'body-v2'
body_hash: 'sha256:60d724a6e7dd42c0c95434b33f99eb5b1c1061801189ad7ef5b090ffb9587f58'
related:
  - "[[2026-09-09-registry-edition-authoring-adr]]"
---
# `registry-edition-authoring` reference: `Signed composite export derivation`

Read-only investigation of the Modelo 296 generation refusal, using the committed parser receipt, generation epicenter, reviewed-profile types, fixed-width codec, and target-publication implementation. This blueprint identifies implementation seams; it does not authorize a new interpretation of PDF prose.

## Summary

The runtime can already encode the official representation. The generated declaration cannot express it because the generator classifies the outer alphanumeric nature as ordinary text before inspecting its subdivision. This is a generator-authority gap, not a reason to stringify the calculated Decimal or weaken the export proof.

The governing decision requires clarification before a direct prose recognizer is implemented. `2026-08-16-aeat-export-fragment-generator-authority-pdf-source-wire-fact-authority-adr` expressly rejects mechanical prose-to-sign/decimal inference and assigns PDF numeric representations to reviewed profiles. Its eligibility excludes this alphanumeric composite. The existing profile union also cannot represent it. `2026-08-18-aeat-export-fragment-generator-authority-split-part-export-value-policy-adr` concerns already parsed unsigned leaves, leaves profile authority unchanged, and does not supply an exception for this unsplit signed parent. The continuity amendment in `2026-09-09-registry-edition-authoring-adr` grants no historical layout authority. No finding here changes those decisions.

## Exact source and failure

The receipt in `src/cadrumo/_data/registry/aeat/modelos/296/revisions/2024-y-siguientes/export/_generation.provenance.json` carries the exact parser anchor: PDF record design, source row 177, ordinal 12, outer offset 145, length 15, Alfanumérico, source `aeat-dr-296-2024`. Its content states a compound value: sign at 145, numeric magnitude at 146–159, integer part at 146–157, decimal part at 158–159. The sign is N for a negative result and space otherwise; the magnitude has no embedded sign or decimal separator. The two component ranges exhaust the fourteen magnitude bytes.

The same receipt emits `m296-2024.declarante.f013`, casilla `02`, as `text`, right-space padded, left justified, unsigned, with `text-an-v1`. This conflicts with a calculated monetary value and explains the export refusal. The receipt is evidence of the existing defect, not a replacement input for regeneration: the generator must reread the hash-verified official binary through the source catalogue.

## Existing implementation boundaries

`dev/registry/pipeline/_export_tree.py:_normalise_field` delegates whole anchors to `_normalise_cell`; explicitly declared parts instead obtain `design_view` and are re-attested against the original parser anchor. `_normalise_cell` handles literal, filler and checksum kinds first. Its alphanumeric branch unconditionally produces text; its later numeric branch deliberately routes PDF anchors through the reviewed profile rather than reading descriptive content as formatting. Preserve both the literal/filler precedence and the existing numeric routing.

`_schema_field` constructs and validates `ExportFieldDefinition`, including source geometry, semantic binding, legal/source references, padding and signing. It has no `sign_position` parameter. Any approved implementation needs to carry that existing schema axis through this constructor rather than introduce a second codec or a formatted-text producer.

`src/cadrumo/domain/calculations/registry/fixed_width_codec.py` already owns `ExportSignPosition.BLANK_OR_N`. `validate_fixed_width_shape` admits it only for money with at least two bytes, left-zero padding, right justification, signed true, and neither a value policy nor an allowed-values domain. `_render_numeric_digits` reserves one sign byte and checks overflow against the remaining width. `_split_numeric_wire` accepts only space or N there. Money uses the existing cent-rounding rule; the proposed generator repair must not silently alter that runtime precision contract.

`dev/registry/pipeline/render_profile.py` provides only `Width17MembershipRule` and `SingletonNumericRule` for the relevant numeric path. The first fixes seventeen-byte Num/N representations; the second fixes unsigned Num. Neither is an admissible way to declare a fifteen-byte signed alphanumeric composite. Do not disguise the source as Num or reuse the width-17 sign-policy token: the reserved blank sign differs from a non-reserved numeric prefix.

`dev/registry/pipeline/export_fragment_provenance.py:ExportFieldDerivationCode` is a closed Literal. A new approved derivation needs its own discriminant and typed receipt; arbitrary strings or reuse of `text-an-v1` would misstate the generation proof.

## Conditional implementation blueprint

If the owning decision permits recognition of this exact structural grammar, the smallest direct derivation is a narrowly scoped helper before the ordinary alphanumeric return, producing the existing money/blank-or-N representation. Alternatively, a reviewed composite-profile rule can carry the interpretation while a helper only verifies its claimed geometry and source agreement. The authority choice belongs in the owning ADR, not this reference.

The helper should return three distinguishable outcomes: unrelated ordinary alphanumeric content, completely verified composite, and recognizable but incomplete or contradictory composite. Only the first may fall through to text. Refusing the third is essential: an incomplete signed-amount declaration must not become apparently valid text.

For the verified case, bind every parsed coordinate to the actual source anchor. Require exactly one sign slot at the outer start, one contiguous magnitude starting at start plus one and ending at the outer end, its declared digit count equal to that span, and one integer plus one decimal range partitioning that magnitude without gaps or overlaps. Require the exact supported N-for-negative/space-otherwise policy, no sign or decimal separator in the magnitude, and two fractional digits before selecting money. Reject duplicates, conflicting sign language, reversed ranges, unsupported scale, missing components, width mismatch, and source/anchor drift. Match source statements, not the casilla number, field identifier, outer width alone, or semantic caption. Normalizing whitespace, accents and quotation glyphs must not erase contradictory clauses.

For this anchor the output would retain offset 145 and length 15, declare money, decimals 2, signed true, sign_position blank_or_n, left-zero padding and right justification. Keep the canonical casilla owner, references and occurrence topology unchanged. Do not invent separately calculated sign or magnitude values.

## Detector controls

Use a source-shaped isolated parser-anchor fixture, not an assertion that a live defect remains. A positive fixture must yield the complete typed declaration and its distinct provenance code. Independent planted failures should remove each component or alter a sign coordinate, magnitude width, endpoint, integer/decimal partition, scale, or sign rule. Duplicate clauses and a valid leading clause followed by contradiction must refuse. An unrelated alphanumeric name, identifier and code must retain ordinary text behavior. Removing the composite text must remove positive recognition.

Drive the generated field through the existing codec with zero, positive and negative values, missing optional value, maximum fitting magnitude, and overflow. Assert the complete fifteen bytes: leading space for zero/positive, N for negative, fourteen magnitude digits. Retain parse/render rejection for a leading digit in the reserved sign position. Existing reference controls are in `src/cadrumo/domain/calculations/registry/tests/test_fixed_width_codec.py` around the reserved-sign fixtures and in `dev/registry/tests/test_sign_positions_are_declared.py`. Add generation/provenance round-trip coverage and actual Modelo 296 filing proof with its required repeated records; field-shape validation alone does not prove filing output.

## Regeneration and publication seam

Generated TOML and provenance are not hand-editable. The operator surface in `dev/registry/pipeline/cli.py` is `republish-target`; the corresponding recipe is `just registry-republish-target 296 2024-y-siguientes aeat-dr-296-2024 2024 0A EXPECTED_MANIFEST_SHA256`. Capture the actual current manifest digest immediately before review; do not substitute the provenance digest or a stale receipt.

The command stages a candidate, regenerates from pinned authorities, validates and transactionally publishes. `_require_republication_eligibility` permits provenance-only drift directly but requires a source-pinned record-drift disposition with remedy republish for changed record declarations. This correction changes records, so its explained disposition and existing target receipt are prerequisites, not bypassable obstacles. A disposition declaring shipped records correct must refuse republication. The target currentness check follows; whole-registry authority publication remains a separate coordinated owner and must not run while registry/compiler inputs are still moving.

After regeneration, take a fresh full-copy reference for edition enrollment. Existing pre-repair export refusal is not byte equality. Keep the generator correction proof separate from the later full-copy-versus-delta byte comparison required by `2026-09-09-registry-edition-authoring-plan`.
