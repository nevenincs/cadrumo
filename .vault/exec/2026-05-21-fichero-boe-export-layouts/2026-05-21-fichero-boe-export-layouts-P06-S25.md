---
tags:
  - '#exec'
  - '#fichero-boe-export-layouts'
date: '2026-07-03'
modified: '2026-07-17'
body_hash: 'sha256:93f2f36bd3ea927ae63ad4c73f632dd2dd6a1cea94e4296d48792d8615cba0f0'
step_id: 'S25'
related:
  - "[[2026-05-21-fichero-boe-export-layouts-plan]]"
---

# Author the M390 fixed-width export layout grounded in the bundled AEAT Diseno de Registros, wire export_refs on the manifest casillas and computed totals, add the export application_link, and cover with the completeness-parity, thin-draft anti-tautology, and export-parse roundtrip gates

## Scope

- `src/aeat/_data/registry/aeat/modelos/390/revisions/2010-y-siguientes/export_layouts/0001-export_layouts.toml`

## Description

- Ground the manifest's eleven bound casillas and three computed annual totals against the bundled AEAT Diseno de Registros ejercicio-2025 xlsx for `modelo_390`, extracting real box positions across pages 0/1/2/2bis/3/4/6.
- Author the `modelo-390-fichero-boe` fixed-width export layout: envelope header/footer, page_01 identity, page_02 (repercutido general/reducido/super-reducido, autorepercutido intracomunitaria, total cuota devengada), page_02b (recargo de equivalencia general/reducido), page_03 (soportado interiores/importaciones), page_04 (total cuota deducible, resultado regimen general), page_06 (regimen simplificado carry, compensacion casillas 97/662).
- Wire `export_refs` on every manifest casilla with a real DR box, including the three computed totals (cuota devengada/deducible total, resultado regimen general) mapped onto boxes 34/64/65 so the completeness gate is non-vacuous.
- Add the required `export` application_link (`modelo-390-export`) satisfying the registry's application-link closure validator.
- Add a M390 registry-backed draft builder and headers fixture to the shared export-support test module.
- Wire modelo 390 into the multi-modelo completeness-parity gate (`_COVERED` and `_DORMANCY_MODELOS`), parametrize the thin-draft anti-tautology gate over 130/390, and add a M390 case to the export-parse roundtrip gate (mutated-byte proof included).
- Replace the now-obsolete `test_modelo_390_export_refuses_missing_boe_layout_from_real_registry` (which asserted the pre-existing gap) with a positive proof that the export now succeeds.
- Post a GitHub issue #508 comment documenting the landed slice and the remaining scope (issue left open).

## Outcome

Modelo 390 (IVA resumen anual) now ships a fixed-width fichero-BOE export layout, closing the last of the eight modelos issue #508 flagged as missing one (the other seven -- 111, 115, 123, 131, 180, 200 -- had already landed in a prior campaign pass; only 390 remained). All 35 touched tests pass (completeness-parity, completeness-gate thin-draft, export-parse roundtrip, registry-boundary positive test). `ruff check` and `ruff format --check` are clean on every touched file; `python -m aeat.locales scaffold --check` is clean. Modelo 100 remains export-format-covered only by `xml_dictionary` (its actual AEAT "importar datos" surface); no bundled fixed-width DR100 exists to ground a fixed-width layout against, so it is out of scope of this fichero-BOE gap by design, not a remaining defect.

## Notes

The full unscoped registry-authority load (`resources().modelos.authority.snapshot(...)`, which validates every modelo's fragments together) intermittently failed during this session from unrelated, concurrently-in-flight peer WIP touching Modelo 202 source fingerprints and the bundled corpus HTML files (uncommitted at the time of this Step). The scoped `build_runtime_schema_provider(modelos=("390",))` path -- the same path production `export_draft` consumers and this Step's tests use -- built and validated cleanly throughout; the unscoped-load failures are peer-campaign churn outside this Step's ownership boundary and were not touched.
