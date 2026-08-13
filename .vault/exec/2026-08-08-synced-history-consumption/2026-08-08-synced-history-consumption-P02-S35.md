---
tags:
  - '#exec'
  - '#synced-history-consumption'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:f3631fec07a69a3c955fc65721210f4d4e306af3c6eff9f27741c01e71500e8e'
step_id: 'S35'
related:
  - "[[2026-08-08-synced-history-consumption-plan]]"
---
# Ground Modelo 353 group-regime carry treatment in the legal catalogue before declaring it. Add only corpus-grounded legal entries for LIVA arts. 163 quinquies, sexies and nonies, with their reviewed provenance, then declare the Modelo 322 source classification from those entries. Gate: the legal refs resolve against official corpus text, each 353 carry has its declared treatment, and the loaded registry validates.

## Scope

- `src/cadrumo/_data/registry/aeat/legal`
- `src/cadrumo/_data/registry/aeat/modelos/353`

## Description

- Ground the three LIVA group-regime provisions in the canonical IVA legal catalogue from the bundled BOE consolidated text and a live BOE cross-check.
- Declare the single Modelo 322 dependency classification owned by the Modelo 353 aggregate construct.
- Attach the existing three same-period per-group-member carries to that construct rather than duplicating treatment on each binding.
- Add a loaded-authority test that verifies the classification, its complete provenance, and the exact three consumer carries.
- Update the real M353 aggregation continuity fixture with the exact input-IVA deduction provenance that the production observation contract requires.

## Outcome

LIVA art. 163 nonies requires the dominant entity to file the group's aggregate periodic self-assessment after the individual self-assessments, and expressly says the aggregate integrates their results. Arts. 163 quinquies and 163 sexies establish the group and the regime's applicability. The canonical registry therefore classifies Modelo 322 as `direct_annual_settlement` for the Modelo 353 aggregate construct.

All three existing Modelo 353 `previous_filing` carries from Modelo 322 now consume the one canonical source classification. The classification contains the group-regime legal basis plus the pre-existing direct carry provenance required by the registry validator. Its source references resolve to the official Modelo 322 and Modelo 353 procedure/form material.

## Verification

- `uv run --no-sync ruff check src/cadrumo/domain/calculations/registry/tests/test_modelo_353_registry.py src/cadrumo/application/calculations/tests/test_modelo_353_grupo_aggregation_continuity.py` - passed.
- `uv run --no-sync pytest -q -n0 src/cadrumo/domain/calculations/registry/tests/test_modelo_353_registry.py` - 11 passed.
- `uv run --no-sync pytest -q -n0 src/cadrumo/application/calculations/tests/test_modelo_353_grupo_aggregation_continuity.py` - 3 passed.
- `uv run --no-sync pytest -q -n0 src/cadrumo/domain/calculations/registry/tests/test_cross_modelo_carry_taxonomy.py` - 8 passed.
- `uv run --no-sync aeat app registry verify` - passed; 73 models, 94 revisions, 824 legal references, and 316 source references loaded and verified.

## Notes

The integration fixture supplies `DOMESTIC_CURRENT` invoice-evidence provenance to its domestic input IVA row rather than weakening the production observation contract. That lets the suite reach and verify the Modelo 322-to-353 carry path.
