---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:d83843d2d48e6490ec32c6fbfeef8acf29f4c60ff2ca6677da1060012f0b85ff'
step_id: 'S292'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Establish whether a detail row's physical record occurrence number in the exported fichero carries meaning, since the renderer numbers occurrences from the detail-rows tuple order while the calculation revision's content address sorts rows before hashing so a pure reorder yields the same revision id: rule whether two ficheros differing only in row order may legitimately share one revision identity, and either make the identity order-aware or record that occurrence numbering is presentation-only and prove nothing downstream depends on it

## Scope

- `src/cadrumo/domain/modelos/_calculation_revision.py canonical detail rows`
- `src/cadrumo/application/filing/_record_renderer.py`
- `the fichero parity gates`
- `and focused reorder-versus-identity tests`

## Changes

- `M` `src/cadrumo/application/modelo/_edit_models.py`
- `M` `src/cadrumo/domain/modelos/_calculation_revision.py`
- `A` `test_occurrence_order_is_a_pure_function_of_content_not_of_supply_order` in `src/cadrumo/application/filing/tests/test_m184_socio_repeat_wiring.py`
- `verify:` `uv run --no-sync pytest src/cadrumo/application/filing/tests/test_m184_socio_repeat_wiring.py src/cadrumo/domain/modelos/tests/test_calculation_revision.py src/cadrumo/application/modelo/tests/test_edit_models.py -q -m unit` -> `pass` (52 passed)

## Notes

Ruling: occurrence numbering is presentation-only, and the proof is
stronger than the Step's premise assumed. The renderer does not number
occurrences from raw `detail_rows` tuple order at all -- every
row-producer resolver in `detail_record_bindings.py`
(`resolve_atribucion_binding_row_values`, `_build_related_party_rows`,
`_build_foreign_asset_rows`, and siblings) sorts its rows by a content
key (`(country_code, tax_id)` or equivalent) BEFORE `enumerate(..., 1)`
assigns row indices. Occurrence is a deterministic function of row
content, never of caller-supplied order, so a reorder is unobservable
even at the fichero-BYTE level, not merely at the revision-id level the
existing `_canonical_detail_rows` order-blindness already covered.

Grounded against the bundled AEAT diseno de registro for modelo 184
(`corpus/aeat_official/disenos_registro/modelo_184`): the type-2 socio
record spec identifies each repeated record by its declared content
("un registro por cada clave o subclave... para los que se haya
consignado un importe y pais"), with no stated sequence requirement --
confirming there is no "declared order" for AEAT to read or lose.

Added `test_occurrence_order_is_a_pure_function_of_content_not_of_supply_order`
to `test_m184_socio_repeat_wiring.py`, rendering the same three members
through the production renderer in three different supply orders and
asserting byte-identical output.

This test landed inside a peer's unrelated S289 commit
(`2e9e0828301f57aa05a7e761baf4c64bcd54ba78`, "repoint m184 socio export
fields onto per-row member bindings") rather than a commit of my own:
the test file was that peer's own uncommitted, in-flight work when I
read and appended to it, and their subsequent commit captured my
addition along with theirs. Reported to team-lead; no further action
taken on that file since its content is correct and already committed.
The two docstring updates above were confirmed clean and committed
separately (`9adcc7cc39`).
