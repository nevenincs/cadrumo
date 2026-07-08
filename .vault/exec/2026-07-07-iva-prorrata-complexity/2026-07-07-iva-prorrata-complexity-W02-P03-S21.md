---
tags:
  - '#exec'
  - '#iva-prorrata-complexity'
date: '2026-07-08'
modified: '2026-07-08'
step_id: 'S21'
related:
  - "[[2026-07-07-iva-prorrata-complexity-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace iva-prorrata-complexity with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S21 and 2026-07-07-iva-prorrata-complexity-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Emit the art-103.Dos.2 +10% mandatory-especial advisory on the live M303 settlement diagnostics so the mandatory-especial breach surfaces to the operator (requires settlement-time dual-regime annual deducible-total computation) and ## Scope

- `src/aeat/application/modelo/_prorrata_regularizacion_advisory.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Emit the art-103.Dos.2 +10% mandatory-especial advisory on the live M303 settlement diagnostics so the mandatory-especial breach surfaces to the operator (requires settlement-time dual-regime annual deducible-total computation)

## Scope

- `src/aeat/application/modelo/_prorrata_regularizacion_advisory.py`

## Description

Implemented the binding ADR `2026-07-08-iva-prorrata-complexity-adr` decision (Option A: prompt-to-classify plus an honest-computability check branch), un-dormanting the S13 +10% mandatory-especial advisory on the live Modelo 303 settlement path.

- Added the public helper `compute_annual_deducible_totals_by_regime` and its frozen carrier `AnnualDeducibleTotalsByRegime` in `src/aeat/application/aggregation/_iva_ledger.py` (exported through the package `__all__`). It aggregates the ejercicio's annual IVA observations ONCE over the canonical `0A` annual `Period`, then resolves the deducible-cuota bindings TWICE over the same observations through the one canonical resolver — a GENERAL-stamped and an ESPECIAL-stamped `IvaLedgerProrrataApportionment` at the register's resolved percentage — and returns both totals, the count of unclassified deducible soportado observations, and the register regime. Returns `None` when no apportionment resolves, the register is sectorized (a named v1 deferral), the revision declares no deducible cuota bindings, or a total is negative.
- Added the two typed `CalculationSourceDiagnosticReason` members `prorrata_especial_obligatoria` and `prorrata_especial_check_unavailable` in `src/aeat/application/aggregation/_source_mesh.py`.
- Added the settlement-only especial branch to `collect_prorrata_regularizacion_diagnostics` in `src/aeat/application/modelo/_prorrata_regularizacion_advisory.py`: the CHECK branch (register ESPECIAL, or GENERAL with zero unclassified deducible soportado rows) consumes the S13 builder `build_prorrata_especial_mandatory_advisory` VERBATIM and adapts its Notice into one diagnostic (`reason=prorrata_especial_obligatoria`, `source_kind=prorrata_especial_mandatory`, message verbatim); the PROMPT branch (register GENERAL with unclassified rows) emits one `prorrata_especial_check_unavailable` diagnostic naming `--input-classification` and `app ledger prorrata elect-especial`, carrying no fabricated amounts. Both ride the existing diagnostic->Notice projection (no CLI change, no new Notice code).
- Updated the S24 inert-classification message `cli.ledger.add.input_classification_inert` via `python -m aeat.locales set` for all four catalogues (en/es/ca/hu) to state that classifying the ejercicio's inputs also enables the settlement art-103.Dos.2 mandatory-especial check on a general bucket, and matched the `default=` fallback text in `src/aeat/entrypoints/cli/_ledger.py`.
- Authored the anti-dormant test `src/aeat/application/modelo/tests/test_prorrata_especial_mandatory_live_emit.py` (real repos via `isolated_runtime_profile`, law-derived spreads).

## Outcome

Step complete. The art-103.Dos.2 obligation now reaches its intended general-filer audience on the live settlement path. Gates green: 8 new anti-dormant tests pass; the prorrata regression slice (62), JSON-schema conformance (140), CLI ledger add/classification/prorrata (67), locale parity + translation-honesty (22) all pass -n0; `aeat.locales scaffold --check` clean; ruff, ruff format, registry collect-only clean. The FIRES case fires `prorrata_especial_obligatoria` for a fully-classified GENERAL bucket with a >10% law-derived spread at 4T and confirmatorily for an ESPECIAL bucket; the PROMPT case fires `prorrata_especial_check_unavailable` for a GENERAL+unclassified bucket; SILENT for 1T / no resolvable register / <=+10% spread / sectorized; and one FIRES case is asserted through the live `collect_bucket_aggregation_advisory_diagnostics` fan-out, proving the emit is not dormant.

## Notes

- The single `ty` diagnostic (`_source_mesh.py` out-of-window `date | None` `<` operator) is PRE-EXISTING at HEAD (unrelated to this change, whose only `_source_mesh.py` edit is the two Literal members); not fixed here to avoid unrelated churn.
- No registry TOML change, no new CLI verb, no new Notice code. The S13 builder and its pinned unit tests are unchanged (consumed verbatim). Sectorized registers are a named v1 deferral, recorded in the helper docstring.
