---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-27'
modified: '2026-08-27'
body_schema: 'body-v2'
body_hash: 'sha256:a6adb49c04f5d5f734bc5575e010f6577f19b03d8136a6819aac92f8400a2148'
step_id: 'S299'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Widen Modelo184MemberRow's identity to (nif, clave, subclave) per the accepted row-shape ADR, add its clave-conditional fields, extend the S288 natural-key tuple for the miembro row kind to match, extend AtribucionMemberSourceResolver to read S297's new profile facts into per-row bindings mirroring the existing nif/name/share/base wiring, add the registry bindings and repoint the corresponding socio export fields from kind='casilla' to kind='binding', and extend _ROW_IDENTITY_FIELDS's Modelo184MemberRow entry to (nif, clave, subclave) in the same change so S298's two-source union does not collide two of one member's rows declared under different claves. Only once every money-bearing field in this scope has a real per-row source, declare the record repeat = 'binding_rows'. Excludes clave-A reduccion, provisiones-gastos and clave-E exactly as S297 excludes them. Prove a real multi-member, multi-clave attribution emits one occurrence per (member, clave, subclave) with the right values in every field this scope covers, not merely the right count, and prove two rows for one member under different claves survive S298's union as distinct rows rather than colliding

## Scope

- `Modelo184MemberRow in _row_models.py`
- `_edit_services.py's natural-key table`
- `_calculation_modelo_adjustments.py's _ROW_IDENTITY_FIELDS`
- `AtribucionMemberSourceResolver`
- `the modelo 184 bindings and socio export record in both revisions`
- `and a grounded multi-member multi-clave export parity test`

## Changes

- `M` `src/cadrumo/domain/modelos/_row_models.py`
- `M` `src/cadrumo/domain/calculations/registry/detail_record_bindings.py`
- `M` `src/cadrumo/application/aggregation/_atribucion_member.py`
- `M` `src/cadrumo/application/modelo/_edit_services.py`
- `M` `src/cadrumo/application/modelo/_calculation_modelo_adjustments.py`
- `M` `src/cadrumo/_data/registry/aeat/modelos/184/revisions/2025-y-siguientes/bindings/0001-bindings.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/184/revisions/2023-2024/bindings/0001-bindings.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/184/revisions/2025-y-siguientes/export/0004-record-m184-socio.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/184/revisions/2023-2024/export/0004-record-m184-socio.toml`
- `M` `src/cadrumo/locales/es/common.yml`, `src/cadrumo/locales/en/common.yml`, `src/cadrumo/locales/ca/common.yml`, `src/cadrumo/locales/hu/common.yml` (sheets.detalle.headers.* for the new row fields)
- `M` `src/cadrumo/domain/modelos/tests/test_row_models.py`
- `M` `src/cadrumo/domain/modelos/tests/test_row_models_m347_revision.py`
- `M` `src/cadrumo/domain/modelos/tests/test_calculation_revision.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_detail_record_row_builders.py`
- `M` `src/cadrumo/application/modelo/tests/test_calculation_modelo_adjustments.py`
- `M` `src/cadrumo/application/modelo/tests/test_detail_row_modelo_membership.py`
- `M` `src/cadrumo/application/aggregation/tests/test_atribucion_member_required_set.py`
- `M` `src/cadrumo/application/aggregation/tests/test_atribucion_member_value_validity.py`
- `M` `src/cadrumo/entrypoints/cli/tests/test_m184_socio_handoff_notices.py`
- `M` `src/cadrumo/entrypoints/cli/tests/test_work_calculate_row_flag.py`
- `A` `src/cadrumo/application/modelo/tests/test_m184_multi_clave_export_parity.py`
- `verify:` `pytest src/cadrumo/domain/modelos/tests/ src/cadrumo/application/aggregation/tests/ src/cadrumo/application/modelo/tests/test_m184_multi_clave_export_parity.py src/cadrumo/domain/calculations/registry/tests/test_modelo_184_registry.py` -> `pass`
- `verify:` `pytest src/cadrumo/domain/calculations/registry/tests/` -> `pass, except pre-existing unrelated failures (see Notes)`
- `verify:` `pytest -m integration src/cadrumo/entrypoints/cli/tests/test_work_calculate_row_flag.py::TestParseRowSpecValid` -> `pass`
- `verify:` `pytest src/cadrumo/application/modelo/tests/test_m184_multi_clave_export_parity.py` (clave-A refusal + C/D non-regression cases, follow-up commit) -> `pass`

## Notes

Most production-code changes in this Step landed already committed to HEAD
before this agent's own commits (`a2cfe67d47`, `9599268f27` and related) with
byte-identical content to what this agent independently authored from the
same diseño/ADR sources -- verified via `git diff HEAD` returning empty for
each file before staging. This agent's own commits carry the residual test
fixes the widened `Modelo184MemberRow` identity required across the wider
test suite, plus the multi-member multi-clave export parity test this
Step's own action text requires, which did not yet exist.

The clave-C/clave-D `reduccion` field is modelled as ONE registry binding
and ONE row field (matching the diseño's own shared physical field,
positions 109-119), consistent with S297's schema-field decision; its
`legal_refs` cite both `ley-35-2006:art-23` (clave C) and `art-32` (clave
D), both already present in the legal catalogue.

A boolean profile fact (`miembro_a_31_diciembre`) is carried through
`AtributionMemberObservation` as the diseño's own `"X"`/blank text flag
rather than a Python bool, because the export field's declared
`data_type = "text"` renders that literal shape, not a bool coercion the
renderer was never asked to support.

`resolve_atribucion_binding_row_values` now distinguishes a genuinely
unproduced row-field key (still a hard `RegistryValidationError`) from a
clave-conditional field that is legitimately `None` for a given row (now
skipped rather than raised), since the four pre-existing bindings assumed
every row field was always populated and the fifteen new ones are not.

Two unrelated pre-existing failures were observed and left untouched: four
`test_work_calculate_row_flag.py::TestRevisionViewSurfacesDetailRows` CLI
integration tests (both M184 and, identically, untouched M349 cases) refuse
with "Recovery enrollment is mandatory" in this environment, and the wider
`test_calculations/registry/tests/` run carries ~25 failures naming other
modelos (194, 200, 220, 270, 308, 721, iva place-of-supply,
counterpart-source-kind) tied to other agents' in-flight uncommitted work in
this shared worktree, confirmed by their appearing under `git status` as
modified by files this Step never touches. A separate pre-existing
regression, also confirmed unrelated to this Step via `git log`, was found
during verification: `test_text_casilla_routing.py::test_build_draft_routes_and_validates_required_m184_member_nif`
references a casilla id another peer's registry commit already removed
(the tree carries its own comment noting the removal); left untouched,
different family's cleanup.

Follow-up commit closes a real gap the honest-pass review caught: the
accepted row-shape ADR blocks the clave-A reducción pending its unresolved
governing provision, but nothing in code enforced it -- the shared
clave-C/clave-D `reduccion` field was reachable under clave A too, since it
is modelled as one field matching the diseño's own physical layout. Added
`Modelo184MemberRow._clave_a_reduccion_stays_blocked`, a model validator
refusing a populated `reduccion` when `clave == "A"`, at the row boundary
(rather than the resolver) so it blocks every supply path -- CLI manual
entry and any future resolver wiring alike -- uniformly. Proved via three
new cases in `test_m184_multi_clave_export_parity.py`: the refusal fires,
claves C and D still populate `reduccion` unaffected, and a clave-A row
with no `reduccion` still constructs cleanly.
